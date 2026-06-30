import sqlite3

from util.card_prices import ensure_card_prices_table

CARD_COLUMNS = {
    "image_uri": "TEXT",
    "cardmarket_url": "TEXT",
    "has_nonfoil": "INTEGER",
    "has_foil": "INTEGER",
    "has_etched": "INTEGER",
    "market_value_etched": "REAL",
    "colors": "TEXT",
    "type_line": "TEXT",
    "card_type": "TEXT",
}


def _backfill_card_types(conn: sqlite3.Connection) -> None:
    from util.card_metadata import primary_card_type

    rows = conn.execute(
        """
        SELECT set_code, collector_number, type_line
        FROM cards
        WHERE (card_type IS NULL OR TRIM(card_type) = '')
          AND type_line IS NOT NULL
          AND TRIM(type_line) != ''
        """
    ).fetchall()
    if not rows:
        return
    conn.executemany(
        """
        UPDATE cards
        SET card_type = ?
        WHERE set_code = ? AND collector_number = ?
        """,
        [
            (primary_card_type(type_line), set_code, collector_number)
            for set_code, collector_number, type_line in rows
        ],
    )


# Add missing card columns without recreating the database.
def ensure_card_columns(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cards)")
    existing = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in CARD_COLUMNS.items():
        if column_name in existing:
            continue
        cursor.execute(f"ALTER TABLE cards ADD COLUMN {column_name} {column_type}")
    _backfill_card_types(conn)


# Remove duplicate purchase rows, keeping the earliest insert per card finish.
def dedupe_purchases(conn: sqlite3.Connection) -> int:
    cursor = conn.cursor()
    before = cursor.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
    cursor.execute(
        """
        DELETE FROM purchases
        WHERE purchase_id NOT IN (
            SELECT MIN(purchase_id)
            FROM purchases
            GROUP BY set_code, collector_number, finish
        )
        """
    )
    removed = before - cursor.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
    return removed


# Ensure one purchase row per set, collector number, and finish.
def ensure_purchase_unique_index(conn: sqlite3.Connection) -> None:
    dedupe_purchases(conn)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_card "
        "ON purchases(set_code, collector_number, finish)"
    )
