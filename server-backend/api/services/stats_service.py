import sqlite3

import pandas as pd

from api.cache import get_cache_epoch, memory_cache
from report.report_data import build_sorted_set_options, load_owned_collection_data
from report.report_stats import load_catalog_counts
from report.stats_data import compute_stats_page
from util.price_history import load_price_snapshot_cache
from util.set_completion import (
    count_completion_keys,
    count_completion_keys_by_rarity,
    count_completion_keys_by_set,
)
from util.set_families import resolve_set_codes_for_scope
from api.services import reports_service, settings_service
from api.services.pricing_helpers import (
    apply_strategy_to_neutral_owned_df,
    build_neutral_owned_df,
)

_VALUED_OWNED_TTL = 300

RARITY_ORDER = (
    "common",
    "uncommon",
    "rare",
    "mythic",
    "special",
    "bonus",
    "unknown",
)


def load_collection_stats(
    conn: sqlite3.Connection,
    *,
    set_code: str = "All",
    finish_filter: str = "all",
    family: bool = False,
    art_style: str = "",
    owned_filter: str = "owned",
    type_filter: str = "all",
    color_filters: str = "",
    color_mode: str = "exact",
    search: str = "",
    rarity_filter: str = "all",
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    power_min: float | None = None,
    toughness_min: float | None = None,
    storage_filters: list[str] | None = None,
) -> dict:
    if _has_catalog_filters(
        art_style=art_style,
        owned_filter=owned_filter,
        type_filter=type_filter,
        color_filters=color_filters,
        search=search,
        rarity_filter=rarity_filter,
        cmc_min=cmc_min,
        cmc_max=cmc_max,
        price_min=price_min,
        price_max=price_max,
        power_min=power_min,
        toughness_min=toughness_min,
        storage_filters=storage_filters,
    ):
        return _load_filtered_collection_stats(
            conn,
            set_code=set_code,
            family=family,
            art_style=art_style,
            owned_filter=owned_filter,
            foil_filter=finish_filter,
            type_filter=type_filter,
            color_filters=color_filters,
            color_mode=color_mode,
            search=search,
            rarity_filter=rarity_filter,
            cmc_min=cmc_min,
            cmc_max=cmc_max,
            price_min=price_min,
            price_max=price_max,
            power_min=power_min,
            toughness_min=toughness_min,
            storage_filters=storage_filters,
        )

    settings = settings_service.get_settings(conn)
    strategy = settings["priceStrategy"]
    normalized_set_code = _normalize_set_code(set_code)
    use_family = bool(family) and normalized_set_code != "All"
    family_members = (
        resolve_set_codes_for_scope(conn, set_code=normalized_set_code, family=True)
        if use_family
        else []
    )
    cached_payload = _load_cached_stats_payload(
        set_code=normalized_set_code,
        finish_filter=finish_filter,
        strategy=strategy,
        family=use_family,
    )
    if cached_payload is not None:
        return cached_payload

    if use_family:
        neutral_df = _load_neutral_owned_for_codes(conn, family_members)
        stats_page_key = "All"
    else:
        neutral_df = _load_neutral_owned_df(conn, normalized_set_code)
        stats_page_key = normalized_set_code

    owned_df = apply_strategy_to_neutral_owned_df(neutral_df, strategy)

    if finish_filter == "nonfoil":
        owned_df = owned_df[owned_df["finish"] == 0]
    elif finish_filter == "foil":
        owned_df = owned_df[owned_df["finish"] == 1]
    elif finish_filter == "etched":
        owned_df = owned_df[owned_df["finish"] == 2]

    catalog_df = load_catalog_counts(conn)
    if use_family and family_members:
        member_set = set(family_members)
        catalog_df = catalog_df[catalog_df["set_code"].isin(member_set)].copy()

    favorite_sets = settings_service.get_favorite_sets(conn)
    page_stats = compute_stats_page(
        stats_page_key,
        owned_df,
        catalog_df,
        {},
        conn,
        load_price_snapshot_cache(conn),
        include_client_drilldowns=False,
    )

    payload = {
        "setCode": normalized_set_code,
        "family": use_family,
        "familyMembers": family_members,
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
        family=use_family,
        payload=payload,
    )
    return payload


