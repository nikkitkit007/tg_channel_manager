from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.settings import settings, TZ

tg_bot_settings = settings.TGBOT

HELP_TEXT = (
    "<b>Помощь</b>\n\n"
    "Этот бот публикует посты из локальной директории в канал через предпросмотр и утверждение.\n\n"
    "<b>Структура поста</b>\n"
    "• Папка-пост с файлами изображений\n"
    "• <code>meta.json</code> — обязательный (метаданные, JSON)\n"
    "• <code>description.txt</code> — опционально (подпись)\n\n"
    "<b>Команды</b>\n"
    "• <code>/start</code> — приветствие\n"
    "• <code>/scan</code> — разово просканировать папку\n"
    "• <code>/start_scan</code> — запустить периодическое сканирование (вернёт task_id)\n"
    "• <code>/stop_scan &lt;task_id&gt;</code> — остановить периодическое сканирование\n"
    "• <code>/view_jobs</code> — показать запланированные публикации (job_id и время)\n"
    "• <code>/view_job &lt;job_id&gt;</code> — открыть превью конкретной публикации + плановая дата\n"
    "• <code>/help</code> — эта справка\n\n"
    "<b>Утверждение и расписание</b>\n"
    "После предпросмотра жми «✅ Утвердить…» → выбери «Сейчас» или «Запланировать».\n"
    "Для ручного ввода даты используй формат <code>YYYY-MM-DD HH:MM</code> "
    f"(локальное время, TZ: <code>{TZ}</code>).\n\n"
    "<b>Важно</b>\n"
    "• Бот должен быть админом канала с правом публикации.\n"
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=HELP_TEXT,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
