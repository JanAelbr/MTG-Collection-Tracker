import sqlite3
import threading

from lib.db import table_exists

_deck_tables_lock = threading.Lock()
_ready_db_paths: set[str] = set()

DECK_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS decks (
    deck_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    purchase_price REAL,
    format TEXT NOT NULL DEFAULT 'commander',
    favorite INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deck_cards (
    deck_card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL,
    card_name TEXT NOT NULL,
    set_code TEXT,
    collector_number TEXT,
    finish INTEGER NOT NULL DEFAULT 0 CHECK (finish IN (0, 1, 2)),
    qty INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
    owned_qty INTEGER NOT NULL DEFAULT 1 CHECK (owned_qty >= 0),
    section TEXT NOT NULL DEFAULT 'main',
    sort_order INTEGER NOT NULL DEFAULT 0,
    in_catalog INTEGER NOT NULL DEFAULT 0,
    UNIQUE (deck_id, set_code, collector_number, finish, section),
    FOREIGN KEY (deck_id) REFERENCES decks(deck_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deck_cards_deck
    ON deck_cards(deck_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_deck_cards_print
    ON deck_cards(set_code, collector_number, finish);
"""

def _database_path(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return row[2] if row else ""


# Create deck tables when missing.
def ensure_deck_tables(conn: sqlite3.Connection) -> None:
    """Run deck schema/migration checks, once per on-disk DB per process.

    Deck endpoints call this on nearly every request; without caching, each
    call re-runs CREATE TABLE IF NOT EXISTS and takes a write lock after the
    tables already exist.
    """
    db_path = _database_path(conn)
    cacheable = bool(db_path) and db_path != ":memory:"
    if cacheable and db_path in _ready_db_paths:
        return

    with _deck_tables_lock:
        if cacheable and db_path in _ready_db_paths:
            return
        conn.executescript(DECK_TABLES_SQL)
        if cacheable:
            _ready_db_paths.add(db_path)


def list_deck_sync_set_codes(conn: sqlite3.Connection) -> list[str]:
    """Return distinct set codes referenced by deck card prints."""
    from lib.config import normalize_set_code

    if not _table_exists(conn, "deck_cards"):
        return []
    rows = conn.execute(
        """
        SELECT DISTINCT set_code
        FROM deck_cards
        WHERE set_code IS NOT NULL AND TRIM(set_code) != ''
        ORDER BY set_code
        """
    ).fetchall()
    codes = {
        normalize_set_code(str(row[0]))
        for row in rows
        if normalize_set_code(str(row[0]))
    }
    return sorted(codes)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return table_exists(conn, table_name)
