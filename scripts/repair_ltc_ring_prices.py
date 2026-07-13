"""Repair LTC Rings of Power Sol Ring URLs and resync market values."""

from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server-backend" / "collection"))

from lib.config import DB_PATH
from util.cardmarket_prices import load_price_guide_index, sync_prices_from_guide
from util.cardmarket_urls import backfill_cardmarket_urls
from util.scryfall_catalog_sync import import_set_catalog_from_scryfall

RING_COLLECTORS = ("408", "409", "410", "408z", "409z", "410z")


def print_ring_rows(conn: sqlite3.Connection, title: str) -> None:
    print(f"\n=== {title} ===")
    for row in conn.execute(
        """
        SELECT collector_number, market_value, market_value_foil,
               cardmarket_url, cardmarket_url_foil
        FROM cards
        WHERE set_code = 'LTC' AND collector_number IN (?, ?, ?, ?, ?, ?)
        ORDER BY collector_number
        """,
        RING_COLLECTORS,
    ):
        print(
            f"#{row[0]}: mv={row[1]} foil_mv={row[2]} "
            f"url={row[3]} foil_url={row[4]}"
        )


def main() -> None:
    print("DB_PATH", DB_PATH)
    guide = load_price_guide_index()

    with sqlite3.connect(DB_PATH) as conn:
        print_ring_rows(conn, "Before")
        import_set_catalog_from_scryfall(conn, "LTC", force_scryfall=True)
        backfilled = backfill_cardmarket_urls(conn, guide)
        conn.commit()
        print(f"\nBackfilled {backfilled} Cardmarket URL row(s)")
        print_ring_rows(conn, "After URL repair")

    result = sync_prices_from_guide(
        date.today().isoformat(),
        set_codes={"LTC"},
        missing_only=False,
    )
    print("\nPrice sync:", result)

    with sqlite3.connect(DB_PATH) as conn:
        print_ring_rows(conn, "After price sync")


if __name__ == "__main__":
    main()
