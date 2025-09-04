from __future__ import annotations

import re
import shutil
from pathlib import Path
from app.config.settings import settings
from telegram import (
    Update,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config.logger import get_logger
from config.settings import MEDIA_GROUP_LIMIT
from core.utils import collect_images, create_path_if_not_exists
from handlers.scan.scan import (
    scan_command,
    caption_trim,
    stop_scan_command,
    start_scan_command,
)
from handlers.start.start import start_command
from storages.publication import TOKENS

log = get_logger(__name__)

tg_bot_settings = settings.TGBOT


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    cq = update.callback_query

    if (
        update.effective_user
        and update.effective_user.id != tg_bot_settings.ADMIN_CHAT_ID
    ):
        await cq.answer("Недостаточно прав")
        return

    data = cq.data or ""
    m = re.match(r"^(approve|skip):([a-f0-9]{12})$", data)
    if not m:
        await cq.answer("Неизвестное действие")
        return

    action, token = m.group(1), m.group(2)
    folder_str = TOKENS.get(token)
    if not folder_str:
        await cq.answer("Кнопка устарела — перезапусти /scan")
        return

    folder = Path(folder_str)
    if not folder.exists():
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

    await cq.answer("Публикую…")

    desc_path = folder / "description.txt"
    desc = (
        desc_path.read_text("utf-8", errors="replace").strip()
        if desc_path.exists()
        else None
    )
    images = collect_images(folder)

    try:
        await publish_to_channel(
            context.application,
            tg_bot_settings.CHANNEL_ID,
            images,
            caption_trim(desc or folder.name),
        )
    except Exception as e:
        log.exception("Publish failed: %s", e)
        await cq.edit_message_text(f"❌ Ошибка публикации: {e}")
        return

    try:
        shutil.rmtree(folder)
    except Exception as e:
        log.error("Failed to delete %s: %s", folder, e)
        await cq.edit_message_text(f"✅ Опубликовано, но не удалено: {e}")
    else:
        await cq.edit_message_text("✅ Опубликовано и удалено: " + folder.name)

    TOKENS.pop(token, None)


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
                if first and j == 0 and caption:
                    media.append(InputMediaPhoto(f, caption=caption))
                else:
                    media.append(InputMediaPhoto(f))
            if media:
                await app.bot.send_media_group(chat_id=channel, media=media)
            first = False
    else:
        await app.bot.send_message(chat_id=channel, text=caption or "")


async def _post_init(app: Application) -> None:
    # await periodic_scan(app)
    log.info(
        f"Bot started. Watching {tg_bot_settings.POSTS_ROOT} every {tg_bot_settings.SCAN_INTERVAL}"
    )


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
