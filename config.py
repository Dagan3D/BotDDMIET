import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('BOT_API_TOKEN')

# Настройки базы данных PostgreSQL
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DB_NAME = os.getenv('POSTGRES_DB', 'bot_db')
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = os.getenv('DB_PORT', '5432')

PG_DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Функция для безопасного получения ID группы
def get_chat_id(env_key):
    try:
        val = os.getenv(env_key)
        if not val:
            return None
        return int(val)
    except (ValueError, TypeError):
        return None

# Словарь групп. Если ID не найден в .env, будет None.
SPECIALIST_GROUPS = {
    'tech': {
        'name': "Техническая поддержка",
        'chat_id': get_chat_id('GROUP_TECH_ID')
    },
    'billing': {
        'name': "Учебный процесс и расписание",
        'chat_id': get_chat_id('GROUP_BILLING_ID')
    },
    'other': {
        'name': "Другое",
        'chat_id': get_chat_id('GROUP_OTHER_ID')
    }
}