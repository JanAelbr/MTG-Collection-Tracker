import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lib.config import DATA_DIR, EXCLUDED_SET_CODES, normalize_set_code

MIGRATION_SETTING_KEY = "tracked_sets_csv_migrated"
LEGACY_EXCLUDED_PURCHASE_CSV_NAMES = frozenset({"purchases.csv", "example.csv"})


def _list_legacy_set_csv_files() -> list[Path]:
    paths = sorted(
        p for p in DATA_DIR.glob("*.csv")
        if p.is_file() and p.name.lower() not in LEGACY_EXCLUDED_PURCHASE_CSV_NAMES
    )
    seen_canonical: set[str] = set()
    unique_paths: list[Path] = []
    for path in paths:
        canonical = normalize_set_code(path.stem)
        if canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)
        unique_paths.append(path)
    return unique_paths


def ensure_tracked_sets_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_sets (
            set_code TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """
    )


def _migration_complete(conn: sqlite3.Connection) -> bool:
    if not _user_settings_exists(conn):
        return False
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (MIGRATION_SETTING_KEY,),
    ).fetchone()
    return bool(row and row[0] == "1")


def _user_settings_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'user_settings' LIMIT 1"
    ).fetchone()
    return row is not None


def _mark_migration_complete(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO user_settings (key, value)
        VALUES (?, '1')
        """,
        (MIGRATION_SETTING_KEY,),
    )


def migrate_tracked_sets_from_csv_once(conn: sqlite3.Connection) -> int:
    """Import tracked set codes from legacy purchase CSV files exactly once per database."""
    ensure_tracked_sets_table(conn)
    if _migration_complete(conn):
        return 0

    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    inserted = 0
    for path in _list_legacy_set_csv_files():
        set_code = normalize_set_code(path.stem)
        if not set_code or set_code in EXCLUDED_SET_CODES:
            continue
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO tracked_sets (set_code, created_at)
            VALUES (?, ?)
            """,
            (set_code, created_at),
        )
        if cursor.rowcount:
            inserted += 1

    if _user_settings_exists(conn):
        _mark_migration_complete(conn)
    return inserted


def ensure_tracked_sets_ready(conn: sqlite3.Connection) -> None:
    ensure_tracked_sets_table(conn)
    migrate_tracked_sets_from_csv_once(conn)


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
