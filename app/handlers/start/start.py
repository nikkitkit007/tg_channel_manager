from __future__ import annotations

from core.utils import html_escape

from app.config.settings import settings
from telegram import (
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
)

from config.logger import get_logger

log = get_logger(__name__)

tg_bot_settings = settings.TGBOT


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        update.effective_user
        and update.effective_user.id != tg_bot_settings.ADMIN_CHAT_ID
    ):
        await update.effective_chat.send_message(
            "Этот бот — приватный. Доступ только у администратора."
        )
        return
    await update.effective_chat.send_message(
        "Привет! Я слежу за папкой и отправляю посты на утверждение."
        "Команды:• /scan — проверить папку сейчас"
        f"• Папка: <code>{html_escape(str(tg_bot_settings.POSTS_ROOT))}</code>"
        f"• Интервал сканирования: {tg_bot_settings.SCAN_INTERVAL} сек.",
        parse_mode=ParseMode.HTML,
    )
