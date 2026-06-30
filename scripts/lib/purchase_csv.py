import csv
from pathlib import Path


# Detect whether a CSV file uses comma or semicolon separators.
def detect_delimiter(csv_path: Path) -> str:
    first_line = csv_path.read_text(encoding="utf-8").splitlines()[0]
    return ";" if ";" in first_line else ","


# Read the collector number from a purchase CSV row.
def card_number_from_row(row: dict) -> str | None:
    return row.get("card_number") or row.get("collector_number")


# Parse a purchase value from CSV text into a float.
def parse_purchase_value(raw_value) -> float:
    if raw_value in (None, ""):
        return 0.0
    try:
        return float(str(raw_value).replace(",", "."))
    except ValueError:
        return 0.0


# Parse finish id from CSV text.
def parse_finish(raw_value) -> int:
    text = str(raw_value).strip().lower()
    if text in ("2", "etched"):
        return 2
    if text in ("1", "true", "yes", "y", "foil"):
        return 1
    return 0
