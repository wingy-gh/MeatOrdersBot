# Бот заказов мяса (Telegram + aiogram 3 + SQLite)

Бот для приёма заказов: календарь на месяц, меню на дату, слоты выдачи, админ-панель и напоминания за 24 часа.

## Структура проекта

```
MeatOrdersBot/
├── bot.py                 # запуск polling
├── config.py              # настройки и HTML прайса
├── .env                   # токен и ADMIN_ID (не коммитить)
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── data/                  # создаётся автоматически, bot.db
├── database/
│   └── db.py              # SQLite (aiosqlite)
├── handlers/
│   ├── user.py            # заказ, прайсы, меню, отмена
│   ├── questions.py       # вопрос админу
│   └── admin.py           # админ-панель
├── keyboards/
│   ├── reply.py
│   ├── inline.py
│   └── calendar.py
├── states/
│   └── fsm.py
├── scheduler/
│   └── reminders.py       # APScheduler
├── filters/
│   └── admin.py
└── utils/
    └── formatters.py
```

## Установка и запуск

1. Установите **Python 3.10+**.
2. Создайте виртуальное окружение и зависимости:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux / macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

3. Откройте `.env` и укажите:

- `BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
- `ADMIN_ID` — ваш числовой Telegram ID ([@userinfobot](https://t.me/userinfobot))
- `TIMEZONE` — часовой пояс, по умолчанию `Europe/Moscow`

4. Текст кнопки **Прайсы** правьте в `config.py` (`PRICES_HTML`).

5. Запуск:

```bash
python bot.py
```

## Как пользоваться

**Клиент:** «Сделать заказ» → дата → мясо → время → имя → телефон → подтверждение. Одновременно только одна активная запись. «Отменить запись» освобождает слот. «Задать вопрос» — текст уходит админу. «Прайсы» и «Меню» — без FSM.

**Админ:** кнопка «Админ-панель» или `/admin`. Добавление рабочих дней, меню на дату, слоты, закрытие дня, расписание, все заказы одним сообщением (в конце — число позиций). Новый заказ приходит с кнопками «Выполнен» / «Отменить».

**Напоминания:** за 24 часа до даты и времени. Если заказ создан ближе чем за сутки — задача не ставится. При отмене задача удаляется. После перезапуска бота задачи восстанавливаются из SQLite.
