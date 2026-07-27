"""Import one set's card catalog from Scryfall into the local database."""

from datetime import date
import sqlite3

from lib.config import HTTP_USER_AGENT
from lib.config import normalize_set_code
from util.db_migrate import ensure_card_columns
from util.price_sync import set_catalog_is_complete, sync_set_catalog
from util.set_catalog import ensure_sets_table, sync_set_metadata


def _catalog_card_count(conn: sqlite3.Connection, set_code: str) -> int:
    """Count cards for a set directly (avoids stale report_data caches mid-import)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM cards WHERE set_code = ?",
        (normalize_set_code(set_code),),
    ).fetchone()
    return int(row[0] or 0) if row else 0


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

    if force_scryfall or not set_catalog_is_complete(cursor, normalized):
        sync_set_catalog(
            cursor,
            normalized.lower(),
            today,
            {normalized},
            force_scryfall=force_scryfall,
        )
    count = _catalog_card_count(conn, normalized)
    if count == 0:
        raise ValueError(f"No cards found for set {normalized} on Scryfall")

    return count
