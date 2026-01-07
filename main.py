import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8526419531:AAHEYXxzCgVZ2orcBuoY6Ce-WwT0dWuRwR0"

ADMINS = [
    959984030,
    6769475417,
    1034179881,
    7958069580
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

waiting_users = {}
reply_map = {}


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 FAQ", callback_data="faq")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать в поддержку RP проекта!\n\n"
        "Выберите нужный раздел 👇",
        reply_markup=main_menu()
    )


@dp.callback_query(lambda c: c.data == "faq")
async def faq(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📘 *FAQ*\n\n"
        "❓ Как вступить?\n"
        "— Подай заявку в разделе набора\n\n"
        "❓ Где правила?\n"
        "— Ознакомься с правилами сервера\n\n"
        "Если ответа нет — напиши в поддержку 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
        ])
    )


@dp.callback_query(lambda c: c.data == "support")
async def support(callback: types.CallbackQuery):
    waiting_users[callback.from_user.id] = True
    await callback.message.edit_text(
        "🆘 Напиши свой вопрос одним сообщением.\n"
        "Администрация ответит тебе здесь.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back")]]
        )
    )


@dp.callback_query(lambda c: c.data == "back")
async def back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Главное меню 👇",
        reply_markup=main_menu()
    )


@dp.message()
async def messages(message: types.Message):
    user_id = message.from_user.id

    if user_id in ADMINS and message.reply_to_message:
        replied_id = message.reply_to_message.message_id
        if replied_id in reply_map:
            await bot.send_message(
                reply_map[replied_id],
                f"📩 Ответ администрации:\n\n{message.text}"
            )
        return

    if waiting_users.get(user_id):
        waiting_users.pop(user_id)

        text = (
            "📨 Новый вопрос в поддержку\n\n"
            f"👤 @{message.from_user.username}\n"
            f"🆔 {user_id}\n\n"
            f"{message.text}"
        )

        for admin in ADMINS:
            sent = await bot.send_message(admin, text)
            reply_map[sent.message_id] = user_id

        await message.answer("✅ Вопрос отправлен администрации.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

