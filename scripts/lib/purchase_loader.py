import csv
import sqlite3
from pathlib import Path

from lib.config import DB_PATH, canonical_set_code_lower, list_set_csv_files, normalize_set_code
from lib.deck_csv import load_deck_entries, read_deck_card_rows
from lib.deck_loader import resolve_deck_row
from lib.deck_purchase import (
    allocate_deck_purchase_prices,
    lookup_unit_market,
    upsert_purchase_value,
)
from lib.run_log import get_logger
from lib.card_locations import sync_card_instances
from lib.purchase_csv import (
    card_number_from_row,
    detect_delimiter,
    parse_finish,
    parse_purchase_value,
)
from util.card_finishes import parse_finish_from_row, resolve_purchase_finish
from util.db_migrate import ensure_purchase_unique_index

log = get_logger(__name__)


def _catalog_finish_flags(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
) -> tuple[int | None, int | None, int | None]:
    row = cursor.execute(
        """
        SELECT has_nonfoil, has_foil, has_etched
        FROM cards
        WHERE set_code = ? AND collector_number = ?
        """,
        (set_code.upper(), str(collector_number).strip()),
    ).fetchone()
    if row is None:
        return None, None, None
    return row[0], row[1], row[2]


def normalize_purchase_finish(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
    finish: int,
) -> int:
    has_nonfoil, has_foil, has_etched = _catalog_finish_flags(
        cursor,
        set_code,
        collector_number,
    )
    if has_nonfoil is None:
        return int(finish)
    return resolve_purchase_finish(
        finish,
        has_nonfoil=has_nonfoil,
        has_foil=has_foil,
        has_etched=has_etched,
    )


# Insert one purchase row into the database.
def insert_purchase(cursor, set_code: str, card_number: str, row: dict) -> None:
    purchase_value = parse_purchase_value(
        row.get("purchase_value") or row.get("price") or row.get("purchase")
    )
    finish = parse_finish_from_row(row, default=parse_finish(row.get("finish")))
    finish = normalize_purchase_finish(cursor, set_code, card_number, finish)
    cursor.execute(
        "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, ?, ?)",
        (set_code.upper(), card_number, purchase_value, finish),
    )


# Insert one purchase row unless that finish is already owned.
def insert_purchase_if_missing(
    cursor,
    set_code: str,
    collector_number: str,
    purchase_value: float,
    finish: int,
) -> bool:
    cursor.execute(
        """
        INSERT OR IGNORE INTO purchases (
            set_code, collector_number, purchase_value, finish
        ) VALUES (?, ?, ?, ?)
        """,
        (set_code.upper(), collector_number, purchase_value, finish),
    )
    return cursor.rowcount > 0


# Import all purchase rows from one per-set CSV file.
def import_purchase_file(cursor, purchase_file: Path) -> int:
    set_code = canonical_set_code_lower(purchase_file.stem)
    log.info("Importing purchases from %s for set %s", purchase_file.name, set_code.upper())
    delimiter = detect_delimiter(purchase_file)
    rows = 0

    with purchase_file.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            card_number = card_number_from_row(row)
            if not card_number:
                continue
            insert_purchase(cursor, set_code, card_number, row)
            rows += 1

    log.info("  %s: %s purchase rows", set_code.upper(), rows)
    return rows


# Resolve one deck CSV row to a tracked print for purchase import.
def purchase_print_from_deck_row(cursor: sqlite3.Cursor, row: dict) -> tuple[str, str, int] | None:
    set_code = row.get("set_code")
    collector_number = row.get("collector_number")
    finish = row.get("finish", row.get("foil", 0))

    if set_code and collector_number:
        normalized_set = normalize_set_code(set_code)
        normalized_number = str(collector_number).strip()
        finish = normalize_purchase_finish(
            cursor,
            normalized_set,
            normalized_number,
            int(finish),
        )
        return normalized_set, normalized_number, finish

    resolved = resolve_deck_row(cursor, row)
    if not resolved.get("set_code") or not resolved.get("collector_number"):
        return None
    normalized_set = str(resolved["set_code"]).upper()
    normalized_number = str(resolved["collector_number"]).strip()
    finish = normalize_purchase_finish(
        cursor,
        normalized_set,
        normalized_number,
        int(resolved["finish"]),
    )
    return normalized_set, normalized_number, finish


def _load_deck_purchase_price(cursor: sqlite3.Cursor, slug: str) -> float | None:
    table = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'decks'"
    ).fetchone()
    if not table:
        return None
    row = cursor.execute(
        "SELECT purchase_price FROM decks WHERE slug = ?",
        (slug.lower(),),
    ).fetchone()
    if not row or row[0] is None:
        return None
    try:
        value = float(row[0])
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


