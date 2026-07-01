import sqlite3
import threading

from lib.config import HTTP_USER_AGENT
from util.app_tables import ensure_app_tables
from util.card_prices import ensure_card_prices_table
from util.db_migrate import (
    backfill_card_types,
    ensure_card_columns,
    ensure_card_indexes,
    ensure_purchase_unique_index,
)
from util.deck_tables import ensure_deck_tables
from util.set_catalog import backfill_missing_set_icon_uris, ensure_sets_columns, ensure_sets_table

CORE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    name TEXT NOT NULL,
    art_style TEXT,
    market_value REAL DEFAULT NULL,
    market_value_foil REAL DEFAULT NULL,
    market_value_etched REAL DEFAULT NULL,
    has_nonfoil INTEGER,
    has_foil INTEGER,
    has_etched INTEGER,
    image_uri TEXT,
    cardmarket_url TEXT,
    colors TEXT,
    type_line TEXT,
    card_type TEXT
);

CREATE TABLE IF NOT EXISTS purchases (
    purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    purchase_value REAL NOT NULL DEFAULT 0,
    finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
    UNIQUE (set_code, collector_number, finish)
);

CREATE TABLE IF NOT EXISTS sets (
    set_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    released_at TEXT,
    scryfall_uri TEXT,
    icon_svg_uri TEXT,
    updated_at TEXT NOT NULL
);
"""


_schema_lock = threading.Lock()
_initialized_db_paths: set[str] = set()


def _database_path(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return row[2] if row else ""


def ensure_database_schema(conn: sqlite3.Connection) -> None:
    """Create core collection tables and run incremental migrations once per database file."""
    db_path = _database_path(conn)
    if db_path and db_path in _initialized_db_paths:
        return
    with _schema_lock:
        if db_path and db_path in _initialized_db_paths:
            return
        conn.executescript(CORE_TABLES_SQL)
        ensure_deck_tables(conn)
        ensure_sets_table(conn)
        ensure_sets_columns(conn)
        backfill_missing_set_icon_uris(conn, {"User-Agent": HTTP_USER_AGENT})
        ensure_card_prices_table(conn)
        ensure_card_columns(conn)
        backfill_card_types(conn)
        ensure_card_indexes(conn)
        ensure_purchase_unique_index(conn)
        ensure_app_tables(conn)
        if db_path:
            _initialized_db_paths.add(db_path)
