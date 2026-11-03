import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonCommands

from . import db
from .config import load_config
from .handlers import owner, user


def build_dispatcher(config) -> Dispatcher:
    # SimpleEventIsolation: сообщения одного человека обрабатываются по очереди
    # (иначе при отправке альбома из 3 фото часть фото могла бы потеряться).
    dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    dp["config"] = config  # доступен в хендлерах как аргумент `config`

    # Порядок важен: сначала меню/анкеты, потом панель владелиц, в конце — запасной хендлер
    dp.include_router(user.router)
    dp.include_router(owner.router)
    dp.include_router(user.fallback_router)
    return dp


async def setup_menu(bot: Bot, config) -> None:
    """Кнопка «Меню» рядом с полем ввода и список команд."""
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть меню"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    # Владелицам дополнительно — список открытых заявок
    for owner_id in config.owner_ids:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Открыть меню"),
                    BotCommand(command="queue", description="Открытые заявки"),
                    BotCommand(command="cancel", description="Отменить текущее действие"),
                ],
                scope=BotCommandScopeChat(chat_id=owner_id),
            )
        except TelegramAPIError:
            pass  # владелица ещё не написала боту — команды появятся после её /start


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    db.init_db(config.db_path)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(config)

    await setup_menu(bot, config)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
