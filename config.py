# config.py
# Все основные настройки и параметры для бота
import os
from dotenv import load_dotenv
load_dotenv()
API_TOKEN = os.getenv('BOT_API_TOKEN')
DB_PATH = "./botddmiet.sqlite"

SPECIALIST_GROUPS = {
    'tech': {
        'name': "Техническая поддержка",
        'chat_id': -1002819516033
    },
    'billing': {
        'name': "Учебный процесс и расписание",
        'chat_id': -1002859896950
    },
    'other': {
        'name': "Другое",
        'chat_id': -1002523367329
    }
}
