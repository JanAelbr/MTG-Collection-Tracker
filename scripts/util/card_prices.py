import sqlite3

from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    MARKET_VALUE_COLUMNS,
)

MAX_OWNED_PRICE_DATES = 2

INSERT_PRICE_SQL = """
INSERT OR REPLACE INTO card_prices (
    set_code, collector_number, finish, price, source, price_date
) VALUES (?, ?, ?, ?, ?, ?)
"""

CARD_PRICES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS card_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
    price REAL NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('scryfall', 'cardmarket')),
    price_date TEXT NOT NULL,
    UNIQUE (set_code, collector_number, finish, source, price_date)
);

CREATE INDEX IF NOT EXISTS idx_card_prices_lookup
    ON card_prices(set_code, collector_number, finish, price_date);
"""


# Keep owned rows for the newest max_dates snapshot dates only.
def prune_owned_price_history(
    conn: sqlite3.Connection,
    *,
    max_dates: int = MAX_OWNED_PRICE_DATES,
) -> tuple[int, int]:
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM card_prices
        WHERE NOT EXISTS (
            SELECT 1
            FROM purchases p
            WHERE p.set_code = card_prices.set_code
              AND p.collector_number = card_prices.collector_number
              AND p.finish = card_prices.finish
        )
        """
    )
    deleted_unowned = cursor.rowcount

    dates = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT price_date FROM card_prices ORDER BY price_date DESC"
        ).fetchall()
    ]
    if len(dates) <= max_dates:
        return deleted_unowned, 0

    keep_dates = dates[:max_dates]
    placeholders = ", ".join("?" for _ in keep_dates)
    cursor.execute(
        f"DELETE FROM card_prices WHERE price_date NOT IN ({placeholders})",
        keep_dates,
    )
    return deleted_unowned, cursor.rowcount


def _purchase_exists(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM purchases
        WHERE set_code = ?
          AND collector_number = ?
          AND finish = ?
        """,
        (set_code.upper(), str(collector_number), int(finish)),
    ).fetchone()
    return row is not None


# Create the card_prices history table when missing.
def ensure_card_prices_table(conn: sqlite3.Connection) -> None:
    from util.finish_migration import ensure_finish_migration

    conn.executescript(CARD_PRICES_TABLE_SQL)
    ensure_finish_migration(conn)


# Store one owned finish snapshot for a date and source.
def record_card_price(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
    price: float,
    source: str,
    price_date: str,
) -> None:
    if not _purchase_exists(conn, set_code, collector_number, finish):
        return
    conn.execute(
        INSERT_PRICE_SQL,
        (
            set_code.upper(),
            str(collector_number),
            int(finish),
            price,
            source,
            price_date,
        ),
    )


# Store many owned finish snapshots in one executemany call.
def record_card_prices_batch(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, int, float, str, str]],
) -> int:
    owned_rows = [
        row for row in rows
        if _purchase_exists(conn, row[0], row[1], row[2])
    ]
    if not owned_rows:
        return 0
    conn.executemany(INSERT_PRICE_SQL, owned_rows)
    return len(owned_rows)


SNAPSHOT_OWNED_PRICES_SQL = """
INSERT OR REPLACE INTO card_prices (
    set_code, collector_number, finish, price, source, price_date
)
SELECT
    p.set_code,
    p.collector_number,
    p.finish,
    CASE p.finish
        WHEN 2 THEN c.market_value_etched
        WHEN 1 THEN c.market_value_foil
        ELSE c.market_value
    END,
    'cardmarket',
    ?
FROM purchases p
JOIN cards c
  ON c.set_code = p.set_code
 AND c.collector_number = p.collector_number
WHERE CASE p.finish
        WHEN 2 THEN c.market_value_etched
        WHEN 1 THEN c.market_value_foil
        ELSE c.market_value
      END IS NOT NULL
"""


# Snapshot current owned card prices for one date in a single query.
def snapshot_owned_cardmarket_prices(conn: sqlite3.Connection, price_date: str) -> int:
    cursor = conn.execute(SNAPSHOT_OWNED_PRICES_SQL, (price_date,))
    rowcount = cursor.rowcount
    prune_owned_price_history(conn)
    return rowcount


# Store finish snapshots when values are known.
def record_card_price_values(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    price_date: str,
    source: str,
    market_value: float | None,
    market_value_foil: float | None,
    market_value_etched: float | None = None,
) -> int:
    recorded = 0
    for finish, value in (
        (FINISH_NONFOIL, market_value),
        (FINISH_FOIL, market_value_foil),
        (FINISH_ETCHED, market_value_etched),
    ):
        if value is not None:
            record_card_price(
                conn, set_code, collector_number, finish, value, source, price_date,
            )
            recorded += 1
    return recorded


# Keep the last known price when a new fetch returns no value.
def preserve_market_value(
    new_value: float | None,
    existing_value: float | None,
) -> float | None:
    return new_value if new_value is not None else existing_value


# Read stored market values for one card, if any.
def load_existing_card_prices(
    cursor,
    set_code: str,
    collector_number: str,
) -> tuple[float | None, float | None, float | None]:
    row = cursor.execute(
        """
        SELECT market_value, market_value_foil, market_value_etched
        FROM cards
        WHERE set_code = ? AND collector_number = ?
        """,
        (set_code.upper(), str(collector_number)),
    ).fetchone()
    if row is None:
        return None, None, None
    return row[0], row[1], row[2]


RESTORE_MARKET_VALUE_SQL = """
UPDATE cards
SET {column} = (
    SELECT cp.price
    FROM card_prices cp
    WHERE cp.set_code = cards.set_code
      AND cp.collector_number = cards.collector_number
      AND cp.finish = ?
      AND cp.source = 'cardmarket'
    ORDER BY cp.price_date DESC, cp.price_id DESC
    LIMIT 1
)
WHERE {column} IS NULL
AND (cardmarket_url IS NULL OR TRIM(cardmarket_url) = '')
AND EXISTS (
    SELECT 1
    FROM card_prices cp
    WHERE cp.set_code = cards.set_code
      AND cp.collector_number = cards.collector_number
      AND cp.finish = ?
      AND cp.source = 'cardmarket'
);
"""


# Repopulate NULL market values from the latest card_prices snapshot.
def restore_market_values_from_history(conn: sqlite3.Connection) -> int:
    cursor = conn.cursor()
    restored = 0
    for finish, column in MARKET_VALUE_COLUMNS.items():
        cursor.execute(
            RESTORE_MARKET_VALUE_SQL.format(column=column),
            (finish, finish),
        )
        restored += cursor.rowcount
    return restored
