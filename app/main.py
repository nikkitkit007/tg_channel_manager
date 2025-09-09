from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters, TypeHandler,
)

from config.logger import get_logger
from config.settings import settings
from core.channel.publisher import on_callback, on_schedule_text, restore_scheduled
from core.utils import create_path_if_not_exists
from handlers.gate.admin_gate import admin_gate
from handlers.help.help import help_command
from handlers.scan.scan import (
    scan_command,
    stop_scan_command,
    start_scan_command,
)
from handlers.start.start import start_command
from handlers.store.delay_posts import list_jobs_command, view_job_command

log = get_logger(__name__)

tg_bot_settings = settings.TGBOT


async def _post_init(app: Application) -> None:
    await restore_scheduled(app)

    log.info(
        "Bot started",
        extras={
            "posts_root": tg_bot_settings.POSTS_ROOT,
            "scan_interval": tg_bot_settings.SCAN_INTERVAL,
        },
    )


def main() -> None:
    create_path_if_not_exists(tg_bot_settings.POSTS_ROOT)

    application = (
        Application.builder()
        .token(tg_bot_settings.BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )
    application.add_handler(TypeHandler(Update, admin_gate), group=-1)

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("start_scan", start_scan_command))
    application.add_handler(CommandHandler("stop_scan", stop_scan_command))
    application.add_handler(CommandHandler("view_jobs", list_jobs_command))
    application.add_handler(CommandHandler("view_job", view_job_command))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & filters.User(user_id=tg_bot_settings.ADMIN_CHAT_ID),
            on_schedule_text,
        )
    )
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
