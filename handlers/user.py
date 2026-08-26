"""Роутер пользователя: заказ, прайсы, меню, отмена записи."""

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID, PRICES_HTML
from database import db as database
from keyboards.calendar import build_calendar, iso, window_bounds
from keyboards.inline import (
    CalDay,
    CalNav,
    ConfirmCB,
    OrderActCB,
    ProductCB,
    SlotCB,
    confirm_order_kb,
    products_kb,
    slots_kb,
    user_cancel_order_kb,
)
from keyboards.reply import (
    BTN_CANCEL_BOOKING,
    BTN_MAIN,
    BTN_MENU,
    BTN_ORDER,
    BTN_PRICES,
    cancel_to_menu_keyboard,
    main_keyboard,
    phone_keyboard,
)
from scheduler.reminders import cancel_reminder, schedule_reminder
from states.fsm import OrderFSM
from utils.formatters import fmt_catalog, fmt_order_card, fmt_user_preview, pretty_date

router = Router(name="user")

PHONE_RE = re.compile(r"^\+?\d{10,15}$")


async def _bookable_dates() -> set[str]:
    start, end = window_bounds()
    days = await database.list_working_days(iso(start), iso(end))
    result: set[str] = set()
    for d in days:
        if d["is_closed"]:
            continue
        times = await database.list_available_times(d["date"])
        menu = await database.list_day_menu(d["date"])
        if times and menu:
            result.add(d["date"])
    return result


async def _show_user_calendar(message: Message, year: int, month: int, *, edit: bool = False) -> None:
    clickable = await _bookable_dates()
    kb = build_calendar(mode="ord", year=year, month=month, clickable=clickable)
    text = (
        "📅 <b>Выберите дату заказа</b>\n\n"
        "Показаны рабочие дни на месяц вперёд, где есть меню и свободное время.\n"
        "<i>Нажмите на число.</i>"
    )
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Здравствуйте! Это бот для <b>заказа мяса</b>.\n\n"
        "🥩 оформите заказ на удобную дату и время\n"
        "🍽 посмотрите меню и прайс\n"
        "❓ задайте вопрос — сообщение уйдёт владельцу",
        reply_markup=main_keyboard(message.from_user.id),
    )


@router.message(F.text == BTN_MAIN)
@router.message(Command("cancel"))
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню.", reply_markup=main_keyboard(message.from_user.id))


@router.message(F.text == BTN_PRICES)
async def show_prices(message: Message) -> None:
    """Прайсы — одно HTML-сообщение, без FSM."""
    await message.answer(PRICES_HTML, reply_markup=main_keyboard(message.from_user.id))


@router.message(F.text == BTN_MENU)
async def show_menu(message: Message) -> None:
    start, end = window_bounds()
    products = await database.list_products()
    dates = await database.list_dates_with_menu(iso(start), iso(end))
    await message.answer(
        fmt_catalog(products, dates),
        reply_markup=main_keyboard(message.from_user.id),
    )


@router.message(F.text == BTN_ORDER)
async def start_order(message: Message, state: FSMContext) -> None:
    existing = await database.get_active_order(message.from_user.id)
    if existing:
        await message.answer(
            "У вас уже есть активная запись. Одновременно можно оформить только один заказ.\n\n"
            + fmt_order_card(existing, title="Ваш заказ"),
            reply_markup=main_keyboard(message.from_user.id),
        )
        return
    await state.set_state(OrderFSM.choosing_date)
    today = window_bounds()[0]
    await _show_user_calendar(message, today.year, today.month)


@router.callback_query(CalNav.filter(F.mode == "ord"), OrderFSM.choosing_date)
async def order_cal_nav(callback: CallbackQuery, callback_data: CalNav) -> None:
    await callback.answer()
    await _show_user_calendar(
        callback.message,
        callback_data.year,
        callback_data.month,
        edit=True,
    )


@router.callback_query(CalDay.filter(F.mode == "ord"), OrderFSM.choosing_date)
async def order_pick_date(callback: CallbackQuery, callback_data: CalDay, state: FSMContext) -> None:
    date = callback_data.date
    if not await database.is_date_bookable(date):
        await callback.answer("Эта дата недоступна", show_alert=True)
        return
    menu = await database.list_day_menu(date)
    if not menu:
        await callback.answer("На эту дату меню не составлено", show_alert=True)
        return
    await state.update_data(date=date)
    await state.set_state(OrderFSM.choosing_product)
    await callback.message.edit_text(
        f"🥩 <b>Выберите мясо</b> на {pretty_date(date)}:",
        reply_markup=products_kb(menu),
    )
    await callback.answer()


@router.callback_query(ProductCB.filter(), OrderFSM.choosing_product)
async def order_pick_product(callback: CallbackQuery, callback_data: ProductCB, state: FSMContext) -> None:
    product = await database.get_product(callback_data.pid)
    data = await state.get_data()
    if not product:
        await callback.answer("Позиция недоступна", show_alert=True)
        return
    times = await database.list_available_times(data["date"])
    if not times:
        await callback.answer("Свободного времени не осталось", show_alert=True)
        return
    await state.update_data(product_id=product["id"], product_name=product["name"])
    await state.set_state(OrderFSM.choosing_time)
    await callback.message.edit_text(
        f"⏰ <b>Когда заберёте заказ?</b>\n"
        f"Дата: {pretty_date(data['date'])}\n"
        f"Позиция: <b>{product['name']}</b>",
        reply_markup=slots_kb(times),
    )
    await callback.answer()


