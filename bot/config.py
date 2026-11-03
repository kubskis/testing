import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_ids: tuple[int, ...]
    owner_usernames: tuple[str, ...]
    db_path: str


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN (см. .env.example)")

    try:
        owner_ids = tuple(int(x) for x in _split(os.getenv("OWNER_IDS", "")))
    except ValueError:
        raise RuntimeError("OWNER_IDS должен содержать числовые Telegram ID через запятую")
    if not owner_ids:
        raise RuntimeError("Не задан OWNER_IDS (см. .env.example)")

    usernames = tuple(x.lstrip("@") for x in _split(os.getenv("OWNER_USERNAMES", "")))

    return Config(
        bot_token=token,
        owner_ids=owner_ids,
        owner_usernames=usernames,
        db_path=os.getenv("DB_PATH", "data/bot.db").strip() or "data/bot.db",
    )
