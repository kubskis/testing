from aiogram.filters import Filter
from aiogram.types import TelegramObject

from .config import Config


class IsOwner(Filter):
    """Пропускает только владелиц бота (ID из OWNER_IDS).

    Для обычных людей обработчики владельцев просто не срабатывают, и сообщение
    уходит дальше — в обычные хендлеры или в «выберите действие»."""

    async def __call__(self, event: TelegramObject, config: Config) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in config.owner_ids
