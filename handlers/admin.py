"""Админ-панель: только ADMIN_ID, интерфейс на inline-кнопках, FSM для ввода."""

import re
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db as database
from filters.admin import IsAdmin
from keyboards.calendar import build_calendar, iso, window_bounds
from keyboards.inline import (
    AdminMenuCB,
    CalDay,
    CalNav,
    DayProductCB,
    OrderActCB,
    SlotAdminCB,
    admin_panel_kb,
    back_admin_kb,
    cancel_orders_list_kb,
    day_menu_admin_kb,
    slots_admin_kb,
)
from keyboards.reply import BTN_ADMIN, cancel_to_menu_keyboard, main_keyboard
from scheduler.reminders import cancel_reminder
from states.fsm import AdminFSM
from utils.formatters import fmt_all_orders, fmt_order_card, fmt_schedule, pretty_date

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


async def _working_set() -> set[str]:
    start, end = window_bounds()
    days = await database.list_working_days(iso(start), iso(end))
    return {d["date"] for d in days}


async def _send_panel(message: Message) -> None:
    await message.answer(
        "🛠 <b>Админ-панель</b>\nВыберите действие:",
        reply_markup=admin_panel_kb(),
    )


@router.message(F.text == BTN_ADMIN)
@router.message(Command("admin"))
async def open_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _send_panel(message)


@router.callback_query(AdminMenuCB.filter(F.action == "home"))
async def admin_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🛠 <b>Админ-панель</b>\nВыберите действие:",
        reply_markup=admin_panel_kb(),
    )
    await callback.answer()


@router.callback_query(AdminMenuCB.filter(F.action == "days"))
async def admin_days(callback: CallbackQuery) -> None:
    start, end = window_bounds()
    clickable = set()
    d = start
    while d <= end:
        clickable.add(iso(d))
        d += timedelta(days=1)
    marked = await _working_set()
    today = date.today()
    await callback.message.edit_text(
        "📅 <b>Рабочие дни</b>\n"
        "Нажмите дату, чтобы добавить её (слоты 10:00–18:00 создаются автоматически).\n"
        "Уже добавленные дни отмечены точкой.",
        reply_markup=build_calendar(
            mode="add",
            year=today.year,
            month=today.month,
            clickable=clickable,
            marked=marked,
            show_admin_back=True,
        ),
    )
    await callback.answer()


@router.callback_query(CalNav.filter(F.mode == "add"))
@router.callback_query(CalNav.filter(F.mode == "mnu"))
@router.callback_query(CalNav.filter(F.mode == "slt"))
@router.callback_query(CalNav.filter(F.mode == "cls"))
@router.callback_query(CalNav.filter(F.mode == "sch"))
async def admin_cal_nav(callback: CallbackQuery, callback_data: CalNav) -> None:
    mode = callback_data.mode
    marked: set[str] = set()
    if mode == "add":
        start, end = window_bounds()
        clickable = set()
        d = start
        while d <= end:
            clickable.add(iso(d))
            d += timedelta(days=1)
        marked = await _working_set()
    else:
        clickable = await _working_set()
        if not clickable:
            await callback.answer("Сначала добавьте рабочие дни", show_alert=True)
            return
    titles = {
        "add": "📅 Рабочие дни",
        "mnu": "🥩 Меню на дату — выберите день",
        "slt": "⏰ Слоты — выберите день",
        "cls": "🔒 Закрыть день — выберите дату",
        "sch": "📋 Расписание — выберите дату",
    }
    await callback.message.edit_text(
        f"<b>{titles[mode]}</b>",
        reply_markup=build_calendar(
            mode=mode,
            year=callback_data.year,
            month=callback_data.month,
            clickable=clickable,
            marked=marked,
            show_admin_back=True,
        ),
    )
    await callback.answer()


@router.callback_query(CalDay.filter(F.mode == "add"))
async def admin_add_day(callback: CallbackQuery, callback_data: CalDay) -> None:
    added = await database.add_working_day(callback_data.date)
    if added:
        await callback.answer(f"Добавлен {pretty_date(callback_data.date)}", show_alert=True)
    else:
        await callback.answer("Этот день уже в расписании", show_alert=True)
    # обновить точки на календаре
    start, end = window_bounds()
    clickable = set()
    d = start
    while d <= end:
        clickable.add(iso(d))
        d += timedelta(days=1)
    marked = await _working_set()
    y, m = int(callback_data.date[:4]), int(callback_data.date[5:7])
    await callback.message.edit_reply_markup(
        reply_markup=build_calendar(
            mode="add",
            year=y,
            month=m,
            clickable=clickable,
            marked=marked,
            show_admin_back=True,
        )
    )


def _need_working_calendar(mode: str, title: str):
    async def handler(callback: CallbackQuery) -> None:
        clickable = await _working_set()
        if not clickable:
            await callback.answer("Сначала добавьте рабочие дни", show_alert=True)
            return
        today = date.today()
        await callback.message.edit_text(
            title,
            reply_markup=build_calendar(
                mode=mode,
                year=today.year,
                month=today.month,
                clickable=clickable,
                show_admin_back=True,
            ),
        )
        await callback.answer()

    return handler


