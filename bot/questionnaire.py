"""Анкеты. Вопросы и их порядок правятся здесь."""
from dataclasses import dataclass

FREE_LIMIT = 40          # бесплатное количество
MAX_STICKERS = 120       # обычные стикеры
MAX_ANIMATED = 50        # анимированные стикеры
MAX_EMOJI = 120          # эмодзи
MIN_PHOTOS = 3
MAX_FILES = 10
MAX_TEXT = 500           # максимум символов в одном ответе


@dataclass(frozen=True)
class Step:
    key: str
    title: str                      # как вопрос выглядит в карточке для владелиц
    prompt: str                     # что пишем клиенту
    type: str = "text"              # text / choice / count / contact
    options: tuple[str, ...] = ()   # для choice
    skip_label: str | None = None   # если задано — можно пропустить кнопкой
    max_len: int = MAX_TEXT


@dataclass(frozen=True)
class Form:
    kind: str
    name: str                       # "Запрос стикеров"
    short: str                      # "Стикеры"
    header: str                     # шапка анкеты
    steps: tuple[Step, ...]
    photos: bool = True


STICKERS = Form(
    kind="stickers",
    name="Запрос стикеров",
    short="Стикеры",
    header=(
        "🔠 Анкета 🌟🌟🌟\n"
        "🐏 на запрос стикеров.\n"
        "Перед отправкой просьба прочитать правила в закрепе канала!"
    ),
    steps=(
        Step("name", "Имя персонажа | фандом", "Имя персонажа | фандом"),
        Step("anim", "С аним/без", "С анимацией или без?", "choice", ("С анимацией", "Без анимации")),
        Step("color", "С колором/без", "С колором или без?", "choice", ("С колором", "Без колора")),
        Step(
            "count",
            "Количество стикеров",
            f"Сколько стикеров нужно? Бесплатное количество — {FREE_LIMIT} шт.\n"
            "Напиши число.",
            "count",
        ),
        Step(
            "contact",
            "Юз для связи",
            "Юз для связи. Если не хочешь указывать — нажми «Пропустить», "
            "я возьму твой юзернейм (или имя, если юзернейма нет).",
            "contact",
            skip_label="Пропустить",
        ),
        Step(
            "wishes",
            "Пожелания для стикеров",
            "Пожелания для стикеров. Если их нет — нажми «Нет пожеланий».",
            skip_label="Нет пожеланий",
        ),
    ),
)

EMOJI = Form(
    kind="emoji",
    name="Запрос эмодзи",
    short="Эмодзи",
    header=(
        "🔠 Анкета 🌟🌟🌟\n"
        "🐏 на запрос эмодзи.\n"
        "Перед отправкой просьба прочитать правила в закрепе канала!"
    ),
    steps=(
        Step("name", "Имя персонажа | фандом", "Имя персонажа | фандом"),
        Step("color", "С колором/без", "С колором или без?", "choice", ("С колором", "Без колора")),
        Step(
            "count",
            "Количество эмодзи",
            f"Сколько эмодзи нужно? Бесплатное количество — {FREE_LIMIT} шт.\n"
            "Напиши число.",
            "count",
        ),
        Step("outline", "С обводкой/без", "С обводкой или без?", "choice", ("С обводкой", "Без обводки")),
        Step(
            "contact",
            "Юз для связи",
            "Юз для связи. Если не хочешь указывать — нажми «Пропустить», "
            "я возьму твой юзернейм (или имя, если юзернейма нет).",
            "contact",
            skip_label="Пропустить",
        ),
        Step(
            "wishes",
            "Пожелания для эмодзи",
            "Пожелания для эмодзи. Если их нет — нажми «Нет пожеланий».",
            skip_label="Нет пожеланий",
        ),
    ),
)

QUESTION = Form(
    kind="question",
    name="Задать вопрос",
    short="Вопрос",
    header="❓ Вопрос владелицам",
    steps=(Step("text", "Вопрос", "Напиши свой вопрос одним сообщением.", max_len=1500),),
    photos=False,
)

FORMS: dict[str, Form] = {f.kind: f for f in (STICKERS, EMOJI, QUESTION)}

PHOTOS_PROMPT = (
    f"🎀 Обязательно добавь к анкете {MIN_PHOTOS} фото персонажа!\n"
    f"Отправь фото (минимум {MIN_PHOTOS}, максимум {MAX_FILES})."
)


def count_limit(kind: str, answers: dict) -> int:
    if kind == "emoji":
        return MAX_EMOJI
    if answers.get("anim") == "С анимацией":
        return MAX_ANIMATED
    return MAX_STICKERS
