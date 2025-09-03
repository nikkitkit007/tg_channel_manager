from core.utils import _html_escape

from core.utils import _html_escape
from main import TOKENS, MEDIA_GROUP_LIMIT, MAX_CAPTION

from __future__ import annotations

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
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config.logger import get_logger
from schemas.enums import IMAGE_EXTS
log = get_logger(__name__)

tg_bot_settings = settings.TGBOT

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and update.effective_user.id != tg_bot_settings.ADMIN_CHAT_ID:
        await update.effective_chat.send_message("Этот бот — приватный. Доступ только у администратора.")
        return
    await update.effective_chat.send_message(
        "Привет! Я слежу за папкой и отправляю посты на утверждение."
        "Команды:• /scan — проверить папку сейчас"
        f"• Папка: <code>{_html_escape(str(tg_bot_settings.POSTS_ROOT))}</code>"
        f"• Интервал сканирования: {tg_bot_settings.SCAN_INTERVAL} сек.",
        parse_mode=ParseMode.HTML,
    )