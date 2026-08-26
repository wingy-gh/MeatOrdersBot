"""FSM-состояния пользователя и администратора."""

from aiogram.fsm.state import State, StatesGroup


class OrderFSM(StatesGroup):
    choosing_date = State()
    choosing_product = State()
    choosing_time = State()
    waiting_name = State()
    waiting_phone = State()
    confirming = State()


class QuestionFSM(StatesGroup):
    waiting_text = State()


class AdminFSM(StatesGroup):
    product_name = State()
    slot_time = State()
