import asyncio
import logging
import re
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import db, render, services, texts
from ..config import Config
from ..forms import (
    FORMS,
    FREE_LIMIT,
    MAX_PHOTOS,
    MAX_TEXT_LEN,
    PHOTOS_REQUIRED,
    count_limit,
    extra_cost,
)
from ..keyboards import cancel_menu, main_reply_kb, step_kb, submit_kb

router = Router()
fallback_router = Router()
log = logging.getLogger(__name__)

# Альбом из 3 фото приходит тремя сообщениями одновременно — без блокировки
# они затирали бы друг друга в хранилище состояния.
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

QUESTION_MAX_LEN = 1500


class Form(StatesGroup):
    answering = State()   # идёт анкета (стикеры / эмодзи)
    photos = State()      # ждём фото персонажа
    question = State()    # ждём текст вопроса


async def send_welcome(message: Message, config: Config) -> None:
    """Приветствие с фото (если владелица его загрузила) и постоянной клавиатурой."""
    kb = main_reply_kb()
    photo = db.get_setting(config.db_path, "welcome_photo")
    if photo:
        try:
            await message.answer_photo(photo, caption=texts.WELCOME, reply_markup=kb)
            return
        except TelegramAPIError as e:
            log.warning("Не удалось отправить приветственное фото: %s", e)
    await message.answer(texts.WELCOME, reply_markup=kb)


# ---------------------------------------------------------------- меню

