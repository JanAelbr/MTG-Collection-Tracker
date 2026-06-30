"""Import deck lists and purchase CSVs into the database.

Usage:
    python scripts/sync_collection.py
    python scripts/deck_sync.py sedris   # single deck only, then purchase_import if needed
"""

import argparse

from lib.collection_sync import sync_collection
from lib.run_log import configure_logging, get_logger

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import deck lists and purchase CSVs into the database.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress logging.",
    )
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)
    sync_collection()


if __name__ == "__main__":
    main()
