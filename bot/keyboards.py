from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .forms import Step

# Цвета кнопок в Telegram: "primary" — синий, "success" — зелёный,
# "danger" — красный, None — стандартный.
PRIMARY, SUCCESS, DANGER = "primary", "success", "danger"


def _btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data, style=style)


def _markup(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def main_menu() -> InlineKeyboardMarkup:
    # Чтобы добавить кнопку, допиши её в нужный ряд (по две в ряд).
    return _markup(
        [_btn("Запрос стикеров", "req:stickers", PRIMARY),
         _btn("Запрос эмодзи", "req:emoji", SUCCESS)],
        [_btn("Платные услуги", "menu:paid", DANGER),
         _btn("Задать вопрос", "req:question", PRIMARY)],
        [_btn("Перезагрузить меню", "menu:reload")],
    )


def back_menu() -> InlineKeyboardMarkup:
    return _markup([_btn("Назад", "menu:reload")])


def cancel_menu() -> InlineKeyboardMarkup:
    return _markup([_btn("Отмена", "menu:reload", DANGER)])


def step_kb(idx: int, step: Step) -> InlineKeyboardMarkup:
    """Кнопки под вопросом анкеты: варианты ответа, «Пропустить», «Отмена»."""
    rows: list[list[InlineKeyboardButton]] = []
    if step.options:
        rows.append([_btn(o, f"ans:{idx}:{i}", PRIMARY) for i, o in enumerate(step.options)])
    if step.skippable:
        rows.append([_btn("Пропустить", f"skip:{idx}")])
    rows.append([_btn("Отмена", "menu:reload", DANGER)])
    return _markup(*rows)


def submit_kb() -> InlineKeyboardMarkup:
    return _markup(
        [_btn("Отправить анкету", "form:submit", SUCCESS)],
        [_btn("Отмена", "menu:reload", DANGER)],
    )


def owner_kb(req: dict) -> InlineKeyboardMarkup | None:
    """Кнопки под заявкой у владелиц — зависят от типа и статуса заявки."""
    rid, status, kind = req["id"], req["status"], req["kind"]
    write = _btn("Написать клиенту", f"o:msg:{rid}", PRIMARY)
    reject = _btn("Отклонить", f"o:rej:{rid}", DANGER)

    if kind == "question":
        if status != "pending":
            return None
        return _markup(
            [_btn("Ответить", f"o:msg:{rid}", PRIMARY),
             _btn("Закрыть", f"o:close:{rid}", SUCCESS)],
            [reject],
        )
    if status == "pending":
        return _markup([_btn("Принять", f"o:acc:{rid}", SUCCESS), reject], [write])
    if status == "queued":
        return _markup([_btn("Выполнено", f"o:done:{rid}", SUCCESS), reject], [write])
    if status == "done":
        # после выполнения можно отправить клиенту готовый набор
        return _markup([write])
    return None
