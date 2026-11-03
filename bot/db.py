import sqlite3
from contextlib import closing
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    username   TEXT,
    full_name  TEXT,
    kind       TEXT NOT NULL,           -- stickers / emoji / question
    text       TEXT,
    status     TEXT NOT NULL DEFAULT 'new',  -- new / answered / done
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(SCHEMA)


def add_request(
    path: str,
    user_id: int,
    username: str | None,
    full_name: str,
    kind: str,
    text: str,
) -> int:
    with closing(sqlite3.connect(path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO requests (user_id, username, full_name, kind, text) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, full_name, kind, text),
        )
        return cur.lastrowid


def set_status(path: str, request_id: int, status: str) -> None:
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
