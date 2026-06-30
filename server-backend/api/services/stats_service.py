import sqlite3

from report.report_data import build_sorted_set_options, get_all_set_codes, load_collection_data
from report.report_pages import build_pages, select_owned_cards
from report.report_stats import load_catalog_counts
from report.stats_data import load_stats_client_payload
from api.services import settings_service
from api.services.pricing_helpers import apply_strategy_to_owned_df


def load_collection_stats(
    conn: sqlite3.Connection,
    *,
    set_code: str = "All",
    finish_filter: str = "all",
) -> dict:
    settings = settings_service.get_settings(conn)
    strategy = settings["priceStrategy"]
    cards_df, _ = load_collection_data(owned_only=True, conn=conn)
    owned_df = select_owned_cards(cards_df, True)
    owned_df = apply_strategy_to_owned_df(owned_df, strategy)

    if finish_filter == "nonfoil":
        owned_df = owned_df[owned_df["finish"] == 0]
    elif finish_filter == "foil":
        owned_df = owned_df[owned_df["finish"] == 1]
    elif finish_filter == "etched":
        owned_df = owned_df[owned_df["finish"] == 2]

    catalog_df = load_catalog_counts(conn)
    favorite_sets = settings_service.get_favorite_sets(conn)
    page_codes = get_all_set_codes()
    normalized_set_code = "All" if str(set_code).lower() == "all" else set_code
    payload = load_stats_client_payload(owned_df, catalog_df, build_pages(page_codes), conn=conn)
    pages = payload.get("pages", {})
    page_stats = pages.get(normalized_set_code, pages.get("All", {}))

    return {
        "setCode": normalized_set_code,
        "finishFilter": finish_filter,
        "foilFilter": finish_filter,
        "priceStrategy": strategy,
        "sets": build_sorted_set_options(
            conn,
            favorite_sets=favorite_sets,
            sort_mode=settings["setSortMode"],
            include_all=True,
        ),
        "stats": _serialize_stats_page(page_stats),
    }


def _serialize_stats_page(page: dict) -> dict:
    return {
        "current": page.get("current"),
        "invested": page.get("invested"),
        "profit": page.get("profit"),
        "ownedCount": page.get("ownedCount"),
        "catalogCount": page.get("catalogCount"),
        "average": page.get("average"),
        "unknownInvested": page.get("unknownInvested"),
        "unknownCount": page.get("unknownCount"),
        "unknownCards": page.get("unknownCards") or [],
        "winners": page.get("winners"),
        "losers": page.get("losers"),
        "setBreakdown": [
            {
                "setCode": row.get("set_code"),
                "count": row.get("count"),
                "catalogCount": row.get("catalog_count"),
                "current": row.get("current"),
                "invested": row.get("invested"),
                "profit": row.get("profit"),
            }
            for row in (page.get("setBreakdown") or [])
        ],
        "artStyles": [
            {
                "setCode": row.get("set_code"),
                "artStyle": row.get("art_style"),
                "count": row.get("count"),
                "current": row.get("current"),
                "invested": row.get("invested"),
                "profit": row.get("profit"),
            }
            for row in (page.get("artStyles") or [])
        ],
    }
