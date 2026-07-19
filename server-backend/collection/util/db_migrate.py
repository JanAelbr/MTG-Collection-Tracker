import sqlite3
from datetime import date

from lib.config import SET_CODE_ALIASES
from lib.run_log import get_logger
from util.card_prices import ensure_card_prices_table

log = get_logger(__name__)

CARD_COLUMNS = {
    "image_uri": "TEXT",
    "image_uri_back": "TEXT",
    "cardmarket_url": "TEXT",
    "cardmarket_url_foil": "TEXT",
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


def backfill_basic_land_flags(conn: sqlite3.Connection) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE cards
        SET is_basic_land = 1
        WHERE COALESCE(is_basic_land, 0) = 0
          AND type_line IS NOT NULL
          AND LOWER(type_line) LIKE '%basic%land%'
        """
    )
    cursor.execute(
        """
        UPDATE cards
        SET card_type = 'land'
        WHERE (card_type IS NULL OR card_type = '')
          AND type_line IS NOT NULL
          AND LOWER(type_line) LIKE '%land%'
        """
    )
    return cursor.rowcount


def mark_complete_catalog_sets(conn: sqlite3.Connection) -> int:
    """Stamp catalog_synced_at on sets whose stored cards already have power metadata."""
    from util.price_sync import count_cards_missing_power_metadata

    today = date.today().isoformat()
    cursor = conn.cursor()
    set_codes = [
        row[0]
        for row in cursor.execute(
            """
            SELECT DISTINCT set_code
            FROM cards
            WHERE set_code IS NOT NULL AND set_code != ''
            """
        ).fetchall()
    ]
    marked = 0
    for set_code in set_codes:
        if count_cards_missing_power_metadata(cursor, set_code) > 0:
            continue
        row = cursor.execute(
            "SELECT catalog_synced_at FROM sets WHERE set_code = ?",
            (set_code,),
        ).fetchone()
        if row and row[0]:
            continue
        cursor.execute(
            """
            INSERT INTO sets (set_code, name, released_at, scryfall_uri, icon_svg_uri, updated_at, catalog_synced_at)
            VALUES (?, ?, NULL, NULL, NULL, ?, ?)
            ON CONFLICT(set_code) DO UPDATE SET
                catalog_synced_at = excluded.catalog_synced_at,
                updated_at = COALESCE(sets.updated_at, excluded.updated_at)
            """,
            (set_code, set_code, today, today),
        )
        marked += 1
    return marked


def backfill_card_types(conn: sqlite3.Connection) -> int:
    from util.card_metadata import primary_card_type

    rows = conn.execute(
        """
        SELECT set_code, collector_number, type_line
        FROM cards
        WHERE (card_type IS NULL OR card_type = '')
          AND type_line IS NOT NULL
          AND type_line != ''
        """
    ).fetchall()
    if not rows:
        return 0
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
    return len(rows)


def list_top_set_codes_by_collection_size(
    conn: sqlite3.Connection,
    limit: int = 15,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT set_code, COUNT(*) AS owned_count
        FROM purchases
        GROUP BY set_code
        ORDER BY owned_count DESC, set_code ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    codes = [str(row[0]).upper() for row in rows if row[0]]
    if len(codes) >= limit:
        return codes[:limit]

    tracked_rows = conn.execute(
        "SELECT set_code FROM tracked_sets ORDER BY set_code ASC"
    ).fetchall()
    seen = set(codes)
    for row in tracked_rows:
        code = str(row[0]).upper()
        if not code or code in seen:
            continue
        codes.append(code)
        seen.add(code)
        if len(codes) >= limit:
            break
    return codes[:limit]


def reload_top_set_catalogs(conn: sqlite3.Connection, limit: int = 15) -> list[str]:
    from util.scryfall_catalog_sync import import_set_catalog_from_scryfall

    reloaded: list[str] = []
    for set_code in list_top_set_codes_by_collection_size(conn, limit=limit):
        try:
            import_set_catalog_from_scryfall(conn, set_code, force_scryfall=True)
            reloaded.append(set_code)
            log.info("Reloaded Scryfall catalog for %s", set_code)
        except Exception as exc:
            log.warning("Could not reload Scryfall catalog for %s: %s", set_code, exc)
    if reloaded:
        conn.commit()
    return reloaded


def ensure_card_detail_metadata(conn: sqlite3.Connection) -> None:
    ensure_card_columns(conn)
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        ("card_detail_metadata_reload_v1",),
    ).fetchone()
    if row and row[0] == "done":
        return
    reloaded = reload_top_set_catalogs(conn, limit=15)
    conn.execute(
        """
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        ("card_detail_metadata_reload_v1", "done"),
    )
    conn.commit()
    if reloaded:
        log.info(
            "Card detail metadata reload finished for %s set(s): %s",
            len(reloaded),
            ", ".join(reloaded),
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


def ensure_card_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cards_set_code ON cards(set_code)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cards_set_art_style ON cards(set_code, art_style)"
    )


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


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _migrate_alias_rows(
    conn: sqlite3.Connection,
    table_name: str,
    alias: str,
    canonical: str,
) -> None:
    if not _table_exists(conn, table_name):
        return
    conn.execute(
        f"""
        UPDATE {table_name}
        SET set_code = ?
        WHERE set_code = ?
          AND NOT EXISTS (
            SELECT 1
            FROM {table_name} existing
            WHERE existing.set_code = ?
              AND existing.collector_number = {table_name}.collector_number
              AND existing.finish = {table_name}.finish
          )
        """,
        (canonical, alias, canonical),
    )
    conn.execute(
        f"DELETE FROM {table_name} WHERE set_code = ?",
        (alias,),
    )


