import sqlite3
from datetime import datetime, timezone

from lib.config import normalize_set_code


def ensure_tracked_sets_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_sets (
            set_code TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """
    )


def ensure_tracked_sets_ready(conn: sqlite3.Connection) -> None:
    ensure_tracked_sets_table(conn)


def list_tracked_set_codes(conn: sqlite3.Connection) -> list[str]:
    ensure_tracked_sets_table(conn)
    rows = conn.execute(
        "SELECT set_code FROM tracked_sets ORDER BY set_code"
    ).fetchall()
    return [str(row[0]) for row in rows]


def is_set_tracked(conn: sqlite3.Connection, set_code: str) -> bool:
    normalized = normalize_set_code(set_code)
    if not normalized:
        return False
    ensure_tracked_sets_table(conn)
    row = conn.execute(
        "SELECT 1 FROM tracked_sets WHERE set_code = ? LIMIT 1",
        (normalized,),
    ).fetchone()
    return row is not None


def add_tracked_set(conn: sqlite3.Connection, set_code: str) -> None:
    normalized = normalize_set_code(set_code)
    if not normalized:
        raise ValueError("Set code is required")
    ensure_tracked_sets_table(conn)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute(
        """
        INSERT INTO tracked_sets (set_code, created_at)
        VALUES (?, ?)
        """,
        (normalized, created_at),
    )


def remove_tracked_set(conn: sqlite3.Connection, set_code: str) -> bool:
    normalized = normalize_set_code(set_code)
    if not normalized:
        return False
    ensure_tracked_sets_table(conn)
    cursor = conn.execute(
        "DELETE FROM tracked_sets WHERE set_code = ?",
        (normalized,),
    )
    return cursor.rowcount > 0


def migrate_tracked_set_alias(
    conn: sqlite3.Connection,
    alias: str,
    canonical: str,
) -> None:
    if not _table_exists(conn, "tracked_sets"):
        return
    conn.execute(
        """
        UPDATE tracked_sets
        SET set_code = ?
        WHERE set_code = ?
          AND NOT EXISTS (
            SELECT 1 FROM tracked_sets existing WHERE existing.set_code = ?
          )
        """,
        (canonical, alias, canonical),
    )
    conn.execute("DELETE FROM tracked_sets WHERE set_code = ?", (alias,))


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None
