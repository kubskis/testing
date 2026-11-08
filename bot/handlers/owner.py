import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import db, render, services, texts
from ..config import Config
from ..filters import IsOwner

router = Router()
# Все сообщения этого роутера — только от владелиц (остальным он просто не отвечает)
router.message.filter(IsOwner())
log = logging.getLogger(__name__)

NO_REASON = {"-", "—", "–"}


class OwnerAction(StatesGroup):
    reject = State()    # ждём причину отказа
    message = State()   # ждём сообщение клиенту


def _is_owner(user_id: int, config: Config) -> bool:
    return user_id in config.owner_ids


async def _stale(call: CallbackQuery, bot: Bot, config: Config, req: dict) -> None:
    """Кто-то уже обработал заявку — показываем актуальный статус."""
    await call.answer(f"Заявка уже: {render.status_label(req)}", show_alert=True)
    await services.refresh_owner_messages(bot, config, req["id"])


@router.callback_query(F.data.startswith("o:"))
async def owner_action(
    call: CallbackQuery, state: FSMContext, bot: Bot, config: Config
) -> None:
    if not _is_owner(call.from_user.id, config):
        await call.answer("Нет доступа", show_alert=True)
        return

    _, action, raw_id = call.data.split(":")
    req = db.get_request(config.db_path, int(raw_id))
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return
    rid, kind, status = req["id"], req["kind"], req["status"]
    is_open = status in db.ACTIVE

    if action == "acc":
        if status != "pending" or kind == "question":
            await _stale(call, bot, config, req)
            return
        db.set_status(config.db_path, rid, "queued")
        req = db.get_request(config.db_path, rid)
        pos = db.queue_position(config.db_path, req)
        sent = await services.notify_user(
            bot, req["user_id"], texts.ACCEPTED.format(id=rid, pos=pos)
        )
        await services.refresh_owner_messages(bot, config, rid)
        await call.answer("Принято" + ("" if sent else " (клиенту не доставлено)"))

    elif action in ("done", "close"):
        if not is_open or (kind != "question" and status != "queued"):
            await _stale(call, bot, config, req)
            return
        db.set_status(config.db_path, rid, "done")
        text = texts.QUESTION_CLOSED if kind == "question" else texts.DONE
        sent = await services.notify_user(bot, req["user_id"], text.format(id=rid))
        await services.refresh_owner_messages(bot, config, rid)
        await call.answer("Готово" + ("" if sent else " (клиенту не доставлено)"))

    elif action == "rej":
        if not is_open:
            await _stale(call, bot, config, req)
            return
        await state.set_state(OwnerAction.reject)
        await state.update_data(request_id=rid)
        await call.message.answer(texts.REJECT_PROMPT.format(id=rid))
        await call.answer()

    elif action == "msg":
        if status == "rejected" or (kind == "question" and status != "pending"):
            await _stale(call, bot, config, req)
            return
        await state.set_state(OwnerAction.message)
        await state.update_data(request_id=rid)
        await call.message.answer(texts.REPLY_PROMPT.format(id=rid))
        await call.answer()

    else:
        await call.answer()


@router.message(Command("cancel"), OwnerAction.reject)
@router.message(Command("cancel"), OwnerAction.message)
async def cancel_action(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(OwnerAction.reject)
async def reject_reason(message: Message, state: FSMContext, bot: Bot, config: Config) -> None:
    if not _is_owner(message.from_user.id, config):
        return
    if not message.text:
        await message.answer("Напиши причину текстом или отправь <code>-</code> (без причины).")
        return

    rid = (await state.get_data())["request_id"]
    await state.clear()
    req = db.get_request(config.db_path, rid)
    if not req or req["status"] not in db.ACTIVE:
        await message.answer("Заявка уже закрыта другим владельцем.")
        return

    text = message.text.strip()
    reason = None if text in NO_REASON else text
    db.set_status(config.db_path, rid, "rejected", reason)

    user_text = texts.REJECTED.format(id=rid)
    if reason:
        user_text += texts.REJECTED_REASON.format(reason=html.escape(reason))
    sent = await services.notify_user(bot, req["user_id"], user_text)
    await services.refresh_owner_messages(bot, config, rid)
    await message.answer(
        f"Заявка #{rid} отклонена"
        + (f" (причина: {html.escape(reason)})" if reason else " без причины")
        + ("." if sent else ". Клиенту сообщение не доставлено.")
    )


@router.message(OwnerAction.message)
async def send_to_client(message: Message, state: FSMContext, bot: Bot, config: Config) -> None:
    if not _is_owner(message.from_user.id, config):
        return
    rid = (await state.get_data())["request_id"]
    await state.clear()
    req = db.get_request(config.db_path, rid)
    if not req:
        await message.answer("Заявка не найдена.")
        return
    try:
        await bot.send_message(req["user_id"], texts.OWNER_MESSAGE.format(id=rid))
        await message.copy_to(req["user_id"])
    except TelegramAPIError as e:
        log.warning("Не удалось отправить сообщение пользователю %s: %s", req["user_id"], e)
        await message.answer("Не удалось отправить (возможно, клиент заблокировал бота).")
        return

    # Ответ на вопрос закрывает его
    if req["kind"] == "question" and req["status"] == "pending":
        db.set_status(config.db_path, rid, "done")
        await services.refresh_owner_messages(bot, config, rid)
    await message.answer(f"Сообщение по заявке #{rid} отправлено.")


@router.message(Command("queue"))
async def show_queue(message: Message, config: Config) -> None:
    if not _is_owner(message.from_user.id, config):
        return
    rows = db.list_active(config.db_path)
    if not rows:
        await message.answer("Активных заявок нет.")
        return
    lines = ["<b>Открытые заявки:</b>"]
    for r in rows:
        lines.append(
            f"#{r['id']} · {texts.KIND_TITLES[r['kind']]} · {render.status_label(r)} · "
            f"{html.escape(render.user_label(r))}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("setwelcome"))
async def set_welcome(message: Message, config: Config) -> None:
    """Фото для приветствия: пришли фото с подписью /setwelcome
    или ответь командой /setwelcome на уже отправленное фото."""
    if not _is_owner(message.from_user.id, config):
        return
    source = message if message.photo else message.reply_to_message
    if not source or not source.photo:
        await message.answer(
            "Пришли фото с подписью <code>/setwelcome</code> "
            "или ответь командой /setwelcome на фото."
        )
        return
    db.set_setting(config.db_path, "welcome_photo", source.photo[-1].file_id)
    await message.answer("Приветственное фото сохранено. Проверь: /start")


@router.message(Command("clearwelcome"))
async def clear_welcome(message: Message, config: Config) -> None:
    if not _is_owner(message.from_user.id, config):
        return
    db.set_setting(config.db_path, "welcome_photo", None)
    await message.answer("Приветственное фото убрано.")
