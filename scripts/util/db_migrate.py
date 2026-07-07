import csv
import sqlite3
from pathlib import Path

from lib.config import ART_STYLES_DIR, DATA_DIR, SET_CODE_ALIASES, art_style_rules_path, purchase_csv_path
from util.card_prices import ensure_card_prices_table

CARD_COLUMNS = {
    "image_uri": "TEXT",
    "cardmarket_url": "TEXT",
    "cardmarket_url_foil": "TEXT",
    "has_nonfoil": "INTEGER",
    "has_foil": "INTEGER",
    "has_etched": "INTEGER",
    "market_value_etched": "REAL",
    "colors": "TEXT",
    "type_line": "TEXT",
    "card_type": "TEXT",
}


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
    for alias, canonical in SET_CODE_ALIASES.items():
        if alias == canonical:
            continue
        _migrate_alias_rows(conn, "purchases", alias, canonical)
        _migrate_alias_card_instances(conn, alias, canonical)
        _migrate_alias_deck_cards(conn, alias, canonical)
        _migrate_alias_card_prices(conn, alias, canonical)
        conn.execute("DELETE FROM cards WHERE set_code = ?", (alias,))
        if _table_exists(conn, "sets"):
            conn.execute("DELETE FROM sets WHERE set_code = ?", (alias,))


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def migrate_deprecated_set_csv_files() -> None:
    """Merge legacy per-set purchase CSV files into their canonical file."""
    for alias, canonical in SET_CODE_ALIASES.items():
        if alias == canonical:
            continue
        alias_path = DATA_DIR / f"{alias.lower()}.csv"
        if not alias_path.exists():
            continue
        canonical_path = purchase_csv_path(canonical)
        if not canonical_path.exists():
            alias_path.replace(canonical_path)
            continue

        alias_fieldnames, alias_rows = _read_csv_rows(alias_path)
        canonical_fieldnames, canonical_rows = _read_csv_rows(canonical_path)
        fieldnames = canonical_fieldnames or alias_fieldnames
        if not fieldnames:
            alias_path.unlink(missing_ok=True)
            continue

        seen = {
            (
                str(row.get("card_number") or row.get("collector_number") or "").strip(),
                str(row.get("finish") or row.get("foil") or "0").strip(),
            )
            for row in canonical_rows
        }
        for row in alias_rows:
            key = (
                str(row.get("card_number") or row.get("collector_number") or "").strip(),
                str(row.get("finish") or row.get("foil") or "0").strip(),
            )
            if not key[0] or key in seen:
                continue
            canonical_rows.append(row)
            seen.add(key)

        _write_csv_rows(canonical_path, fieldnames, canonical_rows)
        alias_path.unlink(missing_ok=True)

        alias_art = ART_STYLES_DIR / f"{alias.lower()}.json"
        canonical_art = art_style_rules_path(canonical)
        if alias_art.exists() and canonical_art.exists():
            alias_art.unlink(missing_ok=True)


def ensure_set_code_aliases(conn: sqlite3.Connection) -> None:
    migrate_deprecated_set_csv_files()
    consolidate_set_code_aliases(conn)
    conn.commit()
