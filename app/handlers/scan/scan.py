from __future__ import annotations

import json

from core.utils import html_escape, collect_images
from storages.publication import TOKENS, JOBS
from config.settings import MAX_CAPTION, MEDIA_GROUP_LIMIT

import uuid
from pathlib import Path
from app.config.settings import settings
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
)

from config.logger import get_logger

log = get_logger(__name__)

tg_bot_settings = settings.TGBOT


async def start_scan_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    task_id = str(uuid.uuid4())  # Генерируем уникальный ID для задачи
    await periodic_scan(context.application, task_id)
    await update.message.reply_text(f"Сканирование запущено с ID {task_id}")


async def periodic_scan(app: Application, task_id: str) -> None:
    async def job_fn(ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await process_scan(ctx)
        except Exception:
            log.exception("Periodic scan failed")

    # Запускаем задачу и сохраняем в jobs
    job = app.job_queue.run_repeating(
        job_fn, interval=tg_bot_settings.SCAN_INTERVAL, first=3
    )
    JOBS[task_id] = job


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_scan(context)


async def stop_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task_id = context.args[0] if context.args else None
    if task_id and task_id in JOBS:
        job = JOBS.pop(task_id)
        job.schedule_removal()

        if update.message:
            await update.message.reply_text(f"Сканирование с ID {task_id} остановлено.")
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                f"Сканирование с ID {task_id} остановлено."
            )
    else:
        if update.message:
            await update.message.reply_text(
                "Задача с таким ID не найдена или не запущена."
            )
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                "Задача с таким ID не найдена или не запущена."
            )


async def process_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    for entry in sorted(
        tg_bot_settings.POSTS_ROOT.iterdir(), key=lambda p: p.name.lower()
    ):
        if not is_post_folder(entry):
            continue
        lock = entry / ".lock"
        if lock.exists():
            continue

        meta = parse_meta(entry / "meta.json")
        images = collect_images(entry)

        # 1) Медиа-превью
        await send_media_preview(
            context.application,
            tg_bot_settings.ADMIN_CHAT_ID,
            images,
            caption_trim(meta.get("title") or entry.name),
        )

        # 2) Карточка с метаданными и кнопками
        token = uuid.uuid4().hex[:12]
        TOKENS[token] = str(entry)

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Утвердить и опубликовать", callback_data=f"approve:{token}"
                    )
                ],
                [InlineKeyboardButton("⏭️ Пропустить", callback_data=f"skip:{token}")],
            ]
        )
        await context.application.bot.send_message(
            chat_id=tg_bot_settings.ADMIN_CHAT_ID,
            text=build_preview_text(entry, meta, desc=None),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

        # помечаем как отправленное
        try:
            lock.write_text(token, encoding="utf-8")
        except Exception:
            pass


def is_post_folder(p: Path) -> bool:
    return p.is_dir() and (p / "meta.json").exists()


def parse_meta(meta_path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
    except json.JSONDecodeError as e:
        log.warning(f"Invalid JSON in meta.json at {meta_path}: {e}")
    except Exception as e:
        log.warning(f"Failed to read or parse meta.json at {meta_path}: {e}")
    return meta


async def send_media_preview(
    app: Application, chat_id: int, images: list[Path], caption: str
) -> None:
    if not images:
        await app.bot.send_message(chat_id=chat_id, text=caption or "(без изображений)")
        return

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
            if first and j == 0 and caption:
                media.append(InputMediaPhoto(f, caption=caption))
            else:
                media.append(InputMediaPhoto(f))
        if media:
            await app.bot.send_media_group(chat_id=chat_id, media=media)
        first = False


def caption_trim(text: str | None) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= MAX_CAPTION else text[: MAX_CAPTION - 1] + "…"


def build_preview_text(folder: Path, meta: dict[str, str], desc: str | None) -> str:
    lines = [f"📦 <b>{html_escape(folder.name)}</b>"]

    if meta:
        for k, v in meta.items():
            if isinstance(v, list):
                v = ", ".join(v)
            lines.append(f"<b>{html_escape(k)}:</b> {html_escape(str(v))}")

    if desc:
        short = desc.strip()
        if len(short) > 500:
            short = short[:500] + "…"
        lines += ["", "<b>description.txt</b>:" + html_escape(short)]

    return "\n".join(lines)
