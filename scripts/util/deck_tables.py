import sqlite3

DECK_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS decks (
    deck_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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

DECK_COLUMNS = {
    "purchase_price": "REAL",
}

DECK_CARD_COLUMNS = {
    "owned_qty": "INTEGER NOT NULL DEFAULT 1 CHECK (owned_qty >= 0)",
}


# Migrate deck_cards.foil to deck_cards.finish when needed.
def ensure_deck_finish_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(deck_cards)").fetchall()
    names = {row[1] for row in columns}
    if "finish" in names:
        return
    if "foil" not in names:
        return
    conn.executescript(
        """
        CREATE TABLE deck_cards_new (
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
        INSERT INTO deck_cards_new (
            deck_card_id, deck_id, card_name, set_code, collector_number, finish,
            qty, owned_qty, section, sort_order, in_catalog
        )
        SELECT
            deck_card_id, deck_id, card_name, set_code, collector_number, foil,
            qty, COALESCE(owned_qty, 1), section, sort_order, in_catalog
        FROM deck_cards;
        DROP TABLE deck_cards;
        ALTER TABLE deck_cards_new RENAME TO deck_cards;
        CREATE INDEX IF NOT EXISTS idx_deck_cards_deck
            ON deck_cards(deck_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_deck_cards_print
            ON deck_cards(set_code, collector_number, finish);
        """
    )


# Migrate deck_cards uniqueness from card name to print identity.
def ensure_deck_cards_print_unique(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'deck_cards'"
    ).fetchone()
    if not row or not row[0] or "card_name, foil, section" not in row[0]:
        return

    conn.executescript(
        """
        CREATE TABLE deck_cards_new (
            deck_card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            card_name TEXT NOT NULL,
            set_code TEXT,
            collector_number TEXT,
            finish INTEGER NOT NULL DEFAULT 0 CHECK (finish IN (0, 1, 2)),
            qty INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
            section TEXT NOT NULL DEFAULT 'main',
            sort_order INTEGER NOT NULL DEFAULT 0,
            in_catalog INTEGER NOT NULL DEFAULT 0,
            UNIQUE (deck_id, set_code, collector_number, finish, section),
            FOREIGN KEY (deck_id) REFERENCES decks(deck_id) ON DELETE CASCADE
        );
        INSERT INTO deck_cards_new SELECT * FROM deck_cards;
        DROP TABLE deck_cards;
        ALTER TABLE deck_cards_new RENAME TO deck_cards;
        CREATE INDEX IF NOT EXISTS idx_deck_cards_deck
            ON deck_cards(deck_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_deck_cards_print
            ON deck_cards(set_code, collector_number, finish);
        """
    )


# Create deck tables when missing.
def ensure_deck_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(DECK_TABLES_SQL)
    ensure_deck_columns(conn)
    ensure_deck_finish_column(conn)
    ensure_deck_card_columns(conn)
    ensure_deck_cards_print_unique(conn)


# Add missing deck columns without recreating the database.
def ensure_deck_columns(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(decks)")
    existing = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in DECK_COLUMNS.items():
        if column_name in existing:
            continue
        cursor.execute(f"ALTER TABLE decks ADD COLUMN {column_name} {column_type}")


# Add missing deck_cards columns without recreating the database.
def ensure_deck_card_columns(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(deck_cards)")
    existing = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in DECK_CARD_COLUMNS.items():
        if column_name in existing:
            continue
        cursor.execute(f"ALTER TABLE deck_cards ADD COLUMN {column_name} {column_type}")
