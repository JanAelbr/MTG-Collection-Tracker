"""System key/value markers stored with the shared catalog (not per profile)."""

import sqlite3

from lib.db import is_attached_table, table_exists

CATALOG_META_TABLE = "catalog_meta"


def ensure_catalog_meta_table(conn: sqlite3.Connection) -> None:
    if is_attached_table(conn, CATALOG_META_TABLE):
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def get_catalog_meta(conn: sqlite3.Connection, key: str) -> str:
    if not table_exists(conn, CATALOG_META_TABLE):
        return ""
    row = conn.execute("SELECT value FROM catalog_meta WHERE key = ?", (key,)).fetchone()
    if not row:
        return ""
    return str(row[0] or "").strip()


def set_catalog_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    ensure_catalog_meta_table(conn)
    conn.execute(
        """
        INSERT INTO catalog_meta (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