def _migrate_alias_card_prices(
    conn: sqlite3.Connection,
    alias: str,
    canonical: str,
) -> None:
    if not _table_exists(conn, "card_prices"):
        return
    conn.execute(
        """
        UPDATE card_prices
        SET set_code = ?
        WHERE set_code = ?
          AND NOT EXISTS (
            SELECT 1
            FROM card_prices existing
            WHERE existing.set_code = ?
              AND existing.collector_number = card_prices.collector_number
              AND existing.finish = card_prices.finish
              AND existing.source = card_prices.source
              AND existing.price_date = card_prices.price_date
          )
        """,
        (canonical, alias, canonical),
    )
    conn.execute("DELETE FROM card_prices WHERE set_code = ?", (alias,))


def _migrate_alias_deck_cards(conn: sqlite3.Connection, alias: str, canonical: str) -> None:
    if not _table_exists(conn, "deck_cards"):
        return
    conn.execute(
        """
        UPDATE deck_cards
        SET set_code = ?,
            card_name = REPLACE(card_name, ?, ?)
        WHERE set_code = ?
        """,
        (canonical, f"{alias} #", f"{canonical} #", alias),
    )


def _migrate_alias_card_instances(conn: sqlite3.Connection, alias: str, canonical: str) -> None:
    if not _table_exists(conn, "card_instances"):
        return
    conn.execute(
        """
        UPDATE card_instances
        SET set_code = ?
        WHERE set_code = ?
        """,
        (canonical, alias),
    )


def consolidate_set_code_aliases(conn: sqlite3.Connection) -> None:
    """Move legacy alias set codes (e.g. PLIST) onto their canonical code (PLST)."""
    from util.tracked_sets import migrate_tracked_set_alias

    for alias, canonical in SET_CODE_ALIASES.items():
        if alias == canonical:
            continue
        _migrate_alias_rows(conn, "purchases", alias, canonical)
        _migrate_alias_card_instances(conn, alias, canonical)
        _migrate_alias_deck_cards(conn, alias, canonical)
        _migrate_alias_card_prices(conn, alias, canonical)
        migrate_tracked_set_alias(conn, alias, canonical)
        conn.execute("DELETE FROM cards WHERE set_code = ?", (alias,))
        if _table_exists(conn, "sets"):
            conn.execute("DELETE FROM sets WHERE set_code = ?", (alias,))


def ensure_set_code_aliases(conn: sqlite3.Connection) -> None:
    consolidate_set_code_aliases(conn)
    conn.commit()
