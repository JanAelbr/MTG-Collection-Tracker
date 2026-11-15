import sqlite3
from lib.db import is_attached_table, table_schema
from lib.run_log import get_logger

log = get_logger(__name__)

CARD_COLUMNS = {
    "image_uri": "TEXT",
    "image_uri_back": "TEXT",
    "cardmarket_url": "TEXT",
    "cardmarket_url_foil": "TEXT",
    "scryfall_cardmarket_url": "TEXT",
    "has_nonfoil": "INTEGER",
    "has_foil": "INTEGER",
    "has_etched": "INTEGER",
    "market_value_etched": "REAL",
    "colors": "TEXT",
    "type_line": "TEXT",
    "card_type": "TEXT",
    "color_identity": "TEXT",
    "oracle_text": "TEXT",
    "mana_cost": "TEXT",
    "cmc": "REAL",
    "legalities": "TEXT",
    "is_basic_land": "INTEGER",
    "scryfall_id": "TEXT",
    "power": "TEXT",
    "toughness": "TEXT",
    "rarity": "TEXT",
}


# Add missing card columns without recreating the database.
def ensure_card_columns(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cards)")
    existing = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in CARD_COLUMNS.items():
        if column_name in existing:
            continue
        cursor.execute(f"ALTER TABLE cards ADD COLUMN {column_name} {column_type}")


def ensure_card_indexes(conn: sqlite3.Connection) -> None:
    if is_attached_table(conn, "cards"):
        return
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cards_set_code ON cards(set_code)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cards_set_collector ON cards(set_code, collector_number)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cards_set_art_style ON cards(set_code, art_style)"
    )
    # Speeds up the many exact `WHERE name = ?` lookups (variant gallery, print
    # finish flags). Does not help `LIKE '%term%'` set search (leading wildcard),
    # which stays a table scan by design — use cards_fts for substring/prefix search.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)"
    )


def _ensure_cards_fts_objects(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
            name,
            oracle_text,
            type_line,
            content='cards',
            content_rowid='rowid'
        )
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS cards_fts_ai AFTER INSERT ON cards BEGIN
            INSERT INTO cards_fts(rowid, name, oracle_text, type_line)
            VALUES (new.rowid, new.name, new.oracle_text, new.type_line);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS cards_fts_ad AFTER DELETE ON cards BEGIN
            INSERT INTO cards_fts(cards_fts, rowid, name, oracle_text, type_line)
            VALUES ('delete', old.rowid, old.name, old.oracle_text, old.type_line);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS cards_fts_au AFTER UPDATE OF name, oracle_text, type_line
        ON cards BEGIN
            INSERT INTO cards_fts(cards_fts, rowid, name, oracle_text, type_line)
            VALUES ('delete', old.rowid, old.name, old.oracle_text, old.type_line);
            INSERT INTO cards_fts(rowid, name, oracle_text, type_line)
            VALUES (new.rowid, new.name, new.oracle_text, new.type_line);
        END
        """
    )


def _fts_doc_count(conn: sqlite3.Connection) -> int | None:
    """Indexed documents. COUNT(*) on cards_fts follows the content table."""
    try:
        row = conn.execute("SELECT COUNT(*) FROM cards_fts_docsize").fetchone()
    except sqlite3.Error:
        return None
    return int(row[0])


def _fts_rowids_diverge(conn: sqlite3.Connection) -> bool:
    ghost = conn.execute(
        """
        SELECT 1 FROM cards_fts_docsize AS d
        WHERE NOT EXISTS (SELECT 1 FROM cards AS c WHERE c.rowid = d.id)
        LIMIT 1
        """
    ).fetchone()
    if ghost:
        return True
    missing = conn.execute(
        """
        SELECT 1 FROM cards AS c
        WHERE NOT EXISTS (SELECT 1 FROM cards_fts_docsize AS d WHERE d.id = c.rowid)
        LIMIT 1
        """
    ).fetchone()
    return missing is not None


def _cards_fts_needs_rebuild(conn: sqlite3.Connection) -> bool:
    indexed = _fts_doc_count(conn)
    if indexed is None:
        return False
    cards_count = int(conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0])
    if indexed != cards_count:
        return True
    return _fts_rowids_diverge(conn)


def ensure_cards_fts(conn: sqlite3.Connection) -> None:
    """FTS5 index over card name/text for catalog search (prefix + token match)."""
    if is_attached_table(conn, "cards"):
        return
    _ensure_cards_fts_objects(conn)
    if not _cards_fts_needs_rebuild(conn):
        return
    log.info("Rebuilding cards_fts; indexed rowids do not match cards")
    conn.execute("INSERT INTO cards_fts(cards_fts) VALUES('rebuild')")


def ensure_purchase_unique_index(conn: sqlite3.Connection) -> None:
    if table_schema(conn, "purchases") != "main":
        return
    cursor = conn.cursor()
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_card "
        "ON purchases(set_code, collector_number, finish)"
    )
