"""Форматирование HTML-сообщений."""

from collections import Counter
from datetime import datetime


def pretty_date(iso_date: str) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return d.strftime("%d.%m.%Y")


def fmt_order_card(order: dict, title: str = "Заказ") -> str:
    uname = f"@{order['username']}" if order.get("username") else "—"
    return (
        f"<b>{title} #{order['id']}</b>\n\n"
        f"📅 Дата: <b>{pretty_date(order['date'])}</b>\n"
        f"⏰ Время: <b>{order['time']}</b>\n"
        f"🥩 Позиция: <b>{order['product_name']}</b>\n"
        f"👤 Имя: {order['client_name']}\n"
        f"📞 Телефон: <code>{order['phone']}</code>\n"
        f"💬 Telegram: {uname}\n"
        f"🆔 ID: <code>{order['user_id']}</code>"
    )


def fmt_user_preview(data: dict) -> str:
    return (
        "Проверьте заказ перед подтверждением:\n\n"
        f"📅 Дата: <b>{pretty_date(data['date'])}</b>\n"
        f"⏰ Время: <b>{data['time']}</b>\n"
        f"🥩 Позиция: <b>{data['product_name']}</b>\n"
        f"👤 Имя: {data['client_name']}\n"
        f"📞 Телефон: <code>{data['phone']}</code>"
    )


def fmt_schedule(date: str, slots: list[dict], orders: list[dict], menu: list[dict], closed: bool) -> str:
    busy = {o["time"]: o for o in orders if o["status"] == "active"}
    lines = [
        f"📋 <b>Расписание на {pretty_date(date)}</b>",
        "🔒 День закрыт" if closed else "🟢 День открыт",
        "",
        "<b>Меню:</b>",
    ]
    if menu:
        lines.extend(f"• {p['name']}" for p in menu)
    else:
        lines.append("<i>не задано</i>")
    lines += ["", "<b>Слоты:</b>"]
    if not slots:
        lines.append("<i>слотов нет</i>")
    for s in slots:
        o = busy.get(s["time"])
        if o:
            lines.append(
                f"• {s['time']} — ❌ {o['client_name']} / {o['product_name']} (#{o['id']})"
            )
        else:
            lines.append(f"• {s['time']} — ✅ свободно")
    return "\n".join(lines)


def fmt_all_orders(orders: list[dict]) -> str:
    if not orders:
        return "📦 <b>Активных заказов нет</b>\n\n<b>Всего позиций: 0</b>"

    blocks = ["📦 <b>Все активные заказы</b>\n"]
    names: list[str] = []
    for i, o in enumerate(orders, 1):
        names.append(o["product_name"])
        uname = f"@{o['username']}" if o.get("username") else "—"
        blocks.append(
            f"<b>{i}.</b> {pretty_date(o['date'])} {o['time']} — <b>{o['product_name']}</b>\n"
            f"   {o['client_name']}, <code>{o['phone']}</code>, {uname}  (#{o['id']})"
        )

    total = len(orders)
    counter = Counter(names)
    parts = "\n".join(f"• {name}: {cnt}" for name, cnt in counter.most_common())
    blocks.append(f"\n<b>Всего позиций: {total}</b>\n{parts}")
    return "\n".join(blocks)


def fmt_catalog(products: list[dict], dates_with_menu: list[tuple[str, int]]) -> str:
    lines = ["🍽 <b>Меню</b>\n", "<b>Каталог продукции:</b>"]
    if products:
        lines.extend(f"• {p['name']}" for p in products)
    else:
        lines.append("<i>каталог пока пуст — администратор добавит позиции</i>")
    lines += ["", "<b>Ближайшие даты с меню:</b>"]
    if dates_with_menu:
        for d, cnt in dates_with_menu:
            lines.append(f"• {pretty_date(d)} — {cnt} поз.")
    else:
        lines.append("<i>на ближайший месяц меню ещё не составлено</i>")
    lines.append("\n<i>Наличие на конкретный день выбирается при оформлении заказа.</i>")
    return "\n".join(lines)
