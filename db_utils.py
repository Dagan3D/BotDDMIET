import aiosqlite
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_topics (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS thread_to_user (
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (chat_id, thread_id)
            );
        """)
        await db.commit()
        print("База данных и таблицы успешно инициализированы.")


async def set_active_topic(user_id, chat_id, thread_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO active_topics (user_id, chat_id, thread_id) VALUES (?, ?, ?)",
            (user_id, chat_id, thread_id)
        )
        await db.execute(
            "INSERT OR REPLACE INTO thread_to_user (chat_id, thread_id, user_id) VALUES (?, ?, ?)",
            (chat_id, thread_id, user_id)
        )
        await db.commit()


async def get_active_topic(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT chat_id, thread_id FROM active_topics WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {'chat_id': row[0], 'thread_id': row[1]}
            return None


async def remove_active_topic(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT chat_id, thread_id FROM active_topics WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                chat_id, thread_id = row
                await db.execute("DELETE FROM thread_to_user WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id))
        await db.execute("DELETE FROM active_topics WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_user_by_thread(chat_id, thread_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM thread_to_user WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None


async def remove_thread(chat_id, thread_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM thread_to_user WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id))
        await db.commit()
