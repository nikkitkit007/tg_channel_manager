from __future__ import annotations

from core.utils import html_escape, collect_images
from storages.publication import TOKENS
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


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        update.effective_user
        and update.effective_user.id != tg_bot_settings.ADMIN_CHAT_ID
    ):
        return
    await process_scan(context)


async def process_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    for entry in sorted(
        tg_bot_settings.POSTS_ROOT.iterdir(), key=lambda p: p.name.lower()
    ):
        if not is_post_folder(entry):
            continue
        lock = entry / ".lock"
        if lock.exists():
            continue  # уже отправляли на утверждение

        meta = parse_meta(entry / "meta.txt")
        desc_path = entry / "description.txt"
        desc = (
            desc_path.read_text("utf-8", errors="replace").strip()
            if desc_path.exists()
            else None
        )
        images = collect_images(entry)

        # 1) Медиа-превью
        await send_media_preview(
            context.application,
            tg_bot_settings.ADMIN_CHAT_ID,
            images,
            caption_trim(desc or entry.name),
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
            text=build_preview_text(entry, meta, desc),
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
    return p.is_dir() and (p / "meta.txt").exists()


def parse_meta(meta_path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    try:
        for line in meta_path.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                k, v = line.split(":", 1)
            elif "=" in line:
                k, v = line.split("=", 1)
            else:
                k, v = "info", line
            meta[k.strip().lower()] = v.strip()
    except Exception as e:
        log.warning("Failed to read meta at %s: %s", meta_path, e)
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
            lines.append(f"<b>{html_escape(k)}:</b> {html_escape(v)}")
    if desc:
        short = desc.strip()
        if len(short) > 500:
            short = short[:500] + "…"
        lines += ["", "<b>description.txt</b>:" + html_escape(short)]
    return "".join(lines)
