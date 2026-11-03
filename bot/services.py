"""Отправка сообщений владелицам и клиентам (общая часть для хендлеров)."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InputMediaPhoto, ReplyParameters

from . import db, render
from .config import Config
from .keyboards import owner_kb

log = logging.getLogger(__name__)


async def notify_owners(bot: Bot, config: Config, req: dict) -> int:
    """Отправляет заявку всем владелицам. Возвращает, скольким дошло."""
    text = render.request_text(req)
    kb = owner_kb(req)
    delivered = 0
    for owner_id in config.owner_ids:
        try:
            msg = await bot.send_message(owner_id, text, reply_markup=kb)
        except TelegramAPIError as e:
            # Обычно значит, что владелица ещё не нажала /start у бота
            log.warning("Не удалось отправить заявку владельцу %s: %s", owner_id, e)
            continue
        db.save_owner_msg(config.db_path, req["id"], owner_id, msg.message_id)
        delivered += 1
        if req["photos"]:
            try:
                await bot.send_media_group(
                    owner_id,
                    [InputMediaPhoto(media=f) for f in req["photos"]],
                    reply_parameters=ReplyParameters(message_id=msg.message_id),
                )
            except TelegramAPIError as e:
                log.warning("Не удалось отправить фото владельцу %s: %s", owner_id, e)
    return delivered


async def refresh_owner_messages(bot: Bot, config: Config, request_id: int) -> None:
    """Обновляет статус и кнопки заявки у всех владелиц (чтобы не нажали дважды)."""
    req = db.get_request(config.db_path, request_id)
    if not req:
        return
    text = render.request_text(req)
    kb = owner_kb(req)
    for owner_id, message_id in db.get_owner_msgs(config.db_path, request_id):
        try:
            await bot.edit_message_text(
                text, chat_id=owner_id, message_id=message_id, reply_markup=kb
            )
        except TelegramBadRequest:
            pass  # «message is not modified» и т.п. — не страшно
        except TelegramAPIError as e:
            log.warning("Не удалось обновить заявку у владельца %s: %s", owner_id, e)


async def notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except TelegramAPIError as e:
        log.warning("Не удалось написать пользователю %s: %s", user_id, e)
        return False
