import sqlite3



from report.deck_queries import enrich_deck_cards_df, load_deck_cards_df, load_deck_list

from report.deck_stats_data import compute_deck_stats_page

from api.services import settings_service

from api.services.pricing_helpers import apply_strategy_to_deck_df

from util.price_history import load_price_snapshot_cache





class DeckError(Exception):

    def __init__(self, message: str, status_code: int = 404):

        super().__init__(message)

        self.message = message

        self.status_code = status_code





def list_decks(conn: sqlite3.Connection) -> dict:

    return {"decks": load_deck_list(conn)}





def _load_strategy_deck_df(conn: sqlite3.Connection) -> tuple[str, object]:

    settings = settings_service.get_settings(conn)

    strategy = settings["priceStrategy"]

    deck_df = apply_strategy_to_deck_df(

        enrich_deck_cards_df(load_deck_cards_df(conn)),

        strategy,

    )

    return strategy, deck_df





def load_deck_stats(

    conn: sqlite3.Connection,

    *,

    deck_id: str = "All",

) -> dict:

    decks = load_deck_list(conn)

    if deck_id not in ("All", "all") and not any(str(d["id"]) == str(deck_id) for d in decks):

        raise DeckError("Deck not found")



    strategy, deck_df = _load_strategy_deck_df(conn)

    snapshot_cache = load_price_snapshot_cache(conn)

    stats = compute_deck_stats_page(

        deck_id,

        deck_df,

        conn,

        snapshot_cache=snapshot_cache,

        include_portfolio_history=False,

    )

    return {

        "deckId": deck_id,

        "priceStrategy": strategy,

        "decks": decks,

        "stats": _serialize_deck_stats(stats),

    }





def load_deck_browse_index(conn: sqlite3.Connection) -> dict:

    strategy, deck_df = _load_strategy_deck_df(conn)

    decks = load_deck_list(conn)

    pages = {

        str(deck["id"]): _serialize_deck_stats(

            compute_deck_stats_page(

                str(deck["id"]),

                deck_df,

                conn,

                include_portfolio_history=False,

            )

        )

        for deck in decks

    }

    return {

        "priceStrategy": strategy,

        "decks": decks,

        "pages": pages,

    }





def load_deck_browse(

    conn: sqlite3.Connection,

    *,

    deck_id: str,

) -> dict:

    decks = load_deck_list(conn)

    deck = next((item for item in decks if str(item["id"]) == str(deck_id)), None)

    if deck is None:

        raise DeckError("Deck not found")



    strategy, deck_df = _load_strategy_deck_df(conn)

    stats = compute_deck_stats_page(

        deck_id,

        deck_df,

        conn,

        include_portfolio_history=False,

    )

    return {

        "deckId": str(deck_id),

        "deck": deck,

        "decks": decks,

        "priceStrategy": strategy,

        "stats": _serialize_deck_stats(stats),

    }





def _serialize_deck_stats(stats: dict) -> dict:

    return {

        "current": stats.get("current"),

        "ownedCurrent": stats.get("ownedCurrent"),

        "invested": stats.get("invested"),

        "profit": stats.get("profit"),

        "purchasePrice": stats.get("purchasePrice"),

        "deckSize": stats.get("deckSize"),

        "trackedQty": stats.get("trackedQty"),

        "ownedQty": stats.get("ownedQty"),

        "missingQty": stats.get("missingQty"),

        "trackedCoverage": stats.get("trackedCoverage"),

        "ownedCoverage": stats.get("ownedCoverage"),

        "average": stats.get("average"),

        "unknownQty": stats.get("unknownQty"),

        "unknownCount": stats.get("unknownCount"),

        "unknownCards": stats.get("unknownCards") or [],

        "winners": stats.get("winners"),

        "losers": stats.get("losers"),

        "cards": [

            {

                "deckId": card.get("deck_id"),

                "deckName": card.get("deck_name"),

                "cardName": card.get("card_name"),

                "setCode": card.get("set_code"),

                "collectorNumber": card.get("collector_number"),

                "finish": card.get("finish"),
                "foil": card.get("finish"),

                "qty": card.get("qty"),

                "section": card.get("section"),

                "ownedQty": card.get("owned_qty"),

                "currentValue": card.get("current_value"),

                "unitValue": card.get("unit_value"),

                "invested": card.get("invested"),

                "profitLoss": card.get("profit_loss"),

                "imageUri": card.get("image_uri"),

                "colors": card.get("colors") or [],

                "typeLine": card.get("type_line") or "",

                "cardType": card.get("card_type") or "",

                "cardTypes": card.get("card_types") or [],

                "cardmarketUrl": card.get("cardmarket_url"),

                "inCatalog": card.get("in_catalog"),

            }

            for card in (stats.get("cards") or [])

        ],

    }


