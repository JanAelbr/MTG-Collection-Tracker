import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_COLLECTION = _SCRIPTS.parent / "server-backend" / "collection"
for _path in (_COLLECTION, _SCRIPTS):
    sys.path.insert(0, str(_path))

from lib.config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE cards (
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
    cardmarket_url_foil TEXT,
    colors TEXT,
    type_line TEXT,
    card_type TEXT
);

CREATE TABLE purchases (
    purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    purchase_value REAL NOT NULL DEFAULT 0,
    finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
    UNIQUE (set_code, collector_number, finish)
);

CREATE TABLE card_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
    price REAL NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('scryfall', 'cardmarket')),
    price_date TEXT NOT NULL,
    UNIQUE (set_code, collector_number, finish, source, price_date)
);

CREATE INDEX idx_card_prices_lookup
    ON card_prices(set_code, collector_number, finish, price_date);

CREATE TABLE sets (
    set_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    released_at TEXT,
    scryfall_uri TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE decks (
    deck_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    purchase_price REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE deck_cards (
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

CREATE INDEX idx_deck_cards_deck
    ON deck_cards(deck_id, sort_order);

CREATE INDEX idx_deck_cards_print
    ON deck_cards(set_code, collector_number, finish);
"""


# Drop and recreate the cards, purchases, and card_prices tables.
def recreate_schema(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS deck_cards")
    cursor.execute("DROP TABLE IF EXISTS decks")
    cursor.execute("DROP TABLE IF EXISTS card_prices")
    cursor.execute("DROP TABLE IF EXISTS purchases")
    cursor.execute("DROP TABLE IF EXISTS cards")
    cursor.execute("DROP TABLE IF EXISTS sets")
    cursor.executescript(SCHEMA_SQL)


# Create a fresh SQLite database with the project schema.
def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    recreate_schema(conn)
    conn.commit()
    conn.close()
    print("Database en tabellen aangemaakt.")


if __name__ == "__main__":
    main()
