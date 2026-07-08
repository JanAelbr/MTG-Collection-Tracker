import sqlite3

from util.storage_tables import ensure_storage_tables, seed_storage_locations


def ensure_app_tables(conn: sqlite3.Connection) -> None:
    ensure_storage_tables(conn)
    _ensure_storage_location_columns(conn)
    _ensure_user_settings_table(conn)
    seed_storage_locations(conn)


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


def _ensure_storage_location_columns(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(storage_locations)").fetchall()
    }
    if "is_system" not in columns:
        conn.execute(
            """
            ALTER TABLE storage_locations
            ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0
            """
        )
    conn.execute(
        """
        UPDATE storage_locations
        SET is_system = 1
        WHERE location_slug LIKE 'binder:%'
           OR location_slug LIKE 'deck:%'
           OR location_slug = 'storage:general'
        """
    )
