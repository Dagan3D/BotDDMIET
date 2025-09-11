
# --- Обработчик команды /close для пользователя ---
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from aiogram import Bot, Dispatcher, types, F
import logging
import asyncio
from db_utils import (
    init_db,
    set_active_topic,
    get_active_topic,
    remove_active_topic,
    get_user_by_thread,
    remove_thread
)

from config import API_TOKEN, SPECIALIST_GROUPS
import localization
MESSAGES = localization.MESSAGES_RU
TOPIC_NAMES = localization.TOPIC_NAMES_RU

# --- Состояния FSM ---
class Support(StatesGroup):
    waiting_for_topic = State()
    waiting_for_question = State()
    in_active_chat = State()  # <-- Наше новое состояние


# --- Настройка ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# --- Клавиатуры ---
def get_topics_keyboard():
    buttons = [
        [InlineKeyboardButton(text=TOPIC_NAMES[key], callback_data=key)]
        for key, details in SPECIALIST_GROUPS.items()
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# --- Хендлеры ---


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    active_topic = await get_active_topic(message.from_user.id)
    if active_topic:
        await message.answer(MESSAGES["active_topic_exists"])
        return
    await state.clear()
    await message.answer(MESSAGES["start"], reply_markup=get_topics_keyboard())
    await state.set_state(Support.waiting_for_topic)


@dp.message(Command("stop"))
async def user_close_ticket(message: types.Message, state: FSMContext):
    active_topic = await get_active_topic(message.from_user.id)
    if not active_topic:
        await message.answer(MESSAGES["no_active_ticket"])
        return
    await remove_active_topic(message.from_user.id)
    await state.clear()
    await message.answer(MESSAGES["ticket_closed_user"])
    try:
        await bot.send_message(
            chat_id=active_topic['chat_id'],
            text=MESSAGES["ticket_closed_notify"],
            message_thread_id=active_topic['thread_id']
        )
    except TelegramBadRequest as e:
        logging.error(f"Не удалось отправить уведомление о закрытии: {e}")
    try:
        await bot.close_forum_topic(
            chat_id=active_topic['chat_id'],
            message_thread_id=active_topic['thread_id']
        )
    except TelegramBadRequest as e:
        logging.error(f"Не удалось закрыть тему: {e}")


@dp.callback_query(Support.waiting_for_topic)
async def process_topic_choice(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(topic_key=callback.data)
    topic_name = SPECIALIST_GROUPS.get(callback.data, {}).get('name')

    await callback.message.edit_text(
        f"{MESSAGES['you_selected']} «{TOPIC_NAMES[callback.data]}».\n\n{MESSAGES['describe_problem']}"
    )
    await state.set_state(Support.waiting_for_question)
    await callback.answer()


@dp.message(Support.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    topic_key = user_data.get('topic_key')
    target_group_info = SPECIALIST_GROUPS.get(topic_key)

    if not target_group_info:
        await message.answer(MESSAGES["error_topic"])
        return

    target_chat_id = target_group_info['chat_id']
    topic_name = f"Обращение от @{message.from_user.username or message.from_user.first_name}"

    try:
        new_topic = await bot.create_forum_topic(chat_id=target_chat_id, name=topic_name)
        topic_id = new_topic.message_thread_id
        await set_active_topic(message.from_user.id, target_chat_id, topic_id)
        await message.answer(MESSAGES["question_sent"])
        await bot.forward_message(
            chat_id=target_chat_id, from_chat_id=message.chat.id,
            message_id=message.message_id, message_thread_id=topic_id
        )
        await state.set_state(Support.in_active_chat)
    except Exception as e:
        logging.error(f"Ошибка при создании темы: {e}")
        await message.answer(MESSAGES["error_create_topic"])
        await state.clear()


@dp.message(Command("close"), F.chat.type.in_({'supergroup'}))
async def close_ticket(message: types.Message, state: FSMContext):
    """Команда для специалиста, чтобы закрыть обращение."""
    if not message.message_thread_id:
        await message.reply(MESSAGES["close_command_in_thread"])
        return

    lookup_key = (message.chat.id, message.message_thread_id)
    user_id_to_notify = await get_user_by_thread(message.chat.id, message.message_thread_id)

    if user_id_to_notify:
        await remove_thread(message.chat.id, message.message_thread_id)
        await remove_active_topic(user_id_to_notify)
        # Уведомляем пользователя
        try:
            await bot.send_message(user_id_to_notify, MESSAGES["ticket_closed_specialist"])
        except TelegramBadRequest:
            # Пользователь мог заблокировать бота
            logging.warning(
                f"Не удалось уведомить пользователя {user_id_to_notify} о закрытии тикета.")

        await message.reply("Обращение закрыто. Пользователь уведомлен.")

        # Красивый бонус: закрываем саму тему в Telegram
        try:
            await bot.close_forum_topic(
                chat_id=lookup_key[0],
                message_thread_id=lookup_key[1]
            )
        except TelegramBadRequest as e:
            logging.error(f"Не удалось закрыть тему: {e}")

    else:
        await message.reply(MESSAGES["no_user_for_thread"])


# Обработчик ответов специалиста остается почти таким же
@dp.message(F.chat.type.in_({'supergroup'}))
async def handle_specialist_reply(message: types.Message):
    if message.text and message.text.startswith('/'):
        return  # Игнорируем команды

    if message.message_thread_id and not message.from_user.is_bot:
        user_id_to_reply = await get_user_by_thread(message.chat.id, message.message_thread_id)
        if user_id_to_reply:
            await bot.copy_message(chat_id=user_id_to_reply, from_chat_id=message.chat.id, message_id=message.message_id)


@dp.message()
async def forward_to_specialist(message: types.Message, state: FSMContext):
    """Ловит все последующие сообщения пользователя и пересылает в его тему."""
    active_topic = await get_active_topic(message.from_user.id)
    if active_topic:
        await bot.forward_message(
            chat_id=active_topic['chat_id'],
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=active_topic['thread_id']
        )
    else:
        # Если по какой-то причине нет активной темы, предлагаем начать заново
        await message.answer(MESSAGES["closed_previous_ticket"])
        await state.clear()


async def main():
    print("Бот запущен...")
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
