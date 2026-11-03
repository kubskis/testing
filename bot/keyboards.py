from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .forms import Step


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


def step_kb(idx: int, step: Step) -> InlineKeyboardMarkup:
    """Кнопки под вопросом анкеты: варианты ответа, «Пропустить», «Отмена»."""
    kb = InlineKeyboardBuilder()
    for i, option in enumerate(step.options):
        kb.button(text=option, callback_data=f"ans:{idx}:{i}")
    kb.adjust(2)
    if step.skippable:
        kb.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip:{idx}"))
    kb.row(InlineKeyboardButton(text="✖️ Отмена", callback_data="menu:reload"))
    return kb.as_markup()


def submit_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📨 Отправить анкету", callback_data="form:submit")
    kb.row(InlineKeyboardButton(text="✖️ Отмена", callback_data="menu:reload"))
    return kb.as_markup()


def owner_kb(req: dict) -> InlineKeyboardMarkup | None:
    """Кнопки под заявкой у владелиц — зависят от типа и статуса заявки."""
    rid, status, kind = req["id"], req["status"], req["kind"]
    kb = InlineKeyboardBuilder()

    if kind == "question":
        if status != "pending":
            return None
        kb.button(text="💬 Ответить", callback_data=f"o:msg:{rid}")
        kb.button(text="✅ Закрыть", callback_data=f"o:close:{rid}")
        kb.button(text="❌ Отклонить", callback_data=f"o:rej:{rid}")
        kb.adjust(2, 1)
        return kb.as_markup()

    if status == "pending":
        kb.button(text="✅ Принять", callback_data=f"o:acc:{rid}")
        kb.button(text="❌ Отклонить", callback_data=f"o:rej:{rid}")
        kb.button(text="💬 Написать клиенту", callback_data=f"o:msg:{rid}")
        kb.adjust(2, 1)
    elif status == "queued":
        kb.button(text="✅ Выполнено", callback_data=f"o:done:{rid}")
        kb.button(text="❌ Отклонить", callback_data=f"o:rej:{rid}")
        kb.button(text="💬 Написать клиенту", callback_data=f"o:msg:{rid}")
        kb.adjust(2, 1)
    elif status == "done":
        # после выполнения можно отправить клиенту готовый набор
        kb.button(text="💬 Написать клиенту", callback_data=f"o:msg:{rid}")
    else:
        return None
    return kb.as_markup()
