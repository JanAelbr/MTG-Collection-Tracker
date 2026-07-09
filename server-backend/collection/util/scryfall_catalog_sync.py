"""Import one set's card catalog from Scryfall into the local database."""

from datetime import date
import sqlite3

from lib.art_styles import ensure_art_style_rules_file
from lib.config import HTTP_USER_AGENT
from lib.config import normalize_set_code
from report.report_data import load_catalog_count_by_set
from util.db_migrate import ensure_card_columns
from util.price_sync import sync_set_catalog
from util.set_catalog import ensure_sets_table, sync_set_metadata


def import_set_catalog_from_scryfall(
    conn: sqlite3.Connection,
    set_code: str,
    *,
    force_scryfall: bool = True,
) -> int:
    normalized = normalize_set_code(set_code)
    if not normalized:
        raise ValueError("Set code is required")

    ensure_sets_table(conn)
    ensure_card_columns(conn)
    ensure_art_style_rules_file(normalized.lower())

    cursor = conn.cursor()
    today = date.today().isoformat()
    headers = {"User-Agent": HTTP_USER_AGENT}

    if not sync_set_metadata(
        cursor,
        normalized,
        headers,
        today,
        force_scryfall=force_scryfall,
    ):
        raise ValueError(f"Set {normalized} was not found on Scryfall")

    sync_set_catalog(
        cursor,
        normalized.lower(),
        today,
        {normalized},
        force_scryfall=force_scryfall,
    )
    catalog_counts = load_catalog_count_by_set(conn)
    count = catalog_counts.get(normalized, 0)
    if count == 0:
        raise ValueError(f"No cards found for set {normalized} on Scryfall")

    return count
