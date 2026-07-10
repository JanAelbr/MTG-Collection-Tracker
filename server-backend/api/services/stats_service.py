import sqlite3

from api.cache import get_cache_epoch, memory_cache
from report.report_data import build_sorted_set_options, load_owned_collection_data
from report.report_stats import load_catalog_counts
from report.stats_data import compute_stats_page
from util.price_history import load_price_snapshot_cache
from api.services import settings_service
from api.services.pricing_helpers import (
    apply_strategy_to_neutral_owned_df,
    build_neutral_owned_df,
)

_VALUED_OWNED_TTL = 300


def load_collection_stats(
    conn: sqlite3.Connection,
    *,
    set_code: str = "All",
    finish_filter: str = "all",
) -> dict:
    settings = settings_service.get_settings(conn)
    strategy = settings["priceStrategy"]
    normalized_set_code = _normalize_set_code(set_code)
    cached_payload = _load_cached_stats_payload(
        set_code=normalized_set_code,
        finish_filter=finish_filter,
        strategy=strategy,
    )
    if cached_payload is not None:
        return cached_payload

    neutral_df = _load_neutral_owned_df(conn, normalized_set_code)
    owned_df = apply_strategy_to_neutral_owned_df(neutral_df, strategy)

    if finish_filter == "nonfoil":
        owned_df = owned_df[owned_df["finish"] == 0]
    elif finish_filter == "foil":
        owned_df = owned_df[owned_df["finish"] == 1]
    elif finish_filter == "etched":
        owned_df = owned_df[owned_df["finish"] == 2]

    catalog_df = load_catalog_counts(conn)
    favorite_sets = settings_service.get_favorite_sets(conn)
    page_stats = compute_stats_page(
        normalized_set_code,
        owned_df,
        catalog_df,
        {},
        conn,
        load_price_snapshot_cache(conn),
        include_client_drilldowns=False,
    )

    payload = {
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
    _store_stats_payload_cache(
        set_code=normalized_set_code,
        finish_filter=finish_filter,
        strategy=strategy,
        payload=payload,
    )
    return payload


def _page_cache_key(set_code: str, finish_filter: str, strategy: str, epoch: int) -> str:
    return memory_cache.make_key(
        "stats.page",
        {"setCode": set_code, "finishFilter": finish_filter, "strategy": strategy},
        epoch,
    )


def _load_cached_stats_payload(
    *,
    set_code: str,
    finish_filter: str,
    strategy: str,
) -> dict | None:
    epoch = get_cache_epoch()
    return memory_cache.get(_page_cache_key(set_code, finish_filter, strategy, epoch))


def _store_stats_payload_cache(
    *,
    set_code: str,
    finish_filter: str,
    strategy: str,
    payload: dict,
) -> None:
    epoch = get_cache_epoch()
    memory_cache.set(
        _page_cache_key(set_code, finish_filter, strategy, epoch),
        payload,
        _VALUED_OWNED_TTL,
    )


def _normalize_set_code(set_code: str) -> str:
    normalized = (set_code or "All").strip()
    if normalized.lower() == "all":
        return "All"
    return normalized.upper()


def _owned_cache_key(epoch: int) -> str:
    return memory_cache.make_key("stats.valued.owned", {}, epoch)


def _set_cache_key(set_code: str, epoch: int) -> str:
    return memory_cache.make_key("stats.valued.set", {"setCode": set_code}, epoch)


def _populate_set_caches_from_owned(full_df: pd.DataFrame, epoch: int) -> None:
    if full_df.empty:
        return
    for set_code, group in full_df.groupby("set_code", sort=False):
        normalized = str(set_code).upper()
        cache_key = _set_cache_key(normalized, epoch)
        if memory_cache.get(cache_key) is None:
            memory_cache.set(cache_key, group.copy(), _VALUED_OWNED_TTL)


def _slice_owned_for_set(full_df: pd.DataFrame, set_code: str) -> pd.DataFrame:
    subset = full_df[full_df["set_code"] == set_code]
    return subset.copy()


def _load_neutral_owned_df(conn: sqlite3.Connection, set_code: str) -> pd.DataFrame:
    epoch = get_cache_epoch()
    if set_code == "All":
        cache_key = _owned_cache_key(epoch)
        cached = memory_cache.get(cache_key)
        if cached is not None:
            return cached

        neutral = build_neutral_owned_df(load_owned_collection_data(conn))
        memory_cache.set(cache_key, neutral, _VALUED_OWNED_TTL)
        _populate_set_caches_from_owned(neutral, epoch)
        return neutral

    set_key = _set_cache_key(set_code, epoch)
    cached = memory_cache.get(set_key)
    if cached is not None:
        return cached

    full = memory_cache.get(_owned_cache_key(epoch))
    if full is not None:
        subset = _slice_owned_for_set(full, set_code)
        memory_cache.set(set_key, subset, _VALUED_OWNED_TTL)
        return subset

    neutral = build_neutral_owned_df(load_owned_collection_data(conn, set_code))
    memory_cache.set(set_key, neutral, _VALUED_OWNED_TTL)
    return neutral


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
