"""Import one deck list from data/decks/ into the database.

Usage:
    python scripts/deck_sync.py sedris
    python scripts/deck_sync.py sedris_the_traitor_king.csv
    python scripts/deck_sync.py "Sedris, the Traitor King"
"""

import argparse
import sys

from lib.deck_loader import import_deck
from lib.run_log import configure_logging, get_logger

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import one deck list from data/decks/decks.csv into the database.",
    )
    parser.add_argument(
        "deck",
        help="Deck slug, CSV filename, or display name from data/decks/decks.csv",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress logging.",
    )
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

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
