"""Админ-панель для владелиц: смена текстов приветствия, анкет и платных услуг."""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import content, texts
from ..config import Config
from ..keyboards import admin_item_kb, admin_menu_kb

router = Router()
log = logging.getLogger(__name__)

PANEL_TEXT = (
    "<b>Админ-панель</b>\n"
    "Выбери, какой текст хочешь изменить.\n\n"
    "Фото для приветствия меняется командой /setwelcome."
)


class AdminEdit(StatesGroup):
    waiting = State()   # ждём новый текст


def _is_owner(user_id: int, config: Config) -> bool:
    return user_id in config.owner_ids


def _item_text(config: Config, key: str) -> str:
    item = content.ITEMS[key]
    status = "изменён вами" if content.is_custom(config.db_path, key) else "стандартный"
    return (
        f"<b>{item.title}</b> ({status})\n"
        f"<i>{item.hint}</i>\n"
        f"Максимум {item.max_len} символов.\n\n"
        "Сейчас текст такой:\n"
        "――――――――――\n"
        f"{content.get_text(config.db_path, key)}\n"
        "――――――――――"
    )


async def _edit_or_send(call: CallbackQuery, text: str, markup) -> None:
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await call.message.answer(text, reply_markup=markup)


@router.message(Command("admin"))
@router.message(F.text == texts.BTN_ADMIN)
async def open_panel(message: Message, state: FSMContext, config: Config) -> None:
    if not _is_owner(message.from_user.id, config):
        return
    await state.clear()
    await message.answer(PANEL_TEXT, reply_markup=admin_menu_kb())


@router.callback_query(F.data.startswith("a:"))
async def admin_callbacks(call: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not _is_owner(call.from_user.id, config):
        await call.answer("Нет доступа", show_alert=True)
        return

    _, action, *rest = call.data.split(":")
    key = rest[0] if rest else None
    if action != "menu" and key not in content.ITEMS:
        await call.answer()
        return

    if action == "menu":
        await state.clear()
        await _edit_or_send(call, PANEL_TEXT, admin_menu_kb())

    elif action == "sel":
        await state.clear()
        await _edit_or_send(call, _item_text(config, key), admin_item_kb(key))

    elif action == "edit":
        item = content.ITEMS[key]
        await state.set_state(AdminEdit.waiting)
        await state.update_data(key=key)
        await call.message.answer(
            f"Пришли новый текст для «{item.title}» одним сообщением.\n"
            f"Максимум {item.max_len} символов.\n"
            "Жирный, курсив и другое форматирование сохранятся. Премиум-эмодзи тоже: "
            "просто вставь их в сообщение, искать их ID не нужно. "
            "Telegram показывает премиум-эмодзи в сообщениях бота не всегда; "
            "если они не отобразятся, будет обычный эмодзи.\n"
            "/cancel — отмена."
        )

    elif action == "reset":
        content.reset_text(config.db_path, key)
        await _edit_or_send(call, _item_text(config, key), admin_item_kb(key))
        await call.answer("Возвращён стандартный текст")
        return

    await call.answer()


@router.message(Command("cancel"), AdminEdit.waiting)
async def cancel_edit(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено. Текст не изменён.", reply_markup=admin_menu_kb())


@router.message(AdminEdit.waiting)
async def receive_text(message: Message, state: FSMContext, config: Config) -> None:
    if not _is_owner(message.from_user.id, config):
        return
    if not message.text:
        await message.answer("Нужен именно текст. Пришли новый текст сообщением или /cancel.")
        return

    key = (await state.get_data())["key"]
    item = content.ITEMS[key]
    if len(message.text) > item.max_len:
        await message.answer(
            f"Слишком длинно: {len(message.text)} символов, максимум {item.max_len}. "
            "Сократи и пришли ещё раз."
        )
        return

    # html_text сохраняет форматирование (жирный, курсив, ссылки, премиум-эмодзи) как HTML
    previous = content.custom_text(config.db_path, key)
    content.set_text(config.db_path, key, message.html_text)
    await state.clear()
    await message.answer("Сохранено. Вот как теперь выглядит:")
    try:
        await message.answer(_item_text(config, key), reply_markup=admin_item_kb(key))
    except TelegramBadRequest as e:
        # Telegram не принял разметку: возвращаем прежний текст, чтобы бот не сломался
        log.warning("Telegram не принял новый текст %s: %s", key, e)
        if previous is None:
            content.reset_text(config.db_path, key)
        else:
            content.set_text(config.db_path, key, previous)
        await message.answer(
            "Telegram не принял этот текст, поэтому я оставил прежний. "
            "Попробуй убрать необычное форматирование или эмодзи и пришли снова.",
            reply_markup=admin_item_kb(key),
        )