def _has_catalog_filters(
    *,
    art_style: str,
    owned_filter: str,
    type_filter: str,
    color_filters: str,
    search: str,
    rarity_filter: str,
    cmc_min: float | None,
    cmc_max: float | None,
    price_min: float | None,
    price_max: float | None,
    power_min: float | None,
    toughness_min: float | None,
    storage_filters: list[str] | None,
) -> bool:
    if (art_style or "").strip():
        return True
    if (owned_filter or "owned").strip().lower() != "owned":
        return True
    if (type_filter or "all").strip().lower() != "all":
        return True
    if (color_filters or "").strip():
        return True
    if (search or "").strip():
        return True
    if (rarity_filter or "all").strip().lower() != "all":
        return True
    if any(value is not None for value in (cmc_min, cmc_max, price_min, price_max, power_min, toughness_min)):
        return True
    if storage_filters:
        return True
    return False


def _load_filtered_collection_stats(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    family: bool,
    art_style: str,
    owned_filter: str,
    foil_filter: str,
    type_filter: str,
    color_filters: str,
    color_mode: str,
    search: str,
    rarity_filter: str,
    cmc_min: float | None,
    cmc_max: float | None,
    price_min: float | None,
    price_max: float | None,
    power_min: float | None,
    toughness_min: float | None,
    storage_filters: list[str] | None,
) -> dict:
    scopes = reports_service.build_collection_filter_scopes(
        conn,
        set_code=set_code,
        family=family,
        art_style=art_style,
        owned_filter=owned_filter,
        foil_filter=foil_filter,
        type_filter=type_filter,
        color_filters=color_filters,
        color_mode=color_mode,
        search=search,
        rarity_filter=rarity_filter,
        cmc_min=cmc_min,
        cmc_max=cmc_max,
        price_min=price_min,
        price_max=price_max,
        power_min=power_min,
        toughness_min=toughness_min,
        storage_filters=storage_filters,
    )
    filter_scope = scopes["filterScope"]
    filtered = scopes["filtered"]
    owned_cards = [card for card in filtered if card.get("owned")]
    normalized_set_code = _normalize_set_code(set_code)
    use_family = bool(scopes["family"])
    settings = scopes["settings"]
    favorite_sets = settings_service.get_favorite_sets(conn)

    page_stats = _compute_stats_from_filtered_cards(
        owned_cards,
        filter_scope,
        set_code=normalized_set_code,
        family=use_family,
    )
    return {
        "setCode": normalized_set_code,
        "family": use_family,
        "familyMembers": [],
        "finishFilter": scopes["foilFilter"],
        "foilFilter": scopes["foilFilter"],
        "ownedFilter": scopes["ownedFilter"],
        "artStyle": scopes["artStyle"],
        "artStyles": scopes["artStyles"],
        "priceStrategy": scopes["priceStrategy"],
        "sets": build_sorted_set_options(
            conn,
            favorite_sets=favorite_sets,
            sort_mode=settings["setSortMode"],
            include_all=True,
        ),
        "stats": page_stats,
    }


def _float_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_nullable(values) -> float | None:
    total = None
    for value in values:
        number = _float_or_none(value)
        if number is None:
            continue
        total = number if total is None else total + number
    return total


def _completion_rows(cards: list[dict]) -> list[tuple[str, str]]:
    return [
        (str(card.get("setCode") or ""), str(card.get("collectorNumber") or ""))
        for card in cards
    ]