# Build purchase rows for one deck before writing CSV or importing directly.
def build_deck_purchase_rows(cursor: sqlite3.Cursor, deck_entry) -> list[dict]:
    rows = read_deck_card_rows(deck_entry.path)
    deck_purchase_price = deck_entry.purchase_price or _load_deck_purchase_price(
        cursor,
        deck_entry.slug,
    )
    resolved_rows: list[dict] = []

    for row in rows:
        resolved_print = purchase_print_from_deck_row(cursor, row)
        if not resolved_print:
            continue
        set_code, collector_number, finish = resolved_print
        resolved_rows.append({
            **row,
            "set_code": set_code,
            "collector_number": collector_number,
            "finish": finish,
            "unit_market": lookup_unit_market(cursor, set_code, collector_number, finish),
        })

    explicit_total = 0.0
    allocation_rows: list[dict] = []
    for row in resolved_rows:
        explicit = row.get("explicit_purchase")
        if explicit is not None:
            explicit_total += explicit * int(row["qty"])
        else:
            allocation_rows.append(row)

    remaining_price = None
    if deck_purchase_price is not None:
        remaining_price = max(deck_purchase_price - explicit_total, 0.0)

    if allocation_rows and remaining_price is not None:
        allocated_prices = allocate_deck_purchase_prices(allocation_rows, remaining_price)
        for row, unit_price in zip(allocation_rows, allocated_prices):
            row["allocated_purchase"] = unit_price

    purchase_rows: list[dict] = []
    for row in resolved_rows:
        explicit = row.get("explicit_purchase")
        if explicit is not None:
            purchase_value = explicit
        elif row.get("allocated_purchase") is not None:
            purchase_value = row["allocated_purchase"]
        else:
            purchase_value = 0.0
        purchase_rows.append({
            "set_code": row["set_code"],
            "collector_number": row["collector_number"],
            "finish": row["finish"],
            "purchase_value": purchase_value,
        })
    return purchase_rows


# Import owned finishes from one registered deck without overwriting set purchase files.
def import_deck_purchase_file(cursor: sqlite3.Cursor, deck_entry) -> int:
    rows = read_deck_card_rows(deck_entry.path)
    deck_purchase_price = deck_entry.purchase_price or _load_deck_purchase_price(
        cursor,
        deck_entry.slug,
    )
    imported = 0
    skipped = 0
    resolved_rows: list[dict] = []

    for row in rows:
        resolved_print = purchase_print_from_deck_row(cursor, row)
        if not resolved_print:
            skipped += 1
            continue
        set_code, collector_number, finish = resolved_print
        resolved_rows.append({
            **row,
            "set_code": set_code,
            "collector_number": collector_number,
            "finish": finish,
            "unit_market": lookup_unit_market(cursor, set_code, collector_number, finish),
        })

    explicit_total = 0.0
    allocation_rows: list[dict] = []
    for row in resolved_rows:
        explicit = row.get("explicit_purchase")
        if explicit is not None:
            explicit_total += explicit * int(row["qty"])
        else:
            allocation_rows.append(row)

    remaining_price = None
    if deck_purchase_price is not None:
        remaining_price = max(deck_purchase_price - explicit_total, 0.0)

    if allocation_rows and remaining_price is not None:
        allocated_prices = allocate_deck_purchase_prices(allocation_rows, remaining_price)
        for row, unit_price in zip(allocation_rows, allocated_prices):
            row["allocated_purchase"] = unit_price

    for row in resolved_rows:
        set_code = row["set_code"]
        collector_number = row["collector_number"]
        finish = row["finish"]
        explicit = row.get("explicit_purchase")

        if explicit is not None:
            if upsert_purchase_value(
                cursor,
                set_code,
                collector_number,
                finish,
                explicit,
                overwrite_zero_only=False,
            ):
                imported += 1
            continue

        allocated = row.get("allocated_purchase")
        if allocated is not None:
            if upsert_purchase_value(
                cursor,
                set_code,
                collector_number,
                finish,
                allocated,
                overwrite_zero_only=True,
            ):
                imported += 1
            continue

        if insert_purchase_if_missing(
            cursor,
            set_code,
            collector_number,
            0.0,
            finish,
        ):
            imported += 1

    log.info(
        "Deck ownership %s (%s): %s new rows, %s unresolved%s",
        deck_entry.path.name,
        deck_entry.name,
        imported,
        skipped,
        f", purchase price {deck_purchase_price:.2f}" if deck_purchase_price else "",
    )
    return imported


# Import purchases from per-set CSV files in data/.
def import_purchases() -> None:
    from lib.purchase_csv_writer import generate_deck_purchase_csvs

    generate_deck_purchase_csvs()
    purchase_files = list_set_csv_files()
    if not purchase_files:
        log.warning("No purchase CSV files found; skipping import")
        return

    log.info("Importing purchases from %s set file(s)", len(purchase_files))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    log.info("Clearing existing purchase rows")
    cursor.execute("DELETE FROM purchases")
    total_rows = 0

    for path in purchase_files:
        total_rows += import_purchase_file(cursor, path)

    ensure_purchase_unique_index(conn)
    sync_card_instances(conn)
    conn.commit()
    conn.close()
    log.info("Purchase import complete: %s rows from set CSV files", total_rows)
