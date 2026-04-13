import logging
import os

from aiogram import Bot, Dispatcher, executor, types

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Бот работает 🚀")


@dp.message_handler()
async def echo(message: types.Message):
    await message.reply(f"Ты написал: {message.text}")


if name == "main":
    executor.start_polling(dp, skip_updates=True)
