import asyncpg
from config import PG_DSN

async def get_pool():
    # Создаем пул соединений. Это эффективнее, чем открывать соединение каждый раз.
    return await asyncpg.create_pool(dsn=PG_DSN)

# Глобальная переменная для пула (инициализируется при старте)
pool = None

async def init_db():
    global pool
    pool = await get_pool()
    
    async with pool.acquire() as connection:
        # В Postgres лучше использовать BIGINT для ID телеграма, так как они могут превышать диапазон обычного INTEGER
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS active_topics (
                user_id BIGINT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                thread_id INTEGER NOT NULL
            );
        """)
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS thread_to_user (
                chat_id BIGINT NOT NULL,
                thread_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                PRIMARY KEY (chat_id, thread_id)
            );
        """)
        print("База данных PostgreSQL подключена и таблицы проверены.")

async def set_active_topic(user_id, chat_id, thread_id):
    async with pool.acquire() as connection:
        # Синтаксис UPSERT в Postgres (ON CONFLICT)
        await connection.execute(
            """
            INSERT INTO active_topics (user_id, chat_id, thread_id) 
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE 
            SET chat_id = EXCLUDED.chat_id, thread_id = EXCLUDED.thread_id
            """,
            user_id, chat_id, thread_id
        )
        
        await connection.execute(
            """
            INSERT INTO thread_to_user (chat_id, thread_id, user_id) 
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id, thread_id) DO UPDATE 
            SET user_id = EXCLUDED.user_id
            """,
            chat_id, thread_id, user_id
        )

async def get_active_topic(user_id):
    async with pool.acquire() as connection:
        row = await connection.fetchrow("SELECT chat_id, thread_id FROM active_topics WHERE user_id = $1", user_id)
        if row:
            return {'chat_id': row['chat_id'], 'thread_id': row['thread_id']}
        return None

async def remove_active_topic(user_id):
    async with pool.acquire() as connection:
        # Используем транзакцию для атомарности
        async with connection.transaction():
            row = await connection.fetchrow("SELECT chat_id, thread_id FROM active_topics WHERE user_id = $1", user_id)
            if row:
                chat_id = row['chat_id']
                thread_id = row['thread_id']
                await connection.execute("DELETE FROM thread_to_user WHERE chat_id = $1 AND thread_id = $2", chat_id, thread_id)
            
            await connection.execute("DELETE FROM active_topics WHERE user_id = $1", user_id)

async def get_user_by_thread(chat_id, thread_id):
    async with pool.acquire() as connection:
        val = await connection.fetchval("SELECT user_id FROM thread_to_user WHERE chat_id = $1 AND thread_id = $2", chat_id, thread_id)
        return val

async def remove_thread(chat_id, thread_id):
    async with pool.acquire() as connection:
        await connection.execute("DELETE FROM thread_to_user WHERE chat_id = $1 AND thread_id = $2", chat_id, thread_id)
        
# Важно: нужно будет корректно закрыть пул при остановке бота, но для простоты
# пока оставим так. aiogram позволяет регистрировать shutdown callback.