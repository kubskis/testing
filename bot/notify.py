"""Отправка заявок владелицам."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputMediaPhoto, Message

from . import cards
from .config import Config
from .keyboards import owner_kb

log = logging.getLogger(__name__)


async def send_refs(bot: Bot, chat_id: int, refs: list[dict]) -> None:
    """Отправляет сохранённые вложения анкеты (фото — альбомом, файлы — по одному)."""
    photos = [r["id"] for r in refs if r["t"] == "photo"]
    docs = [r["id"] for r in refs if r["t"] == "doc"]
    if len(photos) >= 2:
        await bot.send_media_group(chat_id, [InputMediaPhoto(media=i) for i in photos])
    elif photos:
        await bot.send_photo(chat_id, photos[0])
    for file_id in docs:
        await bot.send_document(chat_id, file_id)


async def send_card(bot: Bot, chat_id: int, req: dict, with_refs: bool = True) -> None:
    if with_refs and req["photos"]:
        await send_refs(bot, chat_id, req["photos"])
    await bot.send_message(chat_id, cards.render_card(req), reply_markup=owner_kb(req))


async def notify_owners(
    bot: Bot, config: Config, req: dict, source_message: Message | None = None
) -> int:
    """Рассылает новую заявку всем владелицам. Возвращает, скольким дошло."""
    delivered = 0
    for owner_id in config.owner_ids:
        try:
            await send_card(bot, owner_id, req)
            if source_message is not None and req["data"].get("has_media"):
                await source_message.copy_to(owner_id)
            delivered += 1
        except TelegramAPIError as e:
            # Обычно значит, что владелица ещё не нажала /start у бота
            log.warning("Не удалось отправить заявку владелице %s: %s", owner_id, e)
    return delivered
