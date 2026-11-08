"""Проверка подписки на канал: без подписки пользоваться ботом нельзя."""
import logging
import time

from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from . import texts
from .config import Config
from .keyboards import subscribe_kb

log = logging.getLogger(__name__)

SUBSCRIBED_STATUSES = {"creator", "administrator", "member"}
CACHE_TTL = 120  # секунд: подписанного человека не проверяем заново на каждое сообщение


class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self, config: Config) -> None:
        self.config = config
        self._ok_until: dict[int, float] = {}
        self._owners_warned = False

    async def _check(self, bot: Bot, user_id: int) -> bool | None:
        """True — подписан, False — нет, None — проверить не удалось."""
        now = time.monotonic()
        if self._ok_until.get(user_id, 0) > now:
            return True
        try:
            member = await bot.get_chat_member(self.config.required_channel, user_id)
        except TelegramAPIError as e:
            log.error(
                "Не удалось проверить подписку на %s: %s. "
                "Бот должен быть администратором канала.",
                self.config.required_channel, e,
            )
            await self._warn_owners(bot, str(e))
            return None
        subscribed = member.status in SUBSCRIBED_STATUSES or (
            member.status == "restricted" and bool(getattr(member, "is_member", False))
        )
        if subscribed:
            self._ok_until[user_id] = now + CACHE_TTL
        return subscribed

    async def _warn_owners(self, bot: Bot, error: str) -> None:
        """Один раз за запуск сообщаем владелицам, что проверка подписки не работает."""
        if self._owners_warned:
            return
        self._owners_warned = True
        for owner_id in self.config.owner_ids:
            try:
                await bot.send_message(
                    owner_id,
                    f"Бот не может проверить подписку на канал {self.config.required_channel} "
                    f"({error}).\nСделайте бота администратором этого канала. "
                    "Пока это не сделано, бот пускает всех без проверки.",
                )
            except TelegramAPIError:
                pass

    async def __call__(self, handler, event, data):
        cfg = self.config
        user = data.get("event_from_user")
        if not cfg.required_channel or user is None or user.id in cfg.owner_ids:
            return await handler(event, data)

        subscribed = await self._check(data["bot"], user.id)
        if subscribed is not False:
            # подписан (True) либо проверка сломана (None) — не блокируем клиентов
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("Сначала подпишитесь на канал", show_alert=True)
            if event.data == "sub:check" or event.message is None:
                return
            target = event.message
        else:
            target = event
        await target.answer(texts.SUB_REQUIRED, reply_markup=subscribe_kb(cfg.channel_url))
