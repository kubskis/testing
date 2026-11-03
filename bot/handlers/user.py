import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import db, texts
from ..config import Config
from ..keyboards import back_menu, cancel_menu, main_menu, owner_request_kb

router = Router()
fallback_router = Router()
log = logging.getLogger(__name__)


class RequestForm(StatesGroup):
    waiting = State()


async def _show(call: CallbackQuery, text: str, markup) -> None:
    """Редактирует сообщение с кнопками; если нельзя — отправляет новое."""
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await call.message.answer(text, reply_markup=markup)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.WELCOME, reply_markup=main_menu())


@router.callback_query(F.data == "menu:reload")
async def reload_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show(call, texts.WELCOME, main_menu())
    await call.answer("Меню обновлено")


@router.callback_query(F.data == "menu:paid")
async def paid_services(call: CallbackQuery, config: Config) -> None:
    text = texts.PAID_SERVICES
    if config.owner_usernames:
        contacts = ", ".join(f"@{u}" for u in config.owner_usernames)
        text += f"\n\nДля заказа пиши: {contacts}"
    await _show(call, text, back_menu())
    await call.answer()


@router.callback_query(F.data.startswith("req:"))
async def start_request(call: CallbackQuery, state: FSMContext) -> None:
    kind = call.data.split(":", 1)[1]
    if kind not in texts.PROMPTS:
        await call.answer()
        return
    await state.set_state(RequestForm.waiting)
    await state.update_data(kind=kind)
    await _show(call, texts.PROMPTS[kind], cancel_menu())
    await call.answer()


@router.message(RequestForm.waiting)
async def receive_request(
    message: Message, state: FSMContext, bot: Bot, config: Config
) -> None:
    data = await state.get_data()
    kind = data.get("kind", "question")
    await state.clear()

    user = message.from_user
    text = message.text or message.caption or ""
    request_id = db.add_request(
        config.db_path, user.id, user.username, user.full_name, kind, text
    )

    username = f"@{user.username}" if user.username else "без юзернейма"
    header = (
        f"📩 <b>Новая заявка #{request_id}</b>\n"
        f"Тип: {texts.KIND_TITLES[kind]}\n"
        f"От: {html.escape(user.full_name)} ({html.escape(username)})\n"
        f"ID: <code>{user.id}</code>"
    )
    delivered = 0
    for owner_id in config.owner_ids:
        try:
            await bot.send_message(
                owner_id, header, reply_markup=owner_request_kb(user.id, request_id)
            )
            await message.copy_to(owner_id)
            delivered += 1
        except TelegramAPIError as e:
            # Обычно значит, что владелица ещё не нажала /start у бота
            log.warning("Не удалось отправить заявку владельцу %s: %s", owner_id, e)

    if delivered == 0:
        await message.answer("😔 Не получилось отправить заявку, попробуй позже.")
        return
    await message.answer(texts.REQUEST_SENT.format(id=request_id), reply_markup=main_menu())


@fallback_router.message(StateFilter(None))
async def fallback(message: Message) -> None:
    await message.answer(texts.WELCOME, reply_markup=main_menu())
