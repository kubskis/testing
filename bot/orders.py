"""Общая логика заявок: карточки для владелиц, рассылка, обновление."""
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InputMediaDocument, InputMediaPhoto

from . import db, texts
from .config import Config
from .keyboards import owner_kb
from .questionnaire import FORMS, FREE_LIMIT

log = logging.getLogger(__name__)


def who(user_id: int, username: str | None, full_name: str) -> str:
    """Юзернейм, если он есть, иначе имя со ссылкой на профиль."""
    if username:
        return f"@{html.escape(username)}"
    return f'<a href="tg://user?id={user_id}">{html.escape(full_name)}</a>'


def auto_contact(username: str | None, full_name: str) -> str:
    """Что подставить в «Юз для связи», если человек пропустил вопрос."""
    return f"@{username}" if username else full_name


def render_card(order: dict) -> str:
    form = FORMS[order["kind"]]
    lines = [
        f"📩 <b>Заявка №{order['id']}</b> · {form.short}",
        f"Статус: {texts.STATUS_NAMES.get(order['status'], order['status'])}",
    ]
    if order.get("handled_by") and order["status"] != "pending":
        lines.append(f"Обработала: {html.escape(order['handled_by'])}")
    reason = order.get("reason")
    if order["status"] == "rejected" and reason and reason != "-":
        lines.append(f"Причина отказа: {html.escape(reason)}")
    lines.append("")

    if order["kind"] == "question":
        lines.append(html.escape(order["answers"].get("text", "")))
    else:
        lines.append(html.escape(form.header))
        for i, step in enumerate(form.steps, 1):
            answer = order["answers"].get(step.key, "—")
            line = f"{i}. {html.escape(step.title)}: <b>{html.escape(str(answer))}</b>"
            if step.type == "count" and str(answer).isdigit() and int(answer) > FREE_LIMIT:
                line += f" ⚠️ больше {FREE_LIMIT} — платно"
            lines.append(line)
        lines.append(f"🎀 Фото: {len(order['files'])} шт.")

    lines.append("")
    lines.append(f"👤 Клиент: {who(order['user_id'], order['username'], order['full_name'])}")
    return "\n".join(lines)


async def send_files(bot: Bot, chat_id: int, files: list) -> None:
    photos = [f for t, f in files if t == "photo"]
    docs = [f for t, f in files if t == "document"]
    if len(photos) == 1:
        await bot.send_photo(chat_id, photos[0])
    elif photos:
        await bot.send_media_group(chat_id, [InputMediaPhoto(media=f) for f in photos])
    if len(docs) == 1:
        await bot.send_document(chat_id, docs[0])
    elif docs:
        await bot.send_media_group(chat_id, [InputMediaDocument(media=f) for f in docs])


async def send_to_owners(bot: Bot, config: Config, order: dict) -> int:
    """Отправляет заявку всем владелицам. Возвращает, скольким дошло."""
    delivered = 0
    for owner_id in config.owner_ids:
        try:
            if order["files"]:
                await send_files(bot, owner_id, order["files"])
            msg = await bot.send_message(
                owner_id, render_card(order), reply_markup=owner_kb(order)
            )
            db.save_msg(config.db_path, order["id"], owner_id, msg.message_id)
            delivered += 1
        except TelegramAPIError as e:
            # Обычно значит, что владелица ещё не нажала /start у бота
            log.warning("Не удалось отправить заявку владельцу %s: %s", owner_id, e)
    return delivered


async def refresh_cards(bot: Bot, config: Config, order_id: int) -> None:
    """Обновляет карточку заявки у всех владелиц (статус и кнопки)."""
    order = db.get_order(config.db_path, order_id)
    if order is None:
        return
    text, kb = render_card(order), owner_kb(order)
    for owner_id, message_id in db.get_msgs(config.db_path, order_id):
        try:
            await bot.edit_message_text(
                text, chat_id=owner_id, message_id=message_id, reply_markup=kb
            )
        except TelegramBadRequest as e:
            log.info("Карточка %s/%s не обновлена: %s", owner_id, message_id, e)
        except TelegramAPIError as e:
            log.warning("Ошибка обновления карточки у %s: %s", owner_id, e)


async def notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except TelegramAPIError as e:
        log.warning("Не удалось написать клиенту %s: %s", user_id, e)
        return False
