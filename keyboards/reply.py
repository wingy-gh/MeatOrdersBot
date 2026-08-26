"""Reply-клавиатуры главного меню."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from config import ADMIN_ID

BTN_ORDER = "🥩 Сделать заказ"
BTN_QUESTION = "❓ Задать вопрос"
BTN_PRICES = "📋 Прайсы"
BTN_MENU = "🍽 Меню"
BTN_CANCEL_BOOKING = "❌ Отменить запись"
BTN_ADMIN = "🛠 Админ-панель"
BTN_SHARE_PHONE = "📱 Отправить телефон"
BTN_MAIN = "⬅️ В меню"


def main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_ORDER), KeyboardButton(text=BTN_QUESTION)],
        [KeyboardButton(text=BTN_PRICES), KeyboardButton(text=BTN_MENU)],
        [KeyboardButton(text=BTN_CANCEL_BOOKING)],
    ]
    if user_id == ADMIN_ID:
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SHARE_PHONE, request_contact=True)],
            [KeyboardButton(text=BTN_MAIN)],
        ],
        resize_keyboard=True,
    )


def cancel_to_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_MAIN)]],
        resize_keyboard=True,
    )
