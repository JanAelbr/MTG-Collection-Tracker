"""Load collection data from CSV files into the database."""

from lib.deck_loader import import_decks
from lib.purchase_loader import import_purchases
from lib.run_log import get_logger

log = get_logger(__name__)


# Import deck lists and rebuild purchase ownership from CSV sources.
def sync_collection() -> None:
    log.info("Syncing collection from CSV files")
    import_decks()
    import_purchases()
    log.info("Collection sync complete")