@router.callback_query(SlotCB.filter(), OrderFSM.choosing_time)
async def order_pick_time(callback: CallbackQuery, callback_data: SlotCB, state: FSMContext) -> None:
    data = await state.get_data()
    time = callback_data.time
    if not await database.is_slot_free(data["date"], time):
        await callback.answer("Этот слот уже занят, выберите другой", show_alert=True)
        times = await database.list_available_times(data["date"])
        await callback.message.edit_reply_markup(reply_markup=slots_kb(times))
        return
    await state.update_data(time=time)
    await state.set_state(OrderFSM.waiting_name)
    await callback.message.edit_text(
        f"Выбрано: {pretty_date(data['date'])} в <b>{time}</b>, "
        f"<b>{data['product_name']}</b>.\n\n"
        "Напишите, пожалуйста, <b>ваше имя</b>."
    )
    await callback.message.answer(
        "Имя одним сообщением. Чтобы выйти — «В меню».",
        reply_markup=cancel_to_menu_keyboard(),
    )
    await callback.answer()


@router.message(OrderFSM.waiting_name, F.text)
async def order_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое, попробуйте ещё раз.")
        return
    await state.update_data(client_name=name)
    await state.set_state(OrderFSM.waiting_phone)
    await message.answer(
        "Отправьте <b>номер телефона</b> кнопкой ниже или текстом "
        "(например, <code>+79001234567</code>).",
        reply_markup=phone_keyboard(),
    )


@router.message(OrderFSM.waiting_phone, F.contact)
async def order_phone_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number if message.contact else ""
    await _save_phone_and_confirm(message, state, phone)


@router.message(OrderFSM.waiting_phone, F.text)
async def order_phone_text(message: Message, state: FSMContext) -> None:
    if message.text == BTN_MAIN:
        return
    raw = re.sub(r"[\s\-()]", "", message.text or "")
    if not PHONE_RE.match(raw):
        await message.answer("Не похоже на номер. Пример: +79001234567")
        return
    await _save_phone_and_confirm(message, state, raw)


async def _save_phone_and_confirm(message: Message, state: FSMContext, phone: str) -> None:
    phone = phone.strip()
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    await state.update_data(phone=phone)
    data = await state.get_data()
    await state.set_state(OrderFSM.confirming)
    await message.answer(
        fmt_user_preview(data),
        reply_markup=confirm_order_kb(),
    )


@router.callback_query(ConfirmCB.filter(), OrderFSM.confirming)
async def order_confirm(callback: CallbackQuery, callback_data: ConfirmCB, state: FSMContext) -> None:
    user = callback.from_user
    if callback_data.ok == 0:
        await state.clear()
        await callback.message.edit_text("Оформление отменено.")
        await callback.message.answer("Главное меню.", reply_markup=main_keyboard(user.id))
        await callback.answer()
        return

    data = await state.get_data()
    if await database.get_active_order(user.id):
        await state.clear()
        await callback.answer("У вас уже есть активный заказ", show_alert=True)
        await callback.message.edit_text("Нельзя иметь две записи одновременно.")
        return
    if not await database.is_slot_free(data["date"], data["time"]):
        await callback.answer("Слот заняли, выберите другое время", show_alert=True)
        await state.set_state(OrderFSM.choosing_time)
        times = await database.list_available_times(data["date"])
        await callback.message.edit_text(
            "Это время уже занято. Выберите другое:",
            reply_markup=slots_kb(times),
        )
        return

    order_id = await database.create_order(
        user_id=user.id,
        username=user.username,
        client_name=data["client_name"],
        phone=data["phone"],
        date=data["date"],
        time=data["time"],
        product_id=data["product_id"],
        product_name=data["product_name"],
    )
    await state.clear()
    if not order_id:
        await callback.answer("Не удалось сохранить заказ", show_alert=True)
        await callback.message.answer("Попробуйте начать заново.", reply_markup=main_keyboard(user.id))
        return

    order = await database.get_order(order_id)
    schedule_reminder(callback.bot, order)

    await callback.message.edit_text(
        "✅ <b>Заказ принят!</b>\n\n" + fmt_order_card(order, title="Ваша запись")
    )
    await callback.message.answer(
        "Мы напомним за сутки до получения (если до визита больше 24 часов).",
        reply_markup=main_keyboard(user.id),
    )

    try:
        from keyboards.inline import order_admin_kb

        await callback.bot.send_message(
            ADMIN_ID,
            "🆕 " + fmt_order_card(order, title="Новый заказ"),
            reply_markup=order_admin_kb(order_id),
        )
    except Exception:
        pass
    await callback.answer("Готово")


@router.message(F.text == BTN_CANCEL_BOOKING)
async def user_want_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    order = await database.get_active_order(message.from_user.id)
    if not order:
        await message.answer("Активной записи нет.", reply_markup=main_keyboard(message.from_user.id))
        return
    await message.answer(
        "Отменить эту запись? Слот снова станет свободным.\n\n"
        + fmt_order_card(order, title="Текущий заказ"),
        reply_markup=user_cancel_order_kb(order["id"]),
    )


@router.callback_query(OrderActCB.filter(F.action == "user_cancel"))
async def user_do_cancel(callback: CallbackQuery, callback_data: OrderActCB) -> None:
    order = await database.get_order(callback_data.oid)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    cancelled = await database.cancel_order(callback_data.oid)
    if not cancelled:
        await callback.answer("Заказ уже не активен", show_alert=True)
        return
    cancel_reminder(callback_data.oid)
    await callback.message.edit_text("❌ Запись отменена. Слот снова доступен.")
    await callback.message.answer("Главное меню.", reply_markup=main_keyboard(callback.from_user.id))
    try:
        await callback.bot.send_message(
            ADMIN_ID,
            f"❌ Клиент отменил заказ #{callback_data.oid} "
            f"({pretty_date(cancelled['date'])} {cancelled['time']}, {cancelled['client_name']}).",
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "ignore")
async def ignore_cb(callback: CallbackQuery) -> None:
    await callback.answer()