def _compute_stats_from_filtered_cards(
    owned_cards: list[dict],
    filter_scope: list[dict],
    *,
    set_code: str,
    family: bool,
) -> dict:
    current = _sum_nullable(card.get("currentValue") for card in owned_cards)
    invested = _sum_nullable(card.get("purchaseValue") for card in owned_cards)
    profits = []
    for card in owned_cards:
        profit = card.get("profitLoss")
        if profit is None:
            purchase = _float_or_none(card.get("purchaseValue"))
            value = _float_or_none(card.get("currentValue"))
            if purchase is not None and value is not None and purchase != 0:
                profit = value - purchase
        profits.append(profit)
    profit = _sum_nullable(profits)

    unknown_cards = [
        card for card in owned_cards
        if card.get("currentValue") is None
    ]
    unknown_invested = _sum_nullable(card.get("purchaseValue") for card in unknown_cards)

    single_set = set_code != "All" and not family
    owned_count = count_completion_keys(
        _completion_rows(owned_cards),
        set_code=set_code if single_set else None,
    )
    catalog_count = count_completion_keys(
        _completion_rows(filter_scope),
        set_code=set_code if single_set else None,
    )

    valued = [card for card in owned_cards if card.get("currentValue") is not None]
    average = None
    if valued:
        average = sum(float(card["currentValue"]) for card in valued) / len(valued)

    winners = sum(1 for value in profits if value is not None and value > 0)
    losers = sum(1 for value in profits if value is not None and value < 0)

    stats = {
        "current": current,
        "invested": invested,
        "profit": profit,
        "ownedCount": owned_count,
        "catalogCount": catalog_count,
        "average": average,
        "unknownInvested": unknown_invested,
        "unknownCount": len(unknown_cards),
        "unknownCards": [
            {
                "setCode": card.get("setCode"),
                "collectorNumber": str(card.get("collectorNumber") or ""),
                "name": card.get("name") or "Unknown",
                "artStyle": card.get("artStyle") or "",
                "finish": int(card.get("finish") or 0),
            }
            for card in sorted(
                unknown_cards,
                key=lambda item: (
                    str(item.get("setCode") or ""),
                    str(item.get("collectorNumber") or ""),
                    str(item.get("name") or ""),
                ),
            )
        ],
        "winners": winners,
        "losers": losers,
        "setBreakdown": [],
        "artStyles": [],
        "rarityBreakdown": [],
    }

    if set_code == "All" or family:
        stats["setBreakdown"] = _filtered_set_breakdown(owned_cards, filter_scope)
    else:
        stats["artStyles"] = _filtered_art_style_breakdown(owned_cards)
        stats["rarityBreakdown"] = _filtered_rarity_breakdown(
            owned_cards,
            filter_scope,
            set_code=set_code,
        )
    return stats


def _filtered_set_breakdown(owned_cards: list[dict], filter_scope: list[dict]) -> list[dict]:
    catalog_by_set = count_completion_keys_by_set(_completion_rows(filter_scope))
    grouped: dict[str, list[dict]] = {}
    for card in owned_cards:
        code = str(card.get("setCode") or "").upper()
        if not code:
            continue
        grouped.setdefault(code, []).append(card)

    rows = []
    for code, cards in grouped.items():
        current = _sum_nullable(card.get("currentValue") for card in cards)
        invested = _sum_nullable(card.get("purchaseValue") for card in cards)
        profit = None
        if current is not None or invested is not None:
            profit = (current or 0) - (invested or 0)
        rows.append({
            "setCode": code,
            "count": count_completion_keys(_completion_rows(cards), set_code=code),
            "catalogCount": catalog_by_set.get(code, 0),
            "current": current,
            "invested": invested,
            "profit": profit,
        })
    return sorted(rows, key=lambda row: row["setCode"])


