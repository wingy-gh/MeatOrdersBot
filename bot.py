"""Точка входа Telegram-бота заказов мяса."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, validate_config
from database.db import close_db, init_db
from handlers import admin, questions, user
from scheduler.reminders import restore_reminders, scheduler


async def on_startup(bot: Bot) -> None:
    await init_db()
    scheduler.start()
    restored = await restore_reminders(bot)
    logging.info("Планировщик запущен, восстановлено напоминаний: %s", restored)


async def on_shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await close_db()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    validate_config()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user.router)
    dp.include_router(questions.router)
    dp.include_router(admin.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
