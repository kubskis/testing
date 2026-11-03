"""Отправка сообщений владелицам и клиентам (общая часть для хендлеров)."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputMediaPhoto, ReplyParameters

from . import db, render
from .config import Config
from .keyboards import owner_kb

log = logging.getLogger(__name__)

CAPTION_LIMIT = 1024  # максимум символов в подписи к фото в Telegram


async def notify_owners(bot: Bot, config: Config, req: dict) -> int:
    """Отправляет заявку всем владелицам. Возвращает, скольким дошло.

    Если есть фото и текст заявки влезает в подпись, заявка приходит одним
    альбомом: фото с текстом заявки в подписи. Кнопки Telegram не умеет
    крепить к альбому, поэтому они идут коротким сообщением сразу под ним.
    """
    text = render.request_text(req)
    photos = req["photos"]
    delivered = 0
    for owner_id in config.owner_ids:
        try:
            if photos and len(text) <= CAPTION_LIMIT:
                album = await bot.send_media_group(
                    owner_id,
                    [
                        InputMediaPhoto(media=f, caption=text if i == 0 else None)
                        for i, f in enumerate(photos)
                    ],
                )
                caption_id = album[0].message_id
                controls = await bot.send_message(
                    owner_id,
                    render.controls_text(req),
                    reply_markup=owner_kb(req),
                    reply_parameters=ReplyParameters(message_id=caption_id),
                )
                db.save_owner_msg(
                    config.db_path, req["id"], owner_id, controls.message_id, caption_id
                )
            else:
                # Вопрос без фото, либо текст слишком длинный для подписи
                msg = await bot.send_message(owner_id, text, reply_markup=owner_kb(req))
                db.save_owner_msg(config.db_path, req["id"], owner_id, msg.message_id)
                if photos:
                    await bot.send_media_group(
                        owner_id,
                        [InputMediaPhoto(media=f) for f in photos],
                        reply_parameters=ReplyParameters(message_id=msg.message_id),
                    )
            delivered += 1
        except TelegramAPIError as e:
            # Обычно значит, что владелица ещё не нажала /start у бота
            log.warning("Не удалось отправить заявку владельцу %s: %s", owner_id, e)
    return delivered


async def refresh_owner_messages(bot: Bot, config: Config, request_id: int) -> None:
    """Обновляет статус и кнопки заявки у всех владелиц (чтобы не нажали дважды)."""
    req = db.get_request(config.db_path, request_id)
    if not req:
        return
    text = render.request_text(req)
    kb = owner_kb(req)
    for owner_id, message_id, caption_id in db.get_owner_msgs(config.db_path, request_id):
        if caption_id:
            await _quiet(bot.edit_message_caption(
                chat_id=owner_id, message_id=caption_id, caption=text
            ), owner_id)
            await _quiet(bot.edit_message_text(
                render.controls_text(req),
                chat_id=owner_id, message_id=message_id, reply_markup=kb,
            ), owner_id)
        else:
            await _quiet(bot.edit_message_text(
                text, chat_id=owner_id, message_id=message_id, reply_markup=kb
            ), owner_id)


async def _quiet(coro, owner_id: int) -> None:
    try:
        await coro
    except TelegramAPIError as e:
        # «message is not modified» и подобное — не страшно
        log.info("Не удалось обновить сообщение у владельца %s: %s", owner_id, e)


async def notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except TelegramAPIError as e:
        log.warning("Не удалось написать пользователю %s: %s", user_id, e)
        return False
