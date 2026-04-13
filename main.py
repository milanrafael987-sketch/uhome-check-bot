import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Бот работает 🚀")


@dp.message()
async def echo(message: Message):
    await message.answer(f"Ты написал: {message.text}")


async def main():
    await dp.start_polling(bot)


if name == "main":
    asyncio.run(main())
