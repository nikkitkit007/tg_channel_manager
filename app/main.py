from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
)

from config.logger import get_logger
from core.channel.publisher import tg_bot_settings, on_callback
from core.utils import create_path_if_not_exists
from handlers.scan.scan import (
    scan_command,
    stop_scan_command,
    start_scan_command,
)
from handlers.start.start import start_command

log = get_logger(__name__)


async def _post_init(app: Application) -> None:
    log.info("Bot started",
             extras={"posts_root": tg_bot_settings.POSTS_ROOT, "scan_interval": tg_bot_settings.SCAN_INTERVAL})


def main() -> None:
    create_path_if_not_exists(tg_bot_settings.POSTS_ROOT)

    application = (
        Application.builder()
        .token(tg_bot_settings.BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("start_scan", start_scan_command))
    application.add_handler(CommandHandler("stop_scan", stop_scan_command))
    application.add_handler(CallbackQueryHandler(on_callback))

    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