def _filtered_art_style_breakdown(owned_cards: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for card in owned_cards:
        style = str(card.get("artStyle") or "").strip() or "Unknown"
        grouped.setdefault(style, []).append(card)

    rows = []
    for style, cards in grouped.items():
        set_code = str(cards[0].get("setCode") or "")
        current = _sum_nullable(card.get("currentValue") for card in cards)
        invested = _sum_nullable(card.get("purchaseValue") for card in cards)
        profit = None
        if current is not None or invested is not None:
            profit = (current or 0) - (invested or 0)
        rows.append({
            "setCode": set_code,
            "artStyle": style,
            "count": count_completion_keys(_completion_rows(cards), set_code=set_code or None),
            "current": current,
            "invested": invested,
            "profit": profit,
        })
    return sorted(rows, key=lambda row: row["artStyle"])


def _filtered_rarity_breakdown(
    owned_cards: list[dict],
    filter_scope: list[dict],
    *,
    set_code: str,
) -> list[dict]:
    owned_by_rarity = count_completion_keys_by_rarity(
        [
            (
                str(card.get("setCode") or ""),
                str(card.get("collectorNumber") or ""),
                card.get("rarity"),
            )
            for card in owned_cards
        ],
        set_code=set_code,
    )
    catalog_by_rarity = count_completion_keys_by_rarity(
        [
            (
                str(card.get("setCode") or ""),
                str(card.get("collectorNumber") or ""),
                card.get("rarity"),
            )
            for card in filter_scope
        ],
        set_code=set_code,
    )
    rarity_keys = [
        rarity
        for rarity in RARITY_ORDER
        if catalog_by_rarity.get(rarity) or owned_by_rarity.get(rarity)
    ]
    for rarity in sorted({*catalog_by_rarity, *owned_by_rarity}):
        if rarity not in rarity_keys:
            rarity_keys.append(rarity)
    return [
        {
            "rarity": rarity,
            "owned": int(owned_by_rarity.get(rarity, 0)),
            "catalog": int(catalog_by_rarity.get(rarity, 0)),
        }
        for rarity in rarity_keys
    ]


def _page_cache_key(
    set_code: str,
    finish_filter: str,
    strategy: str,
    epoch: int,
    *,
    family: bool = False,
) -> str:
    return memory_cache.make_key(
        "stats.page",
        {
            "setCode": set_code,
            "finishFilter": finish_filter,
            "strategy": strategy,
            "family": bool(family),
        },
        epoch,
    )


def _load_cached_stats_payload(
    *,
    set_code: str,
    finish_filter: str,
    strategy: str,
    family: bool = False,
) -> dict | None:
    epoch = get_cache_epoch()
    return memory_cache.get(
        _page_cache_key(set_code, finish_filter, strategy, epoch, family=family)
    )


def _store_stats_payload_cache(
    *,
    set_code: str,
    finish_filter: str,
    strategy: str,
    payload: dict,
    family: bool = False,
) -> None:
    epoch = get_cache_epoch()
    memory_cache.set(
        _page_cache_key(set_code, finish_filter, strategy, epoch, family=family),
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


def _family_cache_key(set_codes: list[str], epoch: int) -> str:
    return memory_cache.make_key(
        "stats.valued.family",
        {"setCodes": ",".join(sorted(code.upper() for code in set_codes))},
        epoch,
    )


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


def _slice_owned_for_codes(full_df: pd.DataFrame, set_codes: list[str]) -> pd.DataFrame:
    codes = {code.upper() for code in set_codes}
    subset = full_df[full_df["set_code"].isin(codes)]
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


def _load_neutral_owned_for_codes(
    conn: sqlite3.Connection,
    set_codes: list[str],
) -> pd.DataFrame:
    epoch = get_cache_epoch()
    family_key = _family_cache_key(set_codes, epoch)
    cached = memory_cache.get(family_key)
    if cached is not None:
        return cached

    full = memory_cache.get(_owned_cache_key(epoch))
    if full is None:
        full = build_neutral_owned_df(load_owned_collection_data(conn))
        memory_cache.set(_owned_cache_key(epoch), full, _VALUED_OWNED_TTL)
        _populate_set_caches_from_owned(full, epoch)

    subset = _slice_owned_for_codes(full, set_codes)
    memory_cache.set(family_key, subset, _VALUED_OWNED_TTL)
    return subset


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
        "rarityBreakdown": [
            {
                "rarity": row.get("rarity"),
                "owned": int(row.get("owned") or 0),
                "catalog": int(row.get("catalog") or 0),
            }
            for row in (page.get("rarityBreakdown") or [])
        ],
    }
