"""Асинхронный слой SQLite (aiosqlite)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import aiosqlite

from config import DB_PATH, DEFAULT_SLOTS

# Единственное соединение на процесс — удобно для WAL и транзакций
_db: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("База не инициализирована. Вызовите init_db().")
    return _db


async def init_db() -> aiosqlite.Connection:
    """Создаёт файл БД, таблицы и открывает соединение."""
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA foreign_keys = ON;")
    await _db.execute("PRAGMA journal_mode = WAL;")
    await _db.executescript(
        """
        CREATE TABLE IF NOT EXISTS working_days (
            date TEXT PRIMARY KEY,
            is_closed INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            UNIQUE(date, time)
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS day_menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            UNIQUE(date, product_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            client_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_orders_date_status ON orders(date, status);
        """
    )
    await _db.commit()
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


# ---------- рабочие дни ----------


async def add_working_day(date: str, with_default_slots: bool = True) -> bool:
    """Добавляет рабочий день. False, если день уже есть."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO working_days (date, is_closed) VALUES (?, 0)",
            (date,),
        )
        if with_default_slots:
            await db.executemany(
                "INSERT OR IGNORE INTO time_slots (date, time) VALUES (?, ?)",
                [(date, t) for t in DEFAULT_SLOTS],
            )
        await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_working_day(date: str) -> dict[str, Any] | None:
    db = await get_db()
    cur = await db.execute("SELECT date, is_closed FROM working_days WHERE date = ?", (date,))
    return _row_to_dict(await cur.fetchone())


async def list_working_days(date_from: str, date_to: str) -> list[dict[str, Any]]:
    db = await get_db()
    cur = await db.execute(
        """
        SELECT date, is_closed FROM working_days
        WHERE date >= ? AND date <= ?
        ORDER BY date
        """,
        (date_from, date_to),
    )
    return [dict(r) for r in await cur.fetchall()]


async def close_day(date: str) -> None:
    """Полностью закрывает день: новые записи недоступны."""
    db = await get_db()
    await db.execute(
        "UPDATE working_days SET is_closed = 1 WHERE date = ?",
        (date,),
    )
    await db.commit()


async def open_day(date: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE working_days SET is_closed = 0 WHERE date = ?",
        (date,),
    )
    await db.commit()


async def is_date_bookable(date: str) -> bool:
    day = await get_working_day(date)
    return bool(day) and not day["is_closed"]


# ---------- слоты ----------


async def add_slot(date: str, time: str) -> bool:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO time_slots (date, time) VALUES (?, ?)",
            (date, time),
        )
        await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def delete_slot(slot_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM time_slots WHERE id = ?", (slot_id,))
    await db.commit()


async def list_slots(date: str) -> list[dict[str, Any]]:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, date, time FROM time_slots WHERE date = ? ORDER BY time",
        (date,),
    )
    return [dict(r) for r in await cur.fetchall()]


async def list_available_times(date: str) -> list[str]:
    """Слоты без активных заказов."""
    db = await get_db()
    cur = await db.execute(
        """
        SELECT s.time
        FROM time_slots s
        WHERE s.date = ?
          AND s.time NOT IN (
              SELECT o.time FROM orders o
              WHERE o.date = ? AND o.status = 'active'
          )
        ORDER BY s.time
        """,
        (date, date),
    )
    return [r[0] for r in await cur.fetchall()]


async def is_slot_free(date: str, time: str) -> bool:
    db = await get_db()
    cur = await db.execute(
        "SELECT 1 FROM time_slots WHERE date = ? AND time = ?",
        (date, time),
    )
    if await cur.fetchone() is None:
        return False
    cur = await db.execute(
        "SELECT 1 FROM orders WHERE date = ? AND time = ? AND status = 'active'",
        (date, time),
    )
    return await cur.fetchone() is None


# ---------- продукты и меню дня ----------


async def add_product(name: str) -> int:
    db = await get_db()
    cur = await db.execute("INSERT INTO products (name) VALUES (?)", (name.strip(),))
    await db.commit()
    return cur.lastrowid


async def delete_product(product_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    await db.commit()


async def list_products() -> list[dict[str, Any]]:
    db = await get_db()
    cur = await db.execute("SELECT id, name FROM products ORDER BY name")
    return [dict(r) for r in await cur.fetchall()]


async def get_product(product_id: int) -> dict[str, Any] | None:
    db = await get_db()
    cur = await db.execute("SELECT id, name FROM products WHERE id = ?", (product_id,))
    return _row_to_dict(await cur.fetchone())


async def add_to_day_menu(date: str, product_id: int) -> bool:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO day_menu (date, product_id) VALUES (?, ?)",
            (date, product_id),
        )
        await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def remove_from_day_menu(date: str, product_id: int) -> None:
    db = await get_db()
    await db.execute(
        "DELETE FROM day_menu WHERE date = ? AND product_id = ?",
        (date, product_id),
    )
    await db.commit()