router.callback_query.register(_need_working_calendar("mnu", "🥩 <b>Меню на дату</b>\nВыберите день:"), AdminMenuCB.filter(F.action == "daymenu"))
router.callback_query.register(_need_working_calendar("slt", "⏰ <b>Слоты времени</b>\nВыберите день:"), AdminMenuCB.filter(F.action == "slots"))
router.callback_query.register(_need_working_calendar("cls", "🔒 <b>Закрыть день</b>\nВсе активные заказы на эту дату будут отменены."), AdminMenuCB.filter(F.action == "close"))
router.callback_query.register(_need_working_calendar("sch", "📋 <b>Расписание</b>\nВыберите дату:"), AdminMenuCB.filter(F.action == "sched"))


@router.callback_query(CalDay.filter(F.mode == "mnu"))
async def admin_day_menu(callback: CallbackQuery, callback_data: CalDay) -> None:
    await _render_day_menu(callback, callback_data.date)


async def _render_day_menu(callback: CallbackQuery, date_s: str) -> None:
    on_menu = await database.list_day_menu(date_s)
    catalog = await database.list_products()
    text = (
        f"🥩 <b>Меню на {pretty_date(date_s)}</b>\n\n"
        "❌ — убрать с этой даты\n"
        "➕ — добавить из каталога"
    )
    await callback.message.edit_text(text, reply_markup=day_menu_admin_kb(date_s, on_menu, catalog))
    await callback.answer()


@router.callback_query(DayProductCB.filter(F.action == "add"))
async def admin_menu_add(callback: CallbackQuery, callback_data: DayProductCB) -> None:
    await database.add_to_day_menu(callback_data.date, callback_data.pid)
    await _render_day_menu(callback, callback_data.date)


@router.callback_query(DayProductCB.filter(F.action == "del"))
async def admin_menu_del(callback: CallbackQuery, callback_data: DayProductCB) -> None:
    await database.remove_from_day_menu(callback_data.date, callback_data.pid)
    await _render_day_menu(callback, callback_data.date)


@router.callback_query(DayProductCB.filter(F.action == "new"))
async def admin_menu_new(callback: CallbackQuery, callback_data: DayProductCB, state: FSMContext) -> None:
    await state.set_state(AdminFSM.product_name)
    await state.update_data(target_date=callback_data.date)
    await callback.message.answer(
        "Введите <b>название продукта</b> (например, «Говядина вырезка»).",
        reply_markup=cancel_to_menu_keyboard(),
    )
    await callback.answer()


@router.message(AdminFSM.product_name, F.text)
async def admin_save_product(message: Message, state: FSMContext) -> None:
    from keyboards.reply import BTN_MAIN

    if message.text == BTN_MAIN:
        return
    name = message.text.strip()
    data = await state.get_data()
    date_s = data.get("target_date")
    await state.clear()
    try:
        pid = await database.add_product(name)
        if date_s:
            await database.add_to_day_menu(date_s, pid)
        await message.answer(
            f"Продукт <b>{name}</b> добавлен в каталог"
            + (f" и в меню на {pretty_date(date_s)}." if date_s else "."),
            reply_markup=main_keyboard(message.from_user.id),
        )
        await _send_panel(message)
    except Exception:
        await message.answer(
            "Не удалось добавить (возможно, такое имя уже есть).",
            reply_markup=main_keyboard(message.from_user.id),
        )


@router.callback_query(CalDay.filter(F.mode == "slt"))
async def admin_slots_date(callback: CallbackQuery, callback_data: CalDay) -> None:
    await _render_slots(callback, callback_data.date)


async def _render_slots(callback: CallbackQuery, date_s: str) -> None:
    slots = await database.list_slots(date_s)
    await callback.message.edit_text(
        f"⏰ <b>Слоты на {pretty_date(date_s)}</b>\nНажмите слот, чтобы удалить.",
        reply_markup=slots_admin_kb(date_s, slots),
    )
    await callback.answer()


@router.callback_query(SlotAdminCB.filter(F.action == "del"))
async def admin_slot_del(callback: CallbackQuery, callback_data: SlotAdminCB) -> None:
    await database.delete_slot(callback_data.sid)
    await _render_slots(callback, callback_data.date)


@router.callback_query(SlotAdminCB.filter(F.action == "add"))
async def admin_slot_add(callback: CallbackQuery, callback_data: SlotAdminCB, state: FSMContext) -> None:
    await state.set_state(AdminFSM.slot_time)
    await state.update_data(target_date=callback_data.date)
    await callback.message.answer(
        "Введите время в формате <b>ЧЧ:ММ</b> (например, 19:30).",
        reply_markup=cancel_to_menu_keyboard(),
    )
    await callback.answer()