@router.message(CommandStart())
async def start(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    await send_welcome(message, config)


@router.message(Command("cancel"), StateFilter(Form.answering, Form.photos, Form.question))
async def cancel_form(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=main_reply_kb())


@router.message(F.text == texts.BTN_RELOAD)
async def reload_menu(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    await send_welcome(message, config)


@router.callback_query(F.data == "menu:cancel")
async def cancel_inline(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await call.message.edit_text(texts.CANCELLED)
    except TelegramBadRequest:
        await call.message.answer(texts.CANCELLED, reply_markup=main_reply_kb())
    await call.answer()


@router.message(F.text == texts.BTN_PAID)
async def paid_services(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    text = texts.PAID_SERVICES
    if config.owner_usernames:
        contacts = ", ".join(f"@{u}" for u in config.owner_usernames)
        text += f"\n\nДля заказа пиши: {contacts}"
    await message.answer(text)


# ---------------------------------------------------------------- старт заявки

@router.message(F.text == texts.BTN_STICKERS)
async def request_stickers(message: Message, state: FSMContext, config: Config) -> None:
    await start_request(message, state, config, "stickers")


@router.message(F.text == texts.BTN_EMOJI)
async def request_emoji(message: Message, state: FSMContext, config: Config) -> None:
    await start_request(message, state, config, "emoji")


@router.message(F.text == texts.BTN_QUESTION)
async def request_question(message: Message, state: FSMContext, config: Config) -> None:
    await start_request(message, state, config, "question")


async def start_request(
    message: Message, state: FSMContext, config: Config, kind: str
) -> None:
    await state.clear()

    # Одна открытая заявка каждого типа на человека
    existing = db.get_active(config.db_path, message.from_user.id, kind)
    if existing:
        await message.answer(
            texts.ALREADY_ACTIVE.format(
                what=texts.KIND_WHAT[kind],
                id=existing["id"],
                status=render.status_label(existing).lower(),
            )
        )
        return

    if kind == "question":
        await state.set_state(Form.question)
        await message.answer(texts.QUESTION_PROMPT, reply_markup=cancel_menu())
        return

    await state.set_state(Form.answering)
    await state.set_data({"kind": kind, "idx": 0, "answers": {}, "photos": []})
    await message.answer(FORMS[kind].intro)
    await _ask_step(message, state)


# ---------------------------------------------------------------- шаги анкеты

async def _ask_step(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    form = FORMS[data["kind"]]
    idx = data["idx"]
    total = len(form.steps) + 1  # +1 — шаг с фото

    if idx >= len(form.steps):
        await state.set_state(Form.photos)
        await message.answer(
            texts.PHOTOS_PROMPT.format(n_step=total, total=total, need=PHOTOS_REQUIRED),
            reply_markup=cancel_menu(),
        )
        return

    step = form.steps[idx]
    limit = count_limit(data["kind"], data["answers"])
    prompt = step.prompt.format(free=FREE_LIMIT, limit=limit)
    await message.answer(
        f"<b>Вопрос {idx + 1} из {total}</b>\n{prompt}", reply_markup=step_kb(idx, step)
    )


async def _save_and_next(message: Message, state: FSMContext, value) -> None:
    data = await state.get_data()
    step = FORMS[data["kind"]].steps[data["idx"]]
    answers = dict(data["answers"])
    answers[step.key] = value
    await state.update_data(answers=answers, idx=data["idx"] + 1)
    await _ask_step(message, state)


@router.callback_query(Form.answering, F.data.startswith("ans:"))
async def on_choice(call: CallbackQuery, state: FSMContext) -> None:
    _, idx, opt = call.data.split(":")
    idx, opt = int(idx), int(opt)
    async with _locks[call.from_user.id]:
        data = await state.get_data()
        if data.get("idx") != idx:
            await call.answer("Этот вопрос уже пройден")
            return
        step = FORMS[data["kind"]].steps[idx]
        if step.type != "choice" or opt >= len(step.options):
            await call.answer()
            return
        value = step.options[opt]
        try:
            await call.message.edit_text(f"{call.message.html_text}\n\n<b>Ответ: {value}</b>")
        except TelegramBadRequest:
            pass
        await call.answer()
        await _save_and_next(call.message, state, value)


@router.callback_query(Form.answering, F.data.startswith("skip:"))
async def on_skip(call: CallbackQuery, state: FSMContext) -> None:
    idx = int(call.data.split(":")[1])
    async with _locks[call.from_user.id]:
        data = await state.get_data()
        if data.get("idx") != idx:
            await call.answer("Этот вопрос уже пройден")
            return
        step = FORMS[data["kind"]].steps[idx]
        if not step.skippable:
            await call.answer()
            return
        try:
            await call.message.edit_text(f"{call.message.html_text}\n\n<i>Пропущено</i>")
        except TelegramBadRequest:
            pass
        await call.answer()
        await _save_and_next(call.message, state, None)


@router.message(Form.answering)
async def on_answer(message: Message, state: FSMContext) -> None:
    async with _locks[message.from_user.id]:
        data = await state.get_data()
        idx = data.get("idx", 0)
        step = FORMS[data["kind"]].steps[idx]

        if step.type == "choice":
            await message.answer("Выбери вариант кнопкой под вопросом.")
            return

        text = (message.text or "").strip()
        if not text:
            await message.answer("Ответь, пожалуйста, текстом.")
            return
        if len(text) > MAX_TEXT_LEN:
            await message.answer(f"Слишком длинно, максимум {MAX_TEXT_LEN} символов.")
            return

        value = text
        if step.type == "count":
            limit = count_limit(data["kind"], data["answers"])
            if not re.fullmatch(r"\d{1,4}", text) or not 1 <= int(text) <= limit:
                await message.answer(f"Напиши число от 1 до {limit}.")
                return
            value = int(text)
            cost = extra_cost(value)
            if cost:
                await message.answer(
                    f"Сверх {FREE_LIMIT} шт. доплата составит {cost}⭐/{cost}₽."
                )

        await _save_and_next(message, state, value)


# ---------------------------------------------------------------- фото и отправка

@router.message(Form.photos, F.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
    async with _locks[message.from_user.id]:
        data = await state.get_data()
        photos = list(data.get("photos", []))
        if len(photos) >= MAX_PHOTOS:
            return
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)
        n = len(photos)

        if n < PHOTOS_REQUIRED:
            await message.answer(
                texts.PHOTO_PROGRESS.format(n=n, need=PHOTOS_REQUIRED, left=PHOTOS_REQUIRED - n)
            )
        elif n == PHOTOS_REQUIRED:
            await message.answer(texts.PHOTO_ENOUGH.format(n=n), reply_markup=submit_kb())


@router.message(Form.photos)
async def on_photo_wrong(message: Message) -> None:
    await message.answer("Пришли фото персонажа (именно как фото, не как файл).")


@router.callback_query(Form.photos, F.data == "form:submit")
async def submit_form(call: CallbackQuery, state: FSMContext, bot: Bot, config: Config) -> None:
    async with _locks[call.from_user.id]:
        data = await state.get_data()
        photos = data.get("photos", [])
        if len(photos) < PHOTOS_REQUIRED:
            await call.answer(f"Нужно минимум {PHOTOS_REQUIRED} фото", show_alert=True)
            return
        user = call.from_user
        req_id = db.create_request(
            config.db_path, user.id, user.username, user.full_name,
            data["kind"], data["answers"], photos,
        )
        await state.clear()
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await _finish(call.message, bot, config, req_id, texts.SUBMITTED, data["kind"], user.id)


# ---------------------------------------------------------------- вопрос

@router.message(Form.question)
async def receive_question(
    message: Message, state: FSMContext, bot: Bot, config: Config
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Напиши вопрос текстом.")
        return
    if len(text) > QUESTION_MAX_LEN:
        await message.answer(f"Слишком длинно, максимум {QUESTION_MAX_LEN} символов.")
        return
    user = message.from_user
    async with _locks[user.id]:
        req_id = db.create_request(
            config.db_path, user.id, user.username, user.full_name,
            "question", {"question": text}, [],
        )
        await state.clear()
    await _finish(message, bot, config, req_id, texts.QUESTION_SUBMITTED, "question", user.id)


async def _finish(
    message: Message, bot: Bot, config: Config,
    req_id: int | None, ok_text: str, kind: str, user_id: int,
) -> None:
    """Отправляет готовую заявку владелицам и отвечает клиенту."""
    if req_id is None:  # успели подать параллельно
        existing = db.get_active(config.db_path, user_id, kind)
        if existing:
            await message.answer(
                texts.ALREADY_ACTIVE.format(
                    what=texts.KIND_WHAT[kind],
                    id=existing["id"],
                    status=render.status_label(existing).lower(),
                ),
            )
        return

    req = db.get_request(config.db_path, req_id)
    if await services.notify_owners(bot, config, req) == 0:
        db.delete_request(config.db_path, req_id)  # чтобы клиент мог попробовать снова
        await message.answer(texts.SEND_FAILED)
        return
    await message.answer(ok_text.format(id=req_id))


@fallback_router.message(StateFilter(None))
async def fallback(message: Message) -> None:
    # Заодно возвращаем клавиатуру тем, у кого она пропала
    await message.answer(texts.WELCOME, reply_markup=main_reply_kb())
