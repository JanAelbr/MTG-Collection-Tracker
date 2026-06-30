import sqlite3
from collections.abc import Generator

from fastapi import Depends

from api.db import connect
from util.app_tables import ensure_app_tables


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = connect()
    try:
        ensure_app_tables(conn)
        conn.commit()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
