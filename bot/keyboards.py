from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from . import content, texts
from .forms import Step

# Цвета кнопок в Telegram: "primary" — синий, "success" — зелёный,
# "danger" — красный, None — стандартный.
PRIMARY, SUCCESS, DANGER = "primary", "success", "danger"


def _btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data, style=style)


def _markup(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def main_reply_kb(is_owner: bool = False) -> ReplyKeyboardMarkup:
    """Постоянная клавиатура под полем ввода. Чтобы добавить кнопку, допиши её в ряд
    (по две в ряд) и добавь обработчик по тексту в bot/handlers/user.py."""
    def b(text: str, style: str | None = None) -> KeyboardButton:
        return KeyboardButton(text=text, style=style)

    rows = [
        [b(texts.BTN_STICKERS, PRIMARY), b(texts.BTN_EMOJI, SUCCESS)],
        [b(texts.BTN_PAID, DANGER), b(texts.BTN_QUESTION, PRIMARY)],
        [b(texts.BTN_RELOAD)],
    ]
    if is_owner:
        rows.append([b(texts.BTN_ADMIN, SUCCESS)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_menu_kb() -> InlineKeyboardMarkup:
    """Панель владелиц: какой текст менять."""
    return _markup(*[[_btn(item.title, f"a:sel:{key}", PRIMARY)] for key, item in content.ITEMS.items()])


def admin_item_kb(key: str) -> InlineKeyboardMarkup:
    return _markup(
        [_btn("Изменить текст", f"a:edit:{key}", SUCCESS)],
        [_btn("Вернуть стандартный", f"a:reset:{key}", DANGER)],
        [_btn("Назад", "a:menu")],
    )


def subscribe_kb(url: str) -> InlineKeyboardMarkup:
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text="Подписаться на канал", url=url, style=PRIMARY)])
    rows.append([_btn("Я подписался", "sub:check", SUCCESS)])
    return _markup(*rows)


def cancel_menu() -> InlineKeyboardMarkup:
    return _markup([_btn("Отмена", "menu:cancel", DANGER)])


def step_kb(idx: int, step: Step) -> InlineKeyboardMarkup:
    """Кнопки под вопросом анкеты: варианты ответа, «Пропустить», «Отмена»."""
    rows: list[list[InlineKeyboardButton]] = []
    if step.options:
        rows.append([_btn(o, f"ans:{idx}:{i}", PRIMARY) for i, o in enumerate(step.options)])
    if step.skippable:
        rows.append([_btn("Пропустить", f"skip:{idx}")])
    rows.append([_btn("Отмена", "menu:cancel", DANGER)])
    return _markup(*rows)


def submit_kb() -> InlineKeyboardMarkup:
    return _markup(
        [_btn("Отправить анкету", "form:submit", SUCCESS)],
        [_btn("Отмена", "menu:cancel", DANGER)],
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
