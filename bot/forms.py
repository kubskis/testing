"""Анкеты на стикеры и эмодзи. Вопросы, лимиты и цены правятся здесь."""
import math
from dataclasses import dataclass

FREE_LIMIT = 40          # бесплатное количество
EXTRA_STEP = 10          # докупается пачками по 10 шт.
EXTRA_PRICE = 15         # цена за пачку: 15⭐ / 15₽
PHOTOS_REQUIRED = 3
MAX_PHOTOS = 10          # максимум фото в одной заявке (лимит альбома Telegram)
MAX_TEXT_LEN = 500       # максимальная длина текстового ответа

ANIM_YES = "С анимацией"
ANIM_NO = "Без анимации"


@dataclass(frozen=True)
class Step:
    key: str
    label: str                    # как подписан ответ в заявке для владельцев
    prompt: str                   # вопрос клиенту ({free} и {limit} подставляются)
    type: str                     # text | choice | count | contact
    options: tuple[str, ...] = ()
    skippable: bool = False


@dataclass(frozen=True)
class Form:
    intro: str
    steps: tuple[Step, ...]


_NAME = Step(
    "name",
    "Имя персонажа | фандом",
    "Напиши <b>имя персонажа | фандом</b>\nНапример: <i>Гермиона | Гарри Поттер</i>",
    "text",
)
_COLOR = Step(
    "color", "Колор", "<b>С колором или без?</b>", "choice", ("С колором", "Без колора")
)
_COUNT = Step(
    "count",
    "Количество",
    "<b>Сколько нужно?</b> Напиши число.\n"
    "Бесплатно — до {free} шт. Сверх этого доплата: +10 шт. = 15⭐/15₽.\n"
    "Максимум: {limit} шт.",
    "count",
)
_CONTACT = Step(
    "contact",
    "Юз для связи",
    "<b>Юз для связи</b> — как с тобой связаться?\n"
    "Можно пропустить: тогда бот возьмёт твой юзернейм (или имя, если юзернейма нет).",
    "contact",
    skippable=True,
)

FORMS: dict[str, Form] = {
    "stickers": Form(
        intro=(
            "🌟 <b>Анкета на запрос стикеров</b> 🌟\n\n"
            "Перед отправкой просьба прочитать правила в закрепе канала!\n"
            "🎀 Обязательно нужно будет добавить к анкете 3 фото персонажа."
        ),
        steps=(
            _NAME,
            Step(
                "anim",
                "Анимация",
                "<b>С анимацией или без?</b>",
                "choice",
                (ANIM_YES, ANIM_NO),
            ),
            _COLOR,
            _COUNT,
            _CONTACT,
            Step(
                "wishes",
                "Пожелания",
                "<b>Пожелания для стикеров</b> — что учесть?\nМожно пропустить.",
                "text",
                skippable=True,
            ),
        ),
    ),
    "emoji": Form(
        intro=(
            "🌟 <b>Анкета на запрос эмодзи</b> 🌟\n\n"
            "Перед отправкой просьба прочитать правила в закрепе канала!\n"
            "🎀 Обязательно нужно будет добавить к анкете 3 фото персонажа."
        ),
        steps=(
            _NAME,
            _COLOR,
            _COUNT,
            Step(
                "outline",
                "Обводка",
                "<b>С обводкой или без?</b>",
                "choice",
                ("С обводкой", "Без обводки"),
            ),
            _CONTACT,
            Step(
                "wishes",
                "Пожелания",
                "<b>Пожелания для эмодзи</b> — что учесть?\nМожно пропустить.",
                "text",
                skippable=True,
            ),
        ),
    ),
}


def count_limit(kind: str, answers: dict) -> int:
    """Максимум штук: обычные стикеры — 120, анимированные — 50, эмодзи — 120."""
    if kind == "stickers" and answers.get("anim") == ANIM_YES:
        return 50
    return 120


def extra_cost(count: int) -> int:
    """Доплата за количество сверх бесплатного (в ⭐ или ₽, цена одинаковая)."""
    if count <= FREE_LIMIT:
        return 0
    return math.ceil((count - FREE_LIMIT) / EXTRA_STEP) * EXTRA_PRICE
