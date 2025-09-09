import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telegram import Update, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, Application

from config.logger import get_logger
from config.settings import settings, MEDIA_GROUP_LIMIT, TZ
from core.utils import collect_images
from handlers.scan.scan import (
    caption_trim,
    parse_meta,
    send_media_preview,
    build_preview_text,
)
from schemas.schema import ScheduledPost
from storages import scheduled_store
from storages.publication import TOKENS

tg_bot_settings = settings.TGBOT
log = get_logger(__name__)


def _schedule_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 Сейчас", callback_data=f"publish_now:{token}")],
            [
                InlineKeyboardButton(
                    "⏱ +15 мин", callback_data=f"schedule_in:{token}:900"
                ),
                InlineKeyboardButton(
                    "⏱ +1 ч", callback_data=f"schedule_in:{token}:3600"
                ),
                InlineKeyboardButton(
                    "⏱ +3 ч", callback_data=f"schedule_in:{token}:10800"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📅 Ввести дату/время", callback_data=f"schedule_input:{token}"
                ),
            ],
            [InlineKeyboardButton("✖️ Отмена", callback_data=f"cancel:{token}")],
        ]
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    cq = update.callback_query

    data = cq.data or ""
    m = re.match(
        r"^(approve|skip|publish_now|schedule|schedule_in|schedule_input|cancel|cancel_job|view_job):([a-f0-9]{12}|[\w-]+)(?::(\d+))?$",
        data,
    )

    if not m:
        await cq.answer("Неизвестное действие")
        return

    action, key, extra = m.group(1), m.group(2), m.group(3)

    token = key if action not in {"cancel_job", "view_job"} else None
    folder_str = TOKENS.get(token)

    if not folder_str and action not in {"cancel"}:
        await cq.answer("Кнопка устарела — перезапусти /scan")
        return

    folder = Path(folder_str) if folder_str else None
    if folder and (not folder.exists() or not _is_under_posts_root(folder)):
        TOKENS.pop(token, None)
        await cq.answer("Папка недоступна")
        return

    if action == "skip":
        try:
            (folder / ".lock").unlink(missing_ok=True)
        except Exception:
            pass
        TOKENS.pop(token, None)
        await cq.edit_message_text("⏭️ Пропущено: " + folder.name)
        return

    if action in {"approve", "schedule"}:
        await cq.answer()
        await cq.edit_message_reply_markup(reply_markup=_schedule_kb(token))
        return

    if action == "publish_now":
        await cq.answer("Публикую…")
        await _publish_folder_now(
            context.application, folder, tg_bot_settings.CHANNEL_ID
        )
        await cq.edit_message_text("✅ Опубликовано и удалено: " + folder.name)
        TOKENS.pop(token, None)
        return

    if action == "schedule_in":
        await cq.answer("Планирую…")
        secs = int(extra or "0")
        run_at_utc = datetime.now(timezone.utc) + timedelta(seconds=secs)
        await _schedule_publication(context, token, folder, run_at_utc)
        when_local = run_at_utc.astimezone(TZ).strftime("%Y-%m-%d %H:%M")
        await cq.edit_message_text(
            f"🕒 Запланировано на {when_local}\nПост: {folder.name}"
        )
        return

    if action == "schedule_input":
        await cq.answer()
        context.user_data["awaiting_dt_for_token"] = token
        context.user_data["awaiting_dt_for_folder"] = str(folder)
        await cq.message.reply_text(
            "Введи дату и время публикации в формате YYYY-MM-DD HH:MM (по твоему времени).\n"
            "Напр.: 2025-09-04 18:30\n"
            "Или /cancel"
        )
        return
    # Новый кейс: отмена запланированной задачи по job_id
    if action == "cancel_job":
        await cq.answer("Отменяю…")
        job_id = key
        # снять с планировщика и удалить из стора
        try:
            context.application.job_queue.scheduler.remove_job(job_id)
        except Exception:
            pass
        scheduled_store.pop(job_id)
        await cq.edit_message_text("❌ Задача отменена")
        return

    # Новый кейс: просмотр по job_id (то же, что /view_job, но по кнопке)
    if action == "view_job":
        await cq.answer()
        store = scheduled_store.load_all()
        item = store.get(key)
        if not item:
            await cq.edit_message_text("Задача не найдена.")
            return
        folder = item.folder
        if not folder.exists() or not _is_under_posts_root(folder):
            await cq.edit_message_text("Папка публикации недоступна.")
            return

        TOKENS[item.token] = str(folder)

        images = collect_images(folder)
        desc_path = folder / "description.txt"
        desc = (
            desc_path.read_text("utf-8", errors="replace").strip()
            if desc_path.exists()
            else None
        )
        await send_media_preview(
            context.application,
            tg_bot_settings.ADMIN_CHAT_ID,
            images,
            caption_trim(desc or folder.name),
        )

        meta = parse_meta(folder / "meta.json")
        text = (
            build_preview_text(folder, meta, desc)
            + f"\n\n<b>🕒 Плановая публикация:</b> {item.format_run_at()}"
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🟢 Сейчас", callback_data=f"publish_now:{item.token}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⏱ Перепланировать", callback_data=f"schedule:{item.token}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Отменить задачу", callback_data=f"cancel_job:{key}"
                    )
                ],
            ]
        )
        # Обновим клавиатуру/сообщение
        await cq.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        return

    if action == "cancel":
        await cq.answer("Отменено")
        await cq.edit_message_text("❌ Отменено")
        return


