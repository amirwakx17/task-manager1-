from __future__ import annotations

import asyncio
import html
import hmac
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEB_ACCESS_KEY = os.getenv("WEB_ACCESS_KEY", "").strip()
WEB_USER_ID = int(os.getenv("WEB_USER_ID", "0"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "./data/tasks.db"))
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def connect_db() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def db_connection():
    connection = connect_db()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    with db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_tasks_owner ON tasks(owner_id, id)"
        )


def task_json(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
        "created_at": row["created_at"],
    }


def add_task(owner_id: int, title: str) -> dict:
    with db_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (owner_id, title, created_at) VALUES (?, ?, ?)",
            (owner_id, title, int(time.time())),
        )
        row = connection.execute(
            "SELECT id, title, done, created_at FROM tasks WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return task_json(row)


def get_tasks(owner_id: int) -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, done, created_at FROM tasks
            WHERE owner_id = ? ORDER BY done, id DESC
            """,
            (owner_id,),
        ).fetchall()
    return [task_json(row) for row in rows]


def set_task_done(owner_id: int, task_id: int, done: bool) -> dict | None:
    with db_connection() as connection:
        result = connection.execute(
            "UPDATE tasks SET done = ? WHERE id = ? AND owner_id = ?",
            (int(done), task_id, owner_id),
        )
        if result.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT id, title, done, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return task_json(row)


def remove_task(owner_id: int, task_id: int) -> bool:
    with db_connection() as connection:
        result = connection.execute(
            "DELETE FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )
    return result.rowcount > 0


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TaskUpdate(BaseModel):
    done: bool


def require_web_access(
    x_access_key: str = Header(default="", alias="X-Access-Key"),
) -> int:
    if WEB_USER_ID <= 0:
        raise HTTPException(status_code=503, detail="Veb foydalanuvchisi sozlanmagan")
    if not WEB_ACCESS_KEY:
        raise HTTPException(status_code=503, detail="Veb-kirish kaliti sozlanmagan")
    if not hmac.compare_digest(x_access_key, WEB_ACCESS_KEY):
        raise HTTPException(status_code=401, detail="Kirish kaliti noto'g'ri")
    return WEB_USER_ID


def task_keyboard(owner_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for task in get_tasks(owner_id):
        if task["done"]:
            continue
        builder.button(
            text=f"✅ {task['title'][:35]}",
            callback_data=f"done:{task['id']}",
        )
        builder.button(
            text=f"🗑 {task['title'][:25]}",
            callback_data=f"delete:{task['id']}",
        )
    builder.adjust(1, 1)
    return builder


def task_message(owner_id: int) -> str:
    tasks = get_tasks(owner_id)
    if not tasks:
        return "📋 <b>Vazifalar ro'yxati bo'sh.</b>\n/add vazifa nomi"
    lines = ["📋 <b>Vazifalaringiz:</b>", ""]
    for index, task in enumerate(tasks, start=1):
        mark = "✅" if task["done"] else "▫️"
        lines.append(f"{index}. {mark} {html.escape(task['title'])}")
    lines.extend(["", "/add vazifa nomi — yangi vazifa qo'shish"])
    return "\n".join(lines)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.bot = None
    polling_task: asyncio.Task | None = None

    if BOT_TOKEN:
        bot = Bot(
            BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dispatcher = Dispatcher()

        @dispatcher.message(CommandStart())
        async def start(message: Message) -> None:
            await message.answer(
                "Salom! Vazifalarni boshqarish uchun:\n"
                "/add vazifa nomi — vazifa qo'shish\n"
                "/tasks — ro'yxatni ko'rish\n"
                "/help — yordam"
            )

        @dispatcher.message(Command("help"))
        async def help_command(message: Message) -> None:
            await message.answer(
                "/add vazifa nomi — yangi vazifa\n"
                "/tasks — vazifalarni ko'rish\n"
                "Ro'yxatdagi tugmalar orqali vazifani bajarilgan deb belgilang yoki o'chiring."
            )

        @dispatcher.message(Command("add"))
        async def add_command(message: Message) -> None:
            title = (message.text or "").partition(" ")[2].strip()
            if not title:
                await message.answer("Masalan: <code>/add Hisobotni topshirish</code>")
                return
            if len(title) > 200:
                await message.answer("Vazifa nomi 200 belgidan oshmasin.")
                return
            add_task(message.from_user.id, title)
            await message.answer(
                "✅ Vazifa qo'shildi.\n\n" + task_message(message.from_user.id)
            )

        @dispatcher.message(Command("tasks"))
        async def tasks_command(message: Message) -> None:
            owner_id = message.from_user.id
            await message.answer(
                task_message(owner_id),
                reply_markup=task_keyboard(owner_id).as_markup(),
            )

        @dispatcher.callback_query(F.data.startswith("done:"))
        async def done_callback(callback: CallbackQuery) -> None:
            task_id = int((callback.data or "").split(":", 1)[1])
            task = set_task_done(callback.from_user.id, task_id, True)
            if task is None:
                await callback.answer("Vazifa topilmadi", show_alert=True)
                return
            await callback.message.edit_text(
                task_message(callback.from_user.id),
                reply_markup=task_keyboard(callback.from_user.id).as_markup(),
            )
            await callback.answer("Bajarildi ✅")

        @dispatcher.callback_query(F.data.startswith("delete:"))
        async def delete_callback(callback: CallbackQuery) -> None:
            task_id = int((callback.data or "").split(":", 1)[1])
            if not remove_task(callback.from_user.id, task_id):
                await callback.answer("Vazifa topilmadi", show_alert=True)
                return
            await callback.message.edit_text(
                task_message(callback.from_user.id),
                reply_markup=task_keyboard(callback.from_user.id).as_markup(),
            )
            await callback.answer("O'chirildi")

        app.state.bot = bot
        polling_task = asyncio.create_task(dispatcher.start_polling(bot))
        logger.info("Task Manager bot polling boshlandi")
    else:
        logger.warning("BOT_TOKEN sozlanmagan — Telegram bot polling o'chirilgan")

    yield

    if polling_task is not None:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    if app.state.bot is not None:
        await app.state.bot.session.close()


app = FastAPI(title="Task Manager", lifespan=lifespan)
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Access-Key"],
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "bot_running": app.state.bot is not None}


@app.get("/api/tasks")
def web_list_tasks(owner_id: int = Depends(require_web_access)) -> list[dict]:
    return get_tasks(owner_id)


@app.post("/api/tasks")
def web_add_task(
    payload: TaskCreate,
    owner_id: int = Depends(require_web_access),
) -> dict:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Vazifa nomi bo'sh bo'lmasin")
    return add_task(owner_id, title)


@app.patch("/api/tasks/{task_id}")
def web_update_task(
    task_id: int,
    payload: TaskUpdate,
    owner_id: int = Depends(require_web_access),
) -> dict:
    task = set_task_done(owner_id, task_id, payload.done)
    if task is None:
        raise HTTPException(status_code=404, detail="Vazifa topilmadi")
    return task


@app.delete("/api/tasks/{task_id}")
def web_delete_task(
    task_id: int,
    owner_id: int = Depends(require_web_access),
) -> dict:
    if not remove_task(owner_id, task_id):
        raise HTTPException(status_code=404, detail="Vazifa topilmadi")
    return {"ok": True}
