from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID


class IsAdmin(BaseFilter):
    """Доступ только для ADMIN_ID из .env."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user) and user.id == ADMIN_ID