async def list_day_menu(date: str) -> list[dict[str, Any]]:
    db = await get_db()
    cur = await db.execute(
        """
        SELECT p.id, p.name
        FROM day_menu m
        JOIN products p ON p.id = m.product_id
        WHERE m.date = ?
        ORDER BY p.name
        """,
        (date,),
    )
    return [dict(r) for r in await cur.fetchall()]


async def list_dates_with_menu(date_from: str, date_to: str) -> list[tuple[str, int]]:
    db = await get_db()
    cur = await db.execute(
        """
        SELECT m.date, COUNT(*) AS cnt
        FROM day_menu m
        JOIN working_days d ON d.date = m.date
        WHERE m.date >= ? AND m.date <= ? AND d.is_closed = 0
        GROUP BY m.date
        ORDER BY m.date
        """,
        (date_from, date_to),
    )
    return [(r[0], r[1]) for r in await cur.fetchall()]


# ---------- заказы ----------


async def get_active_order(user_id: int) -> dict[str, Any] | None:
    db = await get_db()
    cur = await db.execute(
        """
        SELECT * FROM orders
        WHERE user_id = ? AND status = 'active'
        ORDER BY date, time
        LIMIT 1
        """,
        (user_id,),
    )
    return _row_to_dict(await cur.fetchone())


async def create_order(
    *,
    user_id: int,
    username: str | None,
    client_name: str,
    phone: str,
    date: str,
    time: str,
    product_id: int,
    product_name: str,
) -> int | None:
    """
    Создаёт заказ, если у пользователя нет другой активной записи
    и слот свободен. Возвращает id или None.
    """
    db = await get_db()
    await db.execute("BEGIN IMMEDIATE")
    try:
        cur = await db.execute(
            "SELECT 1 FROM orders WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        if await cur.fetchone():
            await db.rollback()
            return None
        cur = await db.execute(
            "SELECT 1 FROM orders WHERE date = ? AND time = ? AND status = 'active'",
            (date, time),
        )
        if await cur.fetchone():
            await db.rollback()
            return None
        created = datetime.now().isoformat(timespec="seconds")
        cur = await db.execute(
            """
            INSERT INTO orders (
                user_id, username, client_name, phone,
                date, time, product_id, product_name, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                user_id,
                username,
                client_name,
                phone,
                date,
                time,
                product_id,
                product_name,
                created,
            ),
        )
        await db.commit()
        return cur.lastrowid
    except Exception:
        await db.rollback()
        raise


async def get_order(order_id: int) -> dict[str, Any] | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    return _row_to_dict(await cur.fetchone())


async def cancel_order(order_id: int) -> dict[str, Any] | None:
    """Отмена: слот снова свободен (активных заказов на него нет)."""
    order = await get_order(order_id)
    if not order or order["status"] != "active":
        return None
    db = await get_db()
    await db.execute(
        "UPDATE orders SET status = 'cancelled' WHERE id = ?",
        (order_id,),
    )
    await db.commit()
    order["status"] = "cancelled"
    return order


async def complete_order(order_id: int) -> dict[str, Any] | None:
    order = await get_order(order_id)
    if not order or order["status"] != "active":
        return None
    db = await get_db()
    await db.execute(
        "UPDATE orders SET status = 'completed' WHERE id = ?",
        (order_id,),
    )
    await db.commit()
    order["status"] = "completed"
    return order


async def list_active_orders() -> list[dict[str, Any]]:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM orders WHERE status = 'active' ORDER BY date, time, id"
    )
    return [dict(r) for r in await cur.fetchall()]


async def list_orders_for_date(date: str) -> list[dict[str, Any]]:
    db = await get_db()
    cur = await db.execute(
        """
        SELECT * FROM orders
        WHERE date = ? AND status IN ('active', 'completed')
        ORDER BY time, id
        """,
        (date,),
    )
    return [dict(r) for r in await cur.fetchall()]


async def cancel_active_orders_for_date(date: str) -> list[dict[str, Any]]:
    orders = [
        o
        for o in await list_orders_for_date(date)
        if o["status"] == "active"
    ]
    db = await get_db()
    await db.execute(
        "UPDATE orders SET status = 'cancelled' WHERE date = ? AND status = 'active'",
        (date,),
    )
    await db.commit()
    return orders
