"""CallbackData и inline-кнопки (кроме календаря)."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class CalNav(CallbackData, prefix="cn"):
    """Листание месяца. mode: ord/add/mnu/slt/cls/sch"""

    mode: str
    year: int
    month: int


class CalDay(CallbackData, prefix="cd"):
    mode: str
    date: str  # YYYY-MM-DD


class ProductCB(CallbackData, prefix="pr"):
    pid: int


class SlotCB(CallbackData, prefix="sl"):
    time: str


class ConfirmCB(CallbackData, prefix="cf"):
    ok: int  # 1 / 0


class AdminMenuCB(CallbackData, prefix="am"):
    action: str


class DayProductCB(CallbackData, prefix="dp"):
    action: str  # add / del / new
    date: str
    pid: int = 0


class SlotAdminCB(CallbackData, prefix="sa"):
    action: str  # del / add
    date: str
    sid: int = 0


class OrderActCB(CallbackData, prefix="oa"):
    action: str  # done / cancel / user_cancel
    oid: int


def admin_panel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📅 Рабочие дни", callback_data=AdminMenuCB(action="days").pack())
    b.button(text="🥩 Меню на дату", callback_data=AdminMenuCB(action="daymenu").pack())
    b.button(text="⏰ Слоты времени", callback_data=AdminMenuCB(action="slots").pack())
    b.button(text="📦 Все заказы", callback_data=AdminMenuCB(action="all").pack())
    b.button(text="📋 Расписание на дату", callback_data=AdminMenuCB(action="sched").pack())
    b.button(text="🔒 Закрыть день", callback_data=AdminMenuCB(action="close").pack())
    b.button(text="❌ Отменить заказ", callback_data=AdminMenuCB(action="cancel").pack())
    b.adjust(1)
    return b.as_markup()


def back_admin_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ В админ-панель", callback_data=AdminMenuCB(action="home").pack())
    return b.as_markup()


def products_kb(products: list[dict], extra: InlineKeyboardButton | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=p["name"], callback_data=ProductCB(pid=p["id"]).pack())
    b.adjust(1)
    if extra:
        b.row(extra)
    return b.as_markup()


def slots_kb(times: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in times:
        b.button(text=t, callback_data=SlotCB(time=t).pack())
    b.adjust(3)
    return b.as_markup()


def confirm_order_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=ConfirmCB(ok=1).pack())
    b.button(text="✖️ Отмена", callback_data=ConfirmCB(ok=0).pack())
    b.adjust(2)
    return b.as_markup()


def order_admin_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Выполнен", callback_data=OrderActCB(action="done", oid=order_id).pack())
    b.button(text="❌ Отменить", callback_data=OrderActCB(action="cancel", oid=order_id).pack())
    b.adjust(2)
    return b.as_markup()


def user_cancel_order_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text="Да, отменить запись",
        callback_data=OrderActCB(action="user_cancel", oid=order_id).pack(),
    )
    return b.as_markup()


def cancel_orders_list_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        title = f"#{o['id']} {o['date'][8:10]}.{o['date'][5:7]} {o['time']} — {o['client_name']}"
        b.button(text=title[:64], callback_data=OrderActCB(action="cancel", oid=o["id"]).pack())
    b.button(text="⬅️ В админ-панель", callback_data=AdminMenuCB(action="home").pack())
    b.adjust(1)
    return b.as_markup()


def day_menu_admin_kb(date: str, on_menu: list[dict], catalog: list[dict]) -> InlineKeyboardMarkup:
    """Удаление позиций с даты + добавление из каталога."""
    b = InlineKeyboardBuilder()
    on_ids = {p["id"] for p in on_menu}
    for p in on_menu:
        b.button(
            text=f"❌ {p['name']}",
            callback_data=DayProductCB(action="del", date=date, pid=p["id"]).pack(),
        )
    for p in catalog:
        if p["id"] not in on_ids:
            b.button(
                text=f"➕ {p['name']}",
                callback_data=DayProductCB(action="add", date=date, pid=p["id"]).pack(),
            )
    b.button(
        text="🆕 Новый продукт в каталог",
        callback_data=DayProductCB(action="new", date=date, pid=0).pack(),
    )
    b.button(text="⬅️ В админ-панель", callback_data=AdminMenuCB(action="home").pack())
    b.adjust(1)
    return b.as_markup()


def slots_admin_kb(date: str, slots: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in slots:
        b.button(
            text=f"❌ {s['time']}",
            callback_data=SlotAdminCB(action="del", date=date, sid=s["id"]).pack(),
        )
    b.button(text="➕ Добавить слот", callback_data=SlotAdminCB(action="add", date=date, sid=0).pack())
    b.button(text="⬅️ В админ-панель", callback_data=AdminMenuCB(action="home").pack())
    b.adjust(2)
    return b.as_markup()
