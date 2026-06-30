import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

from lib.config import DB_PATH, purchase_csv_path
from lib.deck_csv import load_deck_entries
from lib.purchase_csv import (
    card_number_from_row,
    detect_delimiter,
    parse_finish,
    parse_purchase_value,
)
from util.card_finishes import parse_finish_from_row
from lib.purchase_loader import build_deck_purchase_rows
from lib.run_log import get_logger

log = get_logger(__name__)

PURCHASE_CSV_HEADERS = ("card_number", "purchase_value", "finish")


def _purchase_row_key(collector_number: str, finish: int) -> tuple[str, int]:
    return str(collector_number).strip(), int(finish)


def _collector_sort_key(collector_number: str) -> tuple:
    text = str(collector_number).strip()
    digits = "".join(char for char in text if char.isdigit())
    suffix = text[len(digits):].lower() if digits else text.lower()
    number = int(digits) if digits else 0
    return number, suffix, text.lower()


def _format_purchase_value(value: float) -> str:
    rounded = round(float(value), 4)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.4f}".rstrip("0").rstrip(".")


# Read purchase rows from one per-set CSV file.
def read_purchase_csv_rows(csv_path: Path) -> tuple[dict[tuple[str, int], dict], str]:
    if not csv_path.is_file():
        return {}, ","

    delimiter = detect_delimiter(csv_path)
    rows: dict[tuple[str, int], dict] = {}
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            collector_number = card_number_from_row(row)
            if not collector_number:
                continue
            finish = parse_finish_from_row(row, default=parse_finish(row.get("finish")))
            purchase_value = parse_purchase_value(
                row.get("purchase_value") or row.get("price") or row.get("purchase")
            )
            key = _purchase_row_key(collector_number, finish)
            rows[key] = {
                "collector_number": str(collector_number).strip(),
                "finish": finish,
                "purchase_value": purchase_value,
            }
    return rows, delimiter


# Write purchase rows to one per-set CSV file.
def write_purchase_csv_rows(
    csv_path: Path,
    rows: dict[tuple[str, int], dict],
    *,
    delimiter: str = ",",
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(
        rows.values(),
        key=lambda row: (_collector_sort_key(row["collector_number"]), int(row["finish"])),
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(PURCHASE_CSV_HEADERS)
        for row in sorted_rows:
            writer.writerow([
                row["collector_number"],
                _format_purchase_value(row["purchase_value"]),
                int(row["finish"]),
            ])


# Merge deck-derived rows with manual CSV rows; manual rows win on duplicates.
def merge_purchase_rows(
    deck_rows: dict[tuple[str, int], dict],
    manual_rows: dict[tuple[str, int], dict],
) -> dict[tuple[str, int], dict]:
    merged = dict(deck_rows)
    merged.update(manual_rows)
    return merged


# Collect deck purchase rows grouped by lowercase set code.
def collect_deck_purchase_rows_by_set(
    cursor: sqlite3.Cursor,
    deck_entries,
) -> dict[str, dict[tuple[str, int], dict]]:
    by_set: dict[str, dict[tuple[str, int], dict]] = defaultdict(dict)
    for deck_entry in deck_entries:
        for row in build_deck_purchase_rows(cursor, deck_entry):
            set_code = str(row["set_code"]).lower()
            key = _purchase_row_key(row["collector_number"], row["finish"])
            by_set[set_code][key] = {
                "collector_number": str(row["collector_number"]).strip(),
                "finish": int(row["finish"]),
                "purchase_value": float(row["purchase_value"]),
            }
    return dict(by_set)


# Write merged per-set purchase CSV files from registered deck lists.
def generate_deck_purchase_csvs() -> int:
    deck_entries = load_deck_entries()
    if not deck_entries:
        log.info("No deck CSV files registered; skipping deck purchase CSV generation")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    deck_rows_by_set = collect_deck_purchase_rows_by_set(cursor, deck_entries)
    conn.close()

    written = 0
    for set_code, deck_rows in sorted(deck_rows_by_set.items()):
        csv_path = purchase_csv_path(set_code)
        manual_rows, delimiter = read_purchase_csv_rows(csv_path)
        merged_rows = merge_purchase_rows(deck_rows, manual_rows)
        write_purchase_csv_rows(csv_path, merged_rows, delimiter=delimiter)
        written += 1
        log.info(
            "Wrote purchase CSV %s (%s deck rows, %s manual rows, %s total)",
            csv_path.name,
            len(deck_rows),
            len(manual_rows),
            len(merged_rows),
        )
    return written
