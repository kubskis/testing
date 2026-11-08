"""Тексты, которые владелицы могут менять через админ-панель (/admin).

Изменённый текст хранится в базе. Пока владелица ничего не меняла (или нажала
«Вернуть стандартный»), используется текст по умолчанию из texts.py / forms.py.
Без зависимостей от aiogram.
"""
from dataclasses import dataclass

from . import db, texts
from .forms import FORMS


@dataclass(frozen=True)
class Item:
    key: str
    title: str      # название в админ-панели
    max_len: int    # максимум символов (подпись к фото в Telegram — 1024)
    hint: str       # пояснение, где виден текст


ITEMS: dict[str, Item] = {
    "welcome": Item(
        "welcome", "Приветствие", 900,
        "Показывается после /start. Если загружено приветственное фото, текст идёт подписью к нему.",
    ),
    "stickers_intro": Item(
        "stickers_intro", "Анкета на стикеры", 900,
        "Показывается, когда человек нажимает «Запрос стикеров». Идёт подписью к картинке.",
    ),
    "emoji_intro": Item(
        "emoji_intro", "Анкета на эмодзи", 900,
        "Показывается, когда человек нажимает «Запрос эмодзи». Идёт подписью к картинке.",
    ),
    "paid": Item(
        "paid", "Платные услуги", 3500,
        "Показывается по кнопке «Платные услуги».",
    ),
}

_PREFIX = "text_"


def default_text(key: str) -> str:
    return {
        "welcome": texts.WELCOME,
        "stickers_intro": FORMS["stickers"].intro,
        "emoji_intro": FORMS["emoji"].intro,
        "paid": texts.PAID_SERVICES,
    }[key]


def get_text(path: str, key: str) -> str:
    return db.get_setting(path, _PREFIX + key) or default_text(key)


def custom_text(path: str, key: str) -> str | None:
    """Текст, сохранённый владелицами, либо None, если используется стандартный."""
    return db.get_setting(path, _PREFIX + key)


def is_custom(path: str, key: str) -> bool:
    return db.get_setting(path, _PREFIX + key) is not None


def set_text(path: str, key: str, html_text: str) -> None:
    db.set_setting(path, _PREFIX + key, html_text)


def reset_text(path: str, key: str) -> None:
    db.set_setting(path, _PREFIX + key, None)
