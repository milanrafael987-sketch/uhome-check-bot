import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
from rapidfuzz import fuzz

import os
API_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DB = "checklists.db"

STATUSES = ["⚪", "✅", "❌", "⚠️"]

# ---------------- DB ----------------

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS checklists (
            id INTEGER PRIMARY KEY,
            source_chat_id INTEGER,
            source_msg_id INTEGER,
            checklist_msg_id INTEGER,
            title TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            checklist_id INTEGER,
            text TEXT,
            status INTEGER,
            user TEXT
        )
        """)
        await db.commit()

# ---------------- PARSER ----------------

def parse_source(text):
    lines = text.split("\n")
    title = lines[0].replace("!!!", "").strip()
    items = []

    for line in lines[1:]:
        if line.strip().startswith("-"):
            items.append(line.strip()[1:].strip())

    return title, items

# ---------------- FORMAT ----------------

def format_checklist(title, items):
    text = f"{title}\n\n"
    for item in items:
        status = STATUSES[item["status"]]
        user = f" ✔ {item['user']}" if item["user"] else ""
        text += f"{status} {item['text']}{user}\n"
    return text

def build_kb(checklist_id, items):
    kb = InlineKeyboardMarkup()
    for idx, _ in enumerate(items):
        kb.add(
            InlineKeyboardButton(
                text="toggle",
                callback_data=f"{checklist_id}:{idx}"
            )
        )
    return kb

# ---------------- CREATE ----------------

@dp.message()
async def create_checklist(message: types.Message):
    if not message.text.startswith("!!!"):
        return

    title, parsed_items = parse_source(message.text)

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "INSERT INTO checklists (source_chat_id, source_msg_id, title) VALUES (?, ?, ?)",
            (message.chat.id, message.message_id, title)
        )
        checklist_id = cursor.lastrowid

        items = []
        for text in parsed_items:
            items.append({"text": text, "status": 0, "user": ""})
            await db.execute(
                "INSERT INTO items (checklist_id, text, status, user) VALUES (?, ?, 0, '')",
                (checklist_id, text)
            )

        await db.commit()

    text = format_checklist(title, items)
    sent = await message.answer(text, reply_markup=build_kb(checklist_id, items))

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE checklists SET checklist_msg_id=? WHERE id=?",
            (sent.message_id, checklist_id)
        )
        await db.commit()

# ---------------- TOGGLE ----------------

@dp.callback_query()
async def toggle(callback: types.CallbackQuery):
    checklist_id, idx = map(int, callback.data.split(":"))
    user = callback.from_user.first_name

    async with aiosqlite.connect(DB) as db:
        rows = await db.execute_fetchall(
            "SELECT id, text, status FROM items WHERE checklist_id=?",
            (checklist_id,)
        )

        item_id, text, status = rows[idx]
        new_status = (status + 1) % 4

        await db.execute(
            "UPDATE items SET status=?, user=? WHERE id=?",
            (new_status, user, item_id)
        )

        updated = await db.execute_fetchall(
            "SELECT text, status, user FROM items WHERE checklist_id=?",
            (checklist_id,)
        )

        checklist = await db.execute_fetchone(
            "SELECT title, checklist_msg_id FROM checklists WHERE id=?",
            (checklist_id,)
        )

        await db.commit()
items = [{"text": t, "status": s, "user": u} for t, s, u in updated]
text = format_checklist(checklist[0], items)

    await bot.edit_message_text(
        text,
        chat_id=callback.message.chat.id,
        message_id=checklist[1],
        reply_markup=build_kb(checklist_id, items)
    )

    await callback.answer()

# ---------------- EDIT SOURCE ----------------

@dp.edited_message()
async def update_from_edit(message: types.Message):
    if not message.text.startswith("!!!"):
        return

    title, new_items = parse_source(message.text)

    async with aiosqlite.connect(DB) as db:
        checklist = await db.execute_fetchone(
            "SELECT id, checklist_msg_id FROM checklists WHERE source_msg_id=?",
            (message.message_id,)
        )
        if not checklist:
            return

        checklist_id, checklist_msg_id = checklist

        old_items = await db.execute_fetchall(
            "SELECT text, status, user FROM items WHERE checklist_id=?",
            (checklist_id,)
        )

        result_items = []

        for new_text in new_items:
            best = None
            best_score = 0

            for old_text, status, user in old_items:
                score = fuzz.ratio(new_text, old_text)
                if score > best_score:
                    best_score = score
                    best = (status, user)

            if best_score > 70:
                result_items.append({"text": new_text, "status": best[0], "user": best[1]})
            else:
                result_items.append({"text": new_text, "status": 0, "user": ""})

        await db.execute("DELETE FROM items WHERE checklist_id=?", (checklist_id,))

        for item in result_items:
            await db.execute(
                "INSERT INTO items (checklist_id, text, status, user) VALUES (?, ?, ?, ?)",
                (checklist_id, item["text"], item["status"], item["user"])
            )

        await db.commit()

    text = format_checklist(title, result_items)

    await bot.edit_message_text(
        text,
        chat_id=message.chat.id,
        message_id=checklist_msg_id,
        reply_markup=build_kb(checklist_id, result_items)
    )

# ---------------- RUN ----------------

async def main():
    await init_db()
    await dp.start_polling(bot)

if name == "main":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
