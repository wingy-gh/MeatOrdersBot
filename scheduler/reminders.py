from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from config import TIMEZONE
from database import db as database
from utils.formatters import pretty_date

scheduler = AsyncIOScheduler(timezone=TIMEZONE)


def job_id(order_id: int) -> str:
    return f"reminder_{order_id}"


def _tz() -> ZoneInfo:
    return ZoneInfo(TIMEZONE)


def reminder_run_at(date: str, time: str) -> datetime | None:
    """Момент отправки: за 24 часа до визита. None — если уже поздно планировать."""
    visit = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=_tz())
    run_at = visit - timedelta(hours=24)
    if run_at <= datetime.now(_tz()):
        return None
    return run_at


async def send_reminder(bot: Bot, user_id: int, when_text: str) -> None:
    text = (
        f"Напоминаем, что вы сделали заказ {when_text}.\n"
        "Ждём вас 🥩"
    )
    try:
        await bot.send_message(user_id, text)
    except Exception:
        # Пользователь мог заблокировать бота — задачу просто пропускаем
        pass


def schedule_reminder(bot: Bot, order: dict) -> None:
    """Ставит задачу, только если до визита больше 24 часов."""
    run_at = reminder_run_at(order["date"], order["time"])
    if run_at is None:
        return
    when_text = f"{pretty_date(order['date'])} в {order['time']}"
    scheduler.add_job(
        send_reminder,
        trigger="date",
        run_date=run_at,
        args=[bot, order["user_id"], when_text],
        id=job_id(order["id"]),
        replace_existing=True,
    )


def cancel_reminder(order_id: int) -> None:
    jid = job_id(order_id)
    if scheduler.get_job(jid):
        scheduler.remove_job(jid)


async def restore_reminders(bot: Bot) -> int:
    """После перезапуска восстанавливаем неотправленные напоминания из БД."""
    restored = 0
    for order in await database.list_active_orders():
        run_at = reminder_run_at(order["date"], order["time"])
        if run_at is None:
            continue
        schedule_reminder(bot, order)
        restored += 1
    return restored
