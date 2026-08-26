"""Загрузка настроек бота из .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта (рядом с bot.py)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow").strip()

# SQLite-файл
DB_PATH = BASE_DIR / "data" / "bot.db"

# Горизонт записи: 1 месяц вперёд
SCHEDULE_DAYS = 30

# Слоты, которые создаются вместе с новым рабочим днём (админ может удалить/добавить)
DEFAULT_SLOTS = [
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
]

# Кнопка «Прайсы» — HTML без FSM, правьте текст под себя
PRICES_HTML = (
    "<b>📋 Прайс на продукцию</b>\n\n"
    "<b>Говядина</b>\n"
    "• Вырезка — <code>1200</code> ₽/кг\n"
    "• Ошеек — <code>890</code> ₽/кг\n"
    "• Фарш — <code>650</code> ₽/кг\n\n"
    "<b>Свинина</b>\n"
    "• Корейка — <code>720</code> ₽/кг\n"
    "• Шея — <code>680</code> ₽/кг\n"
    "• Ребра — <code>540</code> ₽/кг\n\n"
    "<b>Птица</b>\n"
    "• Филе курицы — <code>420</code> ₽/кг\n"
    "• Бедро — <code>380</code> ₽/кг\n\n"
    "<i>Точные позиции и наличие смотрите в «Меню» "
    "и при оформлении заказа на выбранную дату.</i>"
)


def validate_config() -> None:
    """Проверка обязательных переменных перед запуском."""
    if not BOT_TOKEN or BOT_TOKEN == "ВАШ_ТОКЕН_ОТ_BOTFATHER":
        raise RuntimeError("Укажите BOT_TOKEN в файле .env")
    if ADMIN_ID <= 0:
        raise RuntimeError("Укажите числовой ADMIN_ID в файле .env (узнать: @userinfobot)")
