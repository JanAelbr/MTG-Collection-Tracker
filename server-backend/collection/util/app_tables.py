import sqlite3
import threading

from util.storage_tables import ensure_storage_tables, seed_storage_locations

_app_tables_lock = threading.Lock()
_ready_db_paths: set[str] = set()


def _database_path(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return row[2] if row else ""


def ensure_app_tables(conn: sqlite3.Connection, *, force: bool = False) -> None:
    """Ensure storage/settings tables exist and seed default locations.

    After the first successful run for a given on-disk DB file in this process,
    later calls are no-ops so request handlers do not keep taking write locks.
    Pass force=True (or call seed_storage_locations directly) after deck
    create/rename when locations must be refreshed.
    """
    db_path = _database_path(conn)
    cacheable = bool(db_path) and db_path != ":memory:"
    if not force and cacheable and db_path in _ready_db_paths:
        return

    with _app_tables_lock:
        if not force and cacheable and db_path in _ready_db_paths:
            return
        ensure_storage_tables(conn)
        _ensure_user_settings_table(conn)
        seed_storage_locations(conn)
        _backfill_system_location_flags(conn)
        if cacheable:
            _ready_db_paths.add(db_path)


def _ensure_user_settings_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO user_settings (key, value)
        VALUES ('price_strategy', 'trend')
        """
    )


def _backfill_system_location_flags(conn: sqlite3.Connection) -> None:
    """Mark built-in locations as system once (schema may predate is_system)."""
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(storage_locations)").fetchall()
    }
    if "is_system" not in columns:
        return
    needs_backfill = conn.execute(
        """
        SELECT 1
        FROM storage_locations
        WHERE is_system = 0
          AND (
            location_slug LIKE 'binder:%'
            OR location_slug LIKE 'deck:%'
            OR location_slug = 'storage:general'
          )
        LIMIT 1
        """
    ).fetchone()
    if not needs_backfill:
        return
    conn.execute(
        """
        UPDATE storage_locations
        SET is_system = 1
        WHERE location_slug LIKE 'binder:%'
           OR location_slug LIKE 'deck:%'
           OR location_slug = 'storage:general'
        """
    )
