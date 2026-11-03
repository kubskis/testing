import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import db, texts
from ..config import Config

router = Router()
log = logging.getLogger(__name__)


class OwnerReply(StatesGroup):
    waiting = State()


@router.callback_query(F.data.startswith("reply:"))
async def reply_start(call: CallbackQuery, state: FSMContext, config: Config) -> None:
    if call.from_user.id not in config.owner_ids:
        await call.answer("Нет доступа", show_alert=True)
        return
    _, user_id, request_id = call.data.split(":")
    await state.set_state(OwnerReply.waiting)
    await state.update_data(user_id=int(user_id), request_id=int(request_id))
    await call.message.answer(texts.OWNER_REPLY_PROMPT.format(id=request_id))
    await call.answer()


@router.callback_query(F.data.startswith("done:"))
async def mark_done(call: CallbackQuery, config: Config) -> None:
    if call.from_user.id not in config.owner_ids:
        await call.answer("Нет доступа", show_alert=True)
        return
    request_id = int(call.data.split(":")[1])
    db.set_status(config.db_path, request_id, "done")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ Заявка #{request_id} отмечена выполненной.")
    await call.answer()


@router.message(Command("cancel"), OwnerReply.waiting)
async def reply_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(OwnerReply.waiting)
async def reply_send(message: Message, state: FSMContext, bot: Bot, config: Config) -> None:
    if message.from_user.id not in config.owner_ids:
        return
    data = await state.get_data()
    user_id, request_id = data["user_id"], data["request_id"]
    await state.clear()
    try:
        await bot.send_message(user_id, f"💬 Ответ по заявке #{request_id}:")
        await message.copy_to(user_id)
    except TelegramAPIError as e:
        log.warning("Не удалось отправить ответ пользователю %s: %s", user_id, e)
        await message.answer("😔 Не удалось отправить (возможно, клиент заблокировал бота).")
        return
    db.set_status(config.db_path, request_id, "answered")
    await message.answer(f"✅ Ответ по заявке #{request_id} отправлен.")
