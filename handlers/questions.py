"""Вопрос владельцу: FSM ждёт текст и пересылает ADMIN_ID."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_ID
from keyboards.reply import BTN_MAIN, BTN_QUESTION, cancel_to_menu_keyboard, main_keyboard
from states.fsm import QuestionFSM

router = Router(name="questions")


@router.message(F.text == BTN_QUESTION)
async def ask_question(message: Message, state: FSMContext) -> None:
    await state.set_state(QuestionFSM.waiting_text)
    await message.answer(
        "Напишите вопрос одним сообщением — я сразу передам его владельцу.",
        reply_markup=cancel_to_menu_keyboard(),
    )


@router.message(QuestionFSM.waiting_text, F.text)
async def receive_question(message: Message, state: FSMContext) -> None:
    if message.text == BTN_MAIN:
        return
    await state.clear()
    user = message.from_user
    uname = f"@{user.username}" if user.username else "без username"
    try:
        await message.bot.send_message(
            ADMIN_ID,
            "❓ <b>Вопрос от клиента</b>\n"
            f"👤 {user.full_name} ({uname})\n"
            f"🆔 <code>{user.id}</code>\n\n"
            f"{message.html_text or message.text}",
        )
        await message.answer(
            "Сообщение отправлено владельцу. Он ответит вам лично в Telegram.",
            reply_markup=main_keyboard(user.id),
        )
    except Exception:
        await message.answer(
            "Не удалось доставить сообщение. Попробуйте позже.",
            reply_markup=main_keyboard(user.id),
        )