@router.message(AdminFSM.slot_time, F.text)
async def admin_save_slot(message: Message, state: FSMContext) -> None:
    from keyboards.reply import BTN_MAIN

    if message.text == BTN_MAIN:
        return
    raw = (message.text or "").strip()
    if not TIME_RE.match(raw):
        await message.answer("Неверный формат. Пример: 14:00")
        return
    h, m = raw.split(":")
    time = f"{int(h):02d}:{m}"
    data = await state.get_data()
    date_s = data["target_date"]
    await state.clear()
    ok = await database.add_slot(date_s, time)
    await message.answer(
        f"Слот <b>{time}</b> добавлен." if ok else "Такой слот уже есть.",
        reply_markup=main_keyboard(message.from_user.id),
    )
    await _send_panel(message)


@router.callback_query(CalDay.filter(F.mode == "cls"))
async def admin_close_day(callback: CallbackQuery, callback_data: CalDay) -> None:
    date_s = callback_data.date
    day = await database.get_working_day(date_s)
    if day and day["is_closed"]:
        await database.open_day(date_s)
        await callback.message.edit_text(
            f"🟢 День <b>{pretty_date(date_s)}</b> снова открыт.",
            reply_markup=back_admin_kb(),
        )
        await callback.answer("Открыт")
        return
    cancelled = await database.cancel_active_orders_for_date(date_s)
    await database.close_day(date_s)
    for o in cancelled:
        cancel_reminder(o["id"])
        try:
            await callback.bot.send_message(
                o["user_id"],
                f"❌ Заказ на {pretty_date(date_s)} {o['time']} отменён: день закрыт.",
            )
        except Exception:
            pass
    await callback.message.edit_text(
        f"🔒 День <b>{pretty_date(date_s)}</b> закрыт.\n"
        f"Отменено заказов: <b>{len(cancelled)}</b>.",
        reply_markup=back_admin_kb(),
    )
    await callback.answer()


@router.callback_query(CalDay.filter(F.mode == "sch"))
async def admin_schedule(callback: CallbackQuery, callback_data: CalDay) -> None:
    date_s = callback_data.date
    day = await database.get_working_day(date_s)
    closed = bool(day and day["is_closed"])
    text = fmt_schedule(
        date_s,
        await database.list_slots(date_s),
        await database.list_orders_for_date(date_s),
        await database.list_day_menu(date_s),
        closed,
    )
    await callback.message.edit_text(text, reply_markup=back_admin_kb())
    await callback.answer()


@router.callback_query(AdminMenuCB.filter(F.action == "all"))
async def admin_all_orders(callback: CallbackQuery) -> None:
    orders = await database.list_active_orders()
    text = fmt_all_orders(orders)
    # Telegram лимит 4096 символов — режем при необходимости
    if len(text) > 4000:
        text = text[:3900] + "\n\n<i>…сообщение обрезано</i>"
    await callback.message.edit_text(text, reply_markup=back_admin_kb())
    await callback.answer()


@router.callback_query(AdminMenuCB.filter(F.action == "cancel"))
async def admin_cancel_list(callback: CallbackQuery) -> None:
    orders = await database.list_active_orders()
    if not orders:
        await callback.message.edit_text("Активных заказов нет.", reply_markup=back_admin_kb())
        await callback.answer()
        return
    await callback.message.edit_text(
        "❌ <b>Нажмите заказ, чтобы отменить</b> (слот освободится):",
        reply_markup=cancel_orders_list_kb(orders),
    )
    await callback.answer()


@router.callback_query(OrderActCB.filter(F.action == "cancel"))
async def admin_cancel_order(callback: CallbackQuery, callback_data: OrderActCB) -> None:
    order = await database.cancel_order(callback_data.oid)
    if not order:
        await callback.answer("Заказ уже не активен", show_alert=True)
        return
    cancel_reminder(order["id"])
    try:
        await callback.bot.send_message(
            order["user_id"],
            f"❌ Ваш заказ #{order['id']} на {pretty_date(order['date'])} "
            f"{order['time']} отменён администратором.",
        )
    except Exception:
        pass
    await callback.message.edit_text(
        "Заказ отменён, слот свободен.\n\n" + fmt_order_card(order, title="Отменён"),
        reply_markup=back_admin_kb(),
    )
    await callback.answer("Отменено")


@router.callback_query(OrderActCB.filter(F.action == "done"))
async def admin_done(callback: CallbackQuery, callback_data: OrderActCB) -> None:
    order = await database.complete_order(callback_data.oid)
    if not order:
        await callback.answer("Заказ уже не активен", show_alert=True)
        return
    cancel_reminder(order["id"])
    try:
        await callback.bot.send_message(
            order["user_id"],
            f"✅ Заказ #{order['id']} отмечен как выполненный. Спасибо!",
        )
    except Exception:
        pass
    await callback.message.edit_text(
        "✅ Отмечен выполненным.\n\n" + fmt_order_card(order, title="Выполнен")
    )
    await callback.answer("Готово")
