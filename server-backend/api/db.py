import sqlite3
from contextlib import contextmanager
from typing import Iterator

from lib.config import DB_PATH


def connect() -> sqlite3.Connection:
    # timeout matches busy_timeout so concurrent request threads wait instead of
    # failing immediately when another writer holds the lock briefly.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
