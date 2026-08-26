"""Календарь на inline-кнопках (окно записи — 1 месяц)."""

from __future__ import annotations

import calendar as cal
from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SCHEDULE_DAYS
from keyboards.inline import AdminMenuCB, CalDay, CalNav

WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
MONTHS_RU = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


def window_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    return today, today + timedelta(days=SCHEDULE_DAYS)


def iso(d: date) -> str:
    return d.isoformat()


def build_calendar(
    *,
    mode: str,
    year: int,
    month: int,
    clickable: set[str],
    marked: set[str] | None = None,
    show_admin_back: bool = False,
) -> InlineKeyboardMarkup:
    """
    clickable — даты YYYY-MM-DD, по которым можно нажать.
    marked — дополнительно помечаются символом • (например, уже рабочие дни).
    """
    marked = marked or set()
    start, end = window_bounds()
    builder = InlineKeyboardBuilder()

    builder.button(text=f"{MONTHS_RU[month]} {year}", callback_data="ignore")
    builder.adjust(1)

    for wd in WEEKDAYS:
        builder.button(text=wd, callback_data="ignore")

    first_wd, days_in_month = cal.monthrange(year, month)  # Mon=0
    # Пустые клетки до первого дня
    for _ in range(first_wd):
        builder.button(text=" ", callback_data="ignore")

    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        key = iso(d)
        if key in clickable:
            label = str(day)
            if key in marked:
                label = f"•{day}"
            builder.button(text=label, callback_data=CalDay(mode=mode, date=key).pack())
        else:
            builder.button(text="·", callback_data="ignore")

    # Добить неделю до 7
    total = first_wd + days_in_month
    rest = (7 - total % 7) % 7
    for _ in range(rest):
        builder.button(text=" ", callback_data="ignore")

    builder.adjust(1, 7)

    prev_month = date(year, month, 1) - timedelta(days=1)
    next_month = date(year, month, 28) + timedelta(days=8)
    next_month = date(next_month.year, next_month.month, 1)

    nav = InlineKeyboardBuilder()
    if date(prev_month.year, prev_month.month, 1) <= date(end.year, end.month, 1):
        if date(year, month, 1) > date(start.year, start.month, 1):
            nav.button(
                text="◀️",
                callback_data=CalNav(mode=mode, year=prev_month.year, month=prev_month.month).pack(),
            )
    nav.button(text=" ", callback_data="ignore")
    if date(year, month, 1) < date(end.year, end.month, 1):
        nav.button(
            text="▶️",
            callback_data=CalNav(mode=mode, year=next_month.year, month=next_month.month).pack(),
        )
    nav.adjust(3)
    builder.attach(nav)

    if show_admin_back:
        back = InlineKeyboardBuilder()
        back.button(text="⬅️ В админ-панель", callback_data=AdminMenuCB(action="home").pack())
        builder.attach(back)

    return builder.as_markup()
