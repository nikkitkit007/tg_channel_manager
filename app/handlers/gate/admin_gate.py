from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from config.settings import settings
tg_bot_settings = settings.TGBOT


async def admin_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or user.id != tg_bot_settings.ADMIN_CHAT_ID:
        cq = getattr(update, "callback_query", None)
        if cq:
            await cq.answer("Доступ только для администратора", show_alert=False)
        elif update.message:
            await update.message.reply_text("Этот бот приватный. Доступ только у администратора.")
        raise ApplicationHandlerStop()
