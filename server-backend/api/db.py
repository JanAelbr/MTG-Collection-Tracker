import sqlite3
from contextlib import contextmanager
from typing import Iterator

from lib.db import connect_catalog, connect_current, connect_profile, connect_registry

__all__ = ["connect", "connect_catalog", "connect_profile", "connect_registry", "db_session"]


def connect() -> sqlite3.Connection:
    """Connection for the request's active profile (shared catalog attached)."""
    return connect_current()


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
