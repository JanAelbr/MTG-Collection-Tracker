import csv
import re
from dataclasses import dataclass
from pathlib import Path

from lib.config import DECKS_DIR, DECKS_MANIFEST_NAME
from lib.purchase_csv import detect_delimiter, parse_finish, parse_purchase_value
from util.card_finishes import FINISH_FOIL, parse_finish_from_row
from lib.deck_purchase import explicit_purchase_from_row

DEFAULT_SECTION = "main"
VALID_SECTIONS = frozenset({"main", "commander", "sideboard"})
DECK_CARD_COLUMNS = (
    "set_code",
    "collector_number",
    "finish",
    "qty",
    "owned",
    "section",
)
DECK_MANIFEST_COLUMNS = ("deck_name", "purchase_price", "csv_location")


# Official precon names that differ from catalog card names in tracked sets.
CARD_NAME_ALIASES = {
    "The Necropolis": "Vault 12: The Necropolis",
    "Forced Evolution": "Vault 87: Forced Evolution",
    "Looter Il-Kor": "Looter il-Kor",
    "An Offer You Can't Refuse": "An Offer You Can\u2019t Refuse",
}


@dataclass(frozen=True)
class DeckEntry:
    name: str
    purchase_price: float | None
    path: Path
    slug: str


# Parse deck quantity from CSV text.
def parse_qty(raw_value, default: int = 1) -> int:
    if raw_value in (None, ""):
        return default
    try:
        qty = int(str(raw_value).strip())
    except ValueError:
        return default
    return qty if qty > 0 else default


# Parse owned copy count from CSV text, defaulting to one owned copy.
def parse_owned(raw_value, qty: int, default: int = 1) -> int:
    if raw_value in (None, ""):
        owned = default
    else:
        try:
            owned = int(str(raw_value).strip())
        except ValueError:
            owned = default
    owned = max(0, owned)
    return min(owned, qty)


# Normalize a deck section label.
def parse_section(raw_value) -> str:
    section = str(raw_value or DEFAULT_SECTION).strip().lower()
    if section not in VALID_SECTIONS:
        return DEFAULT_SECTION
    return section


# Parse an optional deck purchase price from manifest text.
def parse_deck_purchase_price(raw_value) -> float | None:
    if raw_value in (None, ""):
        return None
    try:
        value = float(str(raw_value).replace(",", "."))
    except ValueError:
        return None
    return value if value > 0 else None


# Read card name from a deck CSV row.
def card_name_from_row(row: dict) -> str | None:
    for key in ("name", "card_name", "card"):
        value = row.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


# Read optional explicit print columns from a deck CSV row.
def print_from_row(row: dict) -> tuple[str | None, str | None]:
    set_code = row.get("set_code") or row.get("set")
    collector_number = row.get("collector_number") or row.get("card_number")
    if set_code and collector_number:
        return str(set_code).upper(), str(collector_number).strip()
    return None, None


# Convert a deck filename stem into a display name.
def deck_name_from_slug(slug: str) -> str:
    words = re.sub(r"[_-]+", " ", slug).strip().split()
    return " ".join(word.capitalize() for word in words)


def resolve_print_from_catalog(
    conn,
    card_name: str,
    preferred_set_codes: tuple[str, ...] = (),
) -> tuple[str, str] | None:
    candidates = [card_name.strip()]
    alias = CARD_NAME_ALIASES.get(card_name.strip())
    if alias:
        candidates.append(alias)

    for candidate in candidates:
        for set_code in preferred_set_codes:
            row = conn.execute(
                """
                SELECT set_code, collector_number
                FROM cards
                WHERE name = ? COLLATE NOCASE AND set_code = ?
                ORDER BY CAST(collector_number AS INTEGER), collector_number
                LIMIT 1
                """,
                (candidate, str(set_code).upper()),
            ).fetchone()
            if row:
                return row[0], row[1]

        row = conn.execute(
            """
            SELECT set_code, collector_number
            FROM cards
            WHERE name = ? COLLATE NOCASE
            ORDER BY set_code, CAST(collector_number AS INTEGER), collector_number
            LIMIT 1
            """,
            (candidate,),
        ).fetchone()
        if row:
            return row[0], row[1]
    return None


def build_deck_rows_from_names(
    conn,
    rows: list[tuple[str, int, str]],
    preferred_set_codes: tuple[str, ...],
) -> tuple[list[dict], list[str]]:
    built: list[dict] = []
    missing: list[str] = []
    for name, qty, section in rows:
        resolved = resolve_print_from_catalog(conn, name, preferred_set_codes)
        if not resolved:
            missing.append(name)
            continue
        set_code, collector_number = resolved
        built.append({
            "set_code": set_code,
            "collector_number": collector_number,
            "finish": FINISH_FOIL,
            "qty": qty,
            "owned_qty": min(qty, 1),
            "section": section,
        })
    return built, missing


def decks_manifest_path() -> Path:
    return DECKS_DIR / DECKS_MANIFEST_NAME


# Resolve one manifest csv_location value to a deck CSV path.
def resolve_deck_csv_path(csv_location: str) -> Path:
    location = Path(str(csv_location).strip())
    if location.is_absolute():
        return location
    return DECKS_DIR / location.name


