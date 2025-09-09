from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.settings import settings
from core.channel.publisher import _is_under_posts_root
from core.utils import collect_images
from handlers.scan.scan import (
    send_media_preview,
    build_preview_text,
    parse_meta,
    caption_trim,
)
from storages import scheduled_store
from storages.publication import TOKENS

tg_bot_settings = settings.TGBOT


async def list_jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    store = scheduled_store.load_all()
    if not store:
        await update.message.reply_text("Запланированных публикаций нет.")
        return

    items = sorted(store.items(), key=lambda kv: kv[1].run_at)
    lines = []
    for job_id, item in items[:50]:  # ограничим вывод
        if not item.folder.exists():
            status = " (папка отсутствует)"
        else:
            status = ""
        lines.append(
            f"• <code>{job_id}</code> — {item.folder.name}{status}\n"
            f"  🕒 { item.format_run_at() }"
        )

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )


async def view_job_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("Укажи job_id: /view_job <job_id>")
        return
    job_id = args[0].strip()

    store = scheduled_store.load_all()
    item = store.get(job_id)
    if not item:
        await update.message.reply_text("Задача не найдена.")
        return

    folder = item.folder
    if not folder.exists() or not _is_under_posts_root(folder):
        await update.message.reply_text("Папка публикации недоступна.")
        return

    # Обеспечим наличие токена→папки для кнопок publish_now/schedule
    TOKENS[item.token] = str(folder)

    # Медиа-превью
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

    # Текстовая карточка + плановое время
    meta = parse_meta(folder / "meta.json")
    text = (
        build_preview_text(folder, meta, desc)
        + f"\n\n<b>🕒 Плановая публикация:</b> {item.format_run_at()}"
    )

    # Кнопки действий
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
                    "❌ Отменить задачу", callback_data=f"cancel_job:{job_id}"
                )
            ],
        ]
    )

    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True
    )
