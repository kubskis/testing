from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Запрос стикеров", callback_data="req:stickers")
    kb.button(text="Запрос эмодзи", callback_data="req:emoji")
    kb.button(text="Платные услуги", callback_data="menu:paid")
    kb.button(text="Задать вопрос", callback_data="req:question")
    # Сюда можно добавлять новые кнопки (по две в ряд):
    # kb.button(text="Портфолио", callback_data="menu:portfolio")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔄 Перезагрузить меню", callback_data="menu:reload"))
    return kb.as_markup()


def back_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="menu:reload")
    return kb.as_markup()


def cancel_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data="menu:reload")
    return kb.as_markup()


def owner_request_kb(user_id: int, request_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Ответить", callback_data=f"reply:{user_id}:{request_id}")
    kb.button(text="✅ Готово", callback_data=f"done:{request_id}")
    kb.adjust(2)
    return kb.as_markup()
