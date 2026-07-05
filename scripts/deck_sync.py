"""Import one deck list from data/decks/ into the database.

Usage:
    python scripts/deck_sync.py sedris
    python scripts/deck_sync.py sedris_the_traitor_king.csv
    python scripts/deck_sync.py "Sedris, the Traitor King"
"""

import argparse
import sys

from lib.deck_loader import import_deck, reconcile_deck_card_finishes
from lib.run_log import configure_logging, get_logger

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import one deck list from data/decks/decks.csv into the database.",
    )
    parser.add_argument(
        "deck",
        nargs="?",
        help="Deck slug, CSV filename, or display name from data/decks/decks.csv",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress logging.",
    )
    parser.add_argument(
        "--reconcile-finishes",
        action="store_true",
        help="Fix deck card finishes against catalog data without re-importing CSV rows.",
    )
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    if args.reconcile_finishes:
        import sqlite3

        from lib.card_locations import sync_card_instances
        from lib.config import DB_PATH
        from util.deck_tables import ensure_deck_tables

        conn = sqlite3.connect(DB_PATH)
        ensure_deck_tables(conn)
        cursor = conn.cursor()
        updated = reconcile_deck_card_finishes(cursor)
        synced = sync_card_instances(conn)
        conn.commit()
        conn.close()
        log.info(
            "Reconciled finish on %s deck card(s); synced %s instance row(s)",
            updated,
            synced,
        )
        return 0

    if not args.deck:
        parser.error("deck is required unless --reconcile-finishes is used")

    log.info("Syncing deck: %s", args.deck)
    try:
        stats = import_deck(args.deck)
    except (ValueError, FileNotFoundError) as exc:
        log.error("%s", exc)
        return 1

    log.info(
        "Deck sync complete: %s (%s cards, %s in catalog)",
        stats["name"],
        stats["card_count"],
        stats["tracked_count"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