# Load deck metadata and card file locations from data/decks/decks.csv.
def load_deck_entries() -> list[DeckEntry]:
    manifest_path = decks_manifest_path()
    if not manifest_path.is_file():
        return []

    delimiter = detect_delimiter(manifest_path)
    entries: list[DeckEntry] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            csv_location = (
                row.get("csv_location")
                or row.get("file")
                or row.get("csv")
                or ""
            ).strip()
            if not csv_location:
                continue
            path = resolve_deck_csv_path(csv_location)
            slug = path.stem.lower()
            deck_name = str(row.get("deck_name") or deck_name_from_slug(slug)).strip()
            entries.append(
                DeckEntry(
                    name=deck_name,
                    purchase_price=parse_deck_purchase_price(row.get("purchase_price")),
                    path=path,
                    slug=slug,
                )
            )
    return entries


# Resolve one deck manifest entry from a slug, filename, or display name.
def find_deck_entry(deck_key: str) -> DeckEntry | None:
    key = deck_key.strip()
    if not key:
        return None

    normalized = Path(key).stem.lower().replace(" ", "_").replace("-", "_")
    entries = load_deck_entries()

    for entry in entries:
        if entry.slug == normalized:
            return entry
        if entry.path.name.casefold() == key.casefold():
            return entry

    for entry in entries:
        if entry.name.casefold() == key.casefold():
            return entry

    partial = [
        entry
        for entry in entries
        if entry.slug == normalized or entry.slug.startswith(f"{normalized}_")
    ]
    if len(partial) == 1:
        return partial[0]
    return None


# Write the deck manifest file.
def write_deck_entries(entries: list[DeckEntry]) -> Path:
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = decks_manifest_path()
    sorted_entries = sorted(entries, key=lambda entry: entry.name.lower())
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(DECK_MANIFEST_COLUMNS)
        for entry in sorted_entries:
            writer.writerow([
                entry.name,
                "" if entry.purchase_price is None else entry.purchase_price,
                entry.path.name,
            ])
    return manifest_path


# Insert or update one deck in the manifest, preserving purchase price when omitted.
def upsert_deck_manifest_entry(
    slug: str,
    name: str,
    filename: str,
    *,
    purchase_price: float | None = None,
) -> None:
    entries = {entry.slug: entry for entry in load_deck_entries()}
    existing = entries.get(slug.lower())
    resolved_price = purchase_price
    if resolved_price is None and existing is not None:
        resolved_price = existing.purchase_price
    entries[slug.lower()] = DeckEntry(
        name=name,
        purchase_price=resolved_price,
        path=DECKS_DIR / filename,
        slug=slug.lower(),
    )
    write_deck_entries(list(entries.values()))


# Collect unique set codes referenced by deck CSV print columns.
def list_deck_sync_set_codes() -> list[str]:
    codes: set[str] = set()
    for entry in load_deck_entries():
        for row in read_deck_card_rows(entry.path):
            set_code = row.get("set_code")
            if set_code:
                codes.add(str(set_code).upper())
    return sorted(codes)


# Read card rows from one deck CSV file.
def read_deck_card_rows(deck_file: Path) -> list[dict]:
    delimiter = detect_delimiter(deck_file)
    rows: list[dict] = []

    with deck_file.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for index, row in enumerate(reader):
            set_code, collector_number = print_from_row(row)
            card_name = card_name_from_row(row)
            if not ((set_code and collector_number) or card_name):
                continue
            qty = parse_qty(row.get("qty"))
            rows.append({
                "card_name": card_name,
                "set_code": set_code,
                "collector_number": collector_number,
                "qty": qty,
                "owned_qty": parse_owned(row.get("owned"), qty),
                "finish": parse_finish_from_row(row, default=parse_finish(row.get("finish"))),
                "section": parse_section(row.get("section")),
                "sort_order": index,
                "explicit_purchase": explicit_purchase_from_row(row),
            })

    return rows


# Sort deck rows by set code and numeric collector number.
def deck_card_sort_key(row: dict) -> tuple:
    set_code = str(row.get("set_code") or "").upper()
    collector_number = str(row.get("collector_number") or "")
    digits = "".join(char for char in collector_number if char.isdigit())
    suffix = collector_number[len(digits):].lower() if digits else collector_number.lower()
    number = int(digits) if digits else 0
    return (set_code, number, suffix)


# Write card rows to one deck CSV file.
def write_deck_card_rows(deck_file: Path, rows: list[dict]) -> None:
    deck_file.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=deck_card_sort_key)
    with deck_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(DECK_CARD_COLUMNS)
        for row in sorted_rows:
            writer.writerow([
                row.get("set_code") or "",
                row.get("collector_number") or "",
                row.get("finish", row.get("foil", 0)),
                row.get("qty", 1),
                row.get("owned_qty", row.get("owned", 1)),
                row.get("section", DEFAULT_SECTION),
            ])


# Rewrite one deck CSV file using the current column layout.
def migrate_deck_card_csv(deck_file: Path) -> int:
    rows = read_deck_card_rows(deck_file)
    write_deck_card_rows(deck_file, rows)
    return len(rows)


# Rewrite all registered deck CSV files using the current column layout.
def migrate_all_deck_card_csvs() -> int:
    migrated = 0
    for entry in load_deck_entries():
        if not entry.path.is_file():
            continue
        migrate_deck_card_csv(entry.path)
        migrated += 1
    return migrated


# Read deck metadata and card rows for one registered deck.
def read_deck_csv_rows(deck_entry: DeckEntry) -> tuple[str, list[dict], float | None]:
    return (
        deck_entry.name,
        read_deck_card_rows(deck_entry.path),
        deck_entry.purchase_price,
    )
