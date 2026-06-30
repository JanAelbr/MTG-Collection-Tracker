import sqlite3

from lib.config import DB_PATH
from report.deck_queries import enrich_deck_cards_df, load_deck_cards_df, load_deck_list
from report.deck_stats_data import compute_deck_stats_page


# Build client payload for the deck browser report.
def load_decks_client_payload() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        deck_df = enrich_deck_cards_df(load_deck_cards_df(conn))
        decks = load_deck_list(conn)
        pages = {
            str(deck["id"]): compute_deck_stats_page(
                str(deck["id"]),
                deck_df,
                conn,
                include_portfolio_history=False,
            )
            for deck in decks
        }

    return {
        "decks": decks,
        "pages": pages,
    }
