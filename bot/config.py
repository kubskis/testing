import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_ids: tuple[int, ...]
    owner_usernames: tuple[str, ...]
    db_path: str
    required_channel: str   # канал, на который нужно быть подписанным (пусто — проверка выключена)
    channel_url: str        # ссылка на канал для кнопки «Подписаться»


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_channel(raw: str, url_override: str = "") -> tuple[str, str]:
    """'@name', 't.me/name' или числовой id -> (идентификатор для Telegram, ссылка)."""
    raw = raw.strip()
    if not raw:
        return "", ""
    m = re.search(r"t\.me/(?:s/)?([A-Za-z0-9_]+)", raw)
    if m:
        name = m.group(1)
    elif re.fullmatch(r"-?\d+", raw):
        return raw, url_override.strip()   # у закрытого канала ссылку нужно задать отдельно
    else:
        name = raw.lstrip("@")
    return f"@{name}", url_override.strip() or f"https://t.me/{name}"


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

    # По умолчанию нужна подписка на @s1ren_33. REQUIRED_CHANNEL= (пусто) — выключить проверку.
    channel, channel_url = parse_channel(
        os.getenv("REQUIRED_CHANNEL", "@s1ren_33"), os.getenv("CHANNEL_URL", "")
    )

    return Config(
        bot_token=token,
        owner_ids=owner_ids,
        owner_usernames=usernames,
        db_path=os.getenv("DB_PATH", "data/bot.db").strip() or "data/bot.db",
        required_channel=channel,
        channel_url=channel_url,
    )
