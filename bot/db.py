import json
import sqlite3
from contextlib import closing
from pathlib import Path

# Заявка считается «открытой», пока у неё один из этих статусов.
# Пока заявка открыта, этот же человек не может подать заявку того же типа.
ACTIVE = ("pending", "queued")

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    username      TEXT,
    full_name     TEXT,
    kind          TEXT NOT NULL,                 -- stickers / emoji / question
    answers       TEXT NOT NULL DEFAULT '{}',    -- JSON: ответы анкеты
    photos        TEXT NOT NULL DEFAULT '[]',    -- JSON: file_id фото
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending / queued / done / rejected
    reject_reason TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT
);
CREATE TABLE IF NOT EXISTS owner_msgs (
    request_id INTEGER NOT NULL,
    owner_id   INTEGER NOT NULL,
    message_id INTEGER NOT NULL,        -- сообщение с кнопками (или с текстом заявки)
    caption_id INTEGER,                 -- первое фото альбома с подписью-заявкой, если есть
    PRIMARY KEY (request_id, owner_id)
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_requests_user ON requests (user_id, kind, status);
"""

# Колонки, которых могло не быть в самой первой версии базы
_MIGRATE_COLUMNS = {
    "answers": "TEXT NOT NULL DEFAULT '{}'",
    "photos": "TEXT NOT NULL DEFAULT '[]'",
    "reject_reason": "TEXT",
    "updated_at": "TEXT",
}


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    d["answers"] = json.loads(d.get("answers") or "{}")
    d["photos"] = json.loads(d.get("photos") or "[]")
    return d


def init_db(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(path)) as conn, conn:
        conn.executescript(SCHEMA)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(requests)")}
        for name, ddl in _MIGRATE_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE requests ADD COLUMN {name} {ddl}")
        owner_cols = {r["name"] for r in conn.execute("PRAGMA table_info(owner_msgs)")}
        if "caption_id" not in owner_cols:
            conn.execute("ALTER TABLE owner_msgs ADD COLUMN caption_id INTEGER")


def get_active(path: str, user_id: int, kind: str) -> dict | None:
    q = ",".join("?" * len(ACTIVE))
    with closing(_connect(path)) as conn:
        row = conn.execute(
            f"SELECT * FROM requests WHERE user_id = ? AND kind = ? AND status IN ({q}) "
            "ORDER BY id DESC LIMIT 1",
            (user_id, kind, *ACTIVE),
        ).fetchone()
    return _row(row)


def create_request(
    path: str,
    user_id: int,
    username: str | None,
    full_name: str,
    kind: str,
    answers: dict,
    photos: list[str],
) -> int | None:
    """Создаёт заявку. Возвращает её номер, либо None, если у человека уже есть
    открытая заявка такого типа."""
    if get_active(path, user_id, kind):
        return None
    with closing(_connect(path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO requests (user_id, username, full_name, kind, answers, photos) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                username,
                full_name,
                kind,
                json.dumps(answers, ensure_ascii=False),
                json.dumps(photos),
            ),
        )
        return cur.lastrowid


def delete_request(path: str, request_id: int) -> None:
    with closing(_connect(path)) as conn, conn:
        conn.execute("DELETE FROM owner_msgs WHERE request_id = ?", (request_id,))
        conn.execute("DELETE FROM requests WHERE id = ?", (request_id,))


def get_request(path: str, request_id: int) -> dict | None:
    with closing(_connect(path)) as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    return _row(row)


def set_status(path: str, request_id: int, status: str, reason: str | None = None) -> None:
    with closing(_connect(path)) as conn, conn:
        conn.execute(
            "UPDATE requests SET status = ?, reject_reason = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (status, reason, request_id),
        )


def queue_position(path: str, request: dict) -> int:
    """Место заявки в очереди среди принятых заявок того же типа."""
    with closing(_connect(path)) as conn:
        (n,) = conn.execute(
            "SELECT COUNT(*) FROM requests WHERE kind = ? AND status = 'queued' AND id <= ?",
            (request["kind"], request["id"]),
        ).fetchone()
    return n


def list_active(path: str) -> list[dict]:
    q = ",".join("?" * len(ACTIVE))
    with closing(_connect(path)) as conn:
        rows = conn.execute(
            f"SELECT * FROM requests WHERE status IN ({q}) ORDER BY id", ACTIVE
        ).fetchall()
    return [_row(r) for r in rows]


def save_owner_msg(
    path: str, request_id: int, owner_id: int, message_id: int, caption_id: int | None = None
) -> None:
    with closing(_connect(path)) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO owner_msgs (request_id, owner_id, message_id, caption_id) "
            "VALUES (?, ?, ?, ?)",
            (request_id, owner_id, message_id, caption_id),
        )


def get_owner_msgs(path: str, request_id: int) -> list[tuple[int, int, int | None]]:
    """[(owner_id, message_id, caption_id), ...]"""
    with closing(_connect(path)) as conn:
        rows = conn.execute(
            "SELECT owner_id, message_id, caption_id FROM owner_msgs WHERE request_id = ?",
            (request_id,),
        ).fetchall()
    return [(r["owner_id"], r["message_id"], r["caption_id"]) for r in rows]


def get_setting(path: str, key: str) -> str | None:
    with closing(_connect(path)) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(path: str, key: str, value: str | None) -> None:
    with closing(_connect(path)) as conn, conn:
        if value is None:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        else:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