# Вынесенная публикация (немедленная)
async def _publish_folder_now(
    app: Application, folder: Path, channel: int | str
) -> None:
    desc_path = folder / "description.txt"
    desc = (
        desc_path.read_text("utf-8", errors="replace").strip()
        if desc_path.exists()
        else None
    )
    images = collect_images(folder)
    await publish_to_channel(app, channel, images, caption_trim(desc or folder.name))
    # удалить папку
    shutil.rmtree(folder)


async def publish_to_channel(
    app: Application, channel: int | str, images: list[Path], caption: str
) -> None:
    if images:
        first = True
        for i in range(0, len(images), MEDIA_GROUP_LIMIT):
            chunk = images[i : i + MEDIA_GROUP_LIMIT]
            media = []
            for j, img in enumerate(chunk):
                try:
                    f = img.open("rb")
                except Exception as e:
                    log.warning("Cannot open %s: %s", img, e)
                    continue
                media.append(
                    InputMediaPhoto(
                        f, caption=caption if first and j == 0 and caption else None
                    )
                )
            if media:
                await app.bot.send_media_group(chat_id=channel, media=media)
            first = False
    else:
        await app.bot.send_message(chat_id=channel, text=caption or "")


async def on_schedule_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    token = context.user_data.pop("awaiting_dt_for_token", None)
    folder_str = context.user_data.pop("awaiting_dt_for_folder", None)
    if not token or not folder_str:
        return

    folder = Path(folder_str)
    if not folder.exists() or not _is_under_posts_root(folder):
        await update.message.reply_text("Папка недоступна.")
        return

    text = (update.message.text or "").strip()
    try:
        dt_local = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        await update.message.reply_text(
            "Неверный формат. Пример: 2025-09-04 18:30. Повтори или /cancel"
        )
        # вернуть «ожидание»
        context.user_data["awaiting_dt_for_token"] = token
        context.user_data["awaiting_dt_for_folder"] = folder_str
        return

    run_at_utc = dt_local.astimezone(timezone.utc)
    await _schedule_publication(context, token, folder, run_at_utc)
    when_local = dt_local.strftime("%Y-%m-%d %H:%M")
    await update.message.reply_text(
        f"🕒 Запланировано на {when_local}\nПост: {folder.name}"
    )


def _is_under_posts_root(p: Path) -> bool:
    try:
        p.resolve().relative_to(tg_bot_settings.POSTS_ROOT.resolve())
        return True
    except Exception:
        return False


async def restore_scheduled(app: Application) -> None:
    store = scheduled_store.load_all()
    if not store:
        return

    now = datetime.now(timezone.utc)
    new_store: dict[str, ScheduledPost] = {}

    async def publish_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
        data = ScheduledPost.model_validate(ctx.job.data)
        folder = data.folder
        if folder.exists():
            try:
                await _publish_folder_now(ctx.application, folder, data.channel)
            finally:
                scheduled_store.pop(ctx.job.id)
        else:
            scheduled_store.pop(ctx.job.id)

    for old_job_id, item in store.items():
        folder = item.folder
        if not folder.exists():
            scheduled_store.pop(old_job_id)
            continue

        if item.run_at <= now:
            scheduled_store.pop(old_job_id)

            token = uuid.uuid4().hex[:12]
            TOKENS[token] = str(folder)
            try:
                (folder / ".lock").write_text(token, encoding="utf-8")
            except Exception:
                pass

            desc_path = folder / "description.txt"
            desc = (
                desc_path.read_text("utf-8", errors="replace").strip()
                if desc_path.exists()
                else None
            )
            images = collect_images(folder)
            meta = parse_meta(folder / "meta.json")

            await send_media_preview(
                app,
                tg_bot_settings.ADMIN_CHAT_ID,
                images,
                caption_trim(desc or folder.name),
            )

            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Утвердить и опубликовать",
                            callback_data=f"approve:{token}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⏭️ Пропустить", callback_data=f"skip:{token}"
                        )
                    ],
                ]
            )
            await app.bot.send_message(
                chat_id=tg_bot_settings.ADMIN_CHAT_ID,
                text=build_preview_text(folder, meta, desc),
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            continue

        job = app.job_queue.run_once(
            publish_job,
            when=item.run_at,
            data=item.model_dump(),
        )
        new_store[job.id] = item

    scheduled_store.save_all(new_store)


async def _schedule_publication(
    context: ContextTypes.DEFAULT_TYPE, token: str, folder: Path, run_at_utc: datetime
) -> None:
    if context.application.job_queue is None:
        log.error("JobQueue не инициализирован.")
        return

    try:
        (folder / ".lock").write_text(token, encoding="utf-8")
    except Exception:
        pass

    item = ScheduledPost(
        token=token,
        folder=folder,
        channel=tg_bot_settings.CHANNEL_ID,
        run_at=run_at_utc,
    )

    async def publish_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
        data = ScheduledPost.model_validate(ctx.job.data)
        if data.folder.exists():
            try:
                await _publish_folder_now(ctx.application, data.folder, data.channel)
            finally:
                scheduled_store.pop(ctx.job.id)
        else:
            scheduled_store.pop(ctx.job.id)

    job = context.application.job_queue.run_once(
        publish_job,
        when=item.run_at,
        data=item.model_dump(),
    )
    scheduled_store.add(job.id, item)
