import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation

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


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    db.init_db(config.db_path)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(config)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
