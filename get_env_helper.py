import asyncio

from telegram import Bot

bot = Bot(token="1111111111111")  # Заменить на свой токен
updates = asyncio.run(bot.get_updates())  # Написать боту /start
print("ADMIN_CHAT_ID", updates[0].message.chat.id)

chat = asyncio.run(
    bot.get_chat("@the_best_postcards")
)  # Заменить на имя канала или его ID
print("CHANNEL_ID", chat.id)
