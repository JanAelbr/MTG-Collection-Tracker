import sqlite3

from api.cache import get_cache_epoch, memory_cache
from report.card_detail_data import collector_sort_key
from report.ranked_cards_data import (
    DEFAULT_PAGE_SIZE,
    load_ranked_cards_data_for_set,
    serialize_ranked_cards,
)
from report.report_data import build_art_style_options, build_sorted_set_options
from api.services.pricing_service import (
    value_from_strategy_map,
    values_by_strategy_for_finish,
)
from api.services import settings_service
from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql
from util.cardmarket_urls import cardmarket_url_for_finish
from util.card_metadata import (
    COLLECTION_FILTER_TYPES,
    card_matches_collection_cmc_filter,
    card_matches_collection_color_filter,
    card_matches_collection_price_filter,
    card_matches_collection_rarity_filter,
    card_matches_collection_stat_filter,
    card_matches_collection_storage_filter,
    card_matches_collection_type_filter,
    card_metadata_api,
    parse_collection_color_filters,
)
from util.card_name_roles import load_card_name_roles_map
from util.price_history import (
    card_price_key,
    default_compare_date,
    get_compare_dates,
    get_price_snapshot_dates,
    load_price_snapshot_cache,
)

_ENRICHED_REPORTS_TTL = 300

REPORT_TYPES = frozenset({"risers", "fallers", "all"})
OWNED_FILTERS = frozenset({"owned", "all", "unowned"})
FOIL_FILTERS = frozenset({"all", "nonfoil", "foil", "etched"})
TYPE_FILTERS = frozenset({"all", *COLLECTION_FILTER_TYPES})


class ReportsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def load_reports_meta(conn: sqlite3.Connection) -> dict:
    from util.set_family_sync import ensure_tracked_family_children_once

    ensure_tracked_family_children_once(conn)
    settings = settings_service.get_settings(conn)
    dates = get_price_snapshot_dates(conn)
    compare_dates = get_compare_dates(dates)
    favorite_sets = settings_service.get_favorite_sets(conn)
    sets = build_sorted_set_options(
        conn,
        favorite_sets=favorite_sets,
        sort_mode=settings["setSortMode"],
        include_all=True,
    )
    non_all_sets = [item for item in sets if item["setCode"] != "All"]
    return {
        "defaultPageSize": settings["pageSize"],
        "compareDates": compare_dates,
        "defaultCompareDate": default_compare_date(dates),
        "latestSnapshotDate": dates[0] if dates else None,
        "priceStrategy": settings["priceStrategy"],
        "priceStrategies": settings["priceStrategies"],
        "sets": sets,
        "favoriteSets": favorite_sets,
        "defaultSet": non_all_sets[0]["setCode"] if non_all_sets else "All",
        "compareDate": settings["compareDate"],
    }


def list_report_cards(
    conn: sqlite3.Connection,
    *,
    report: str,
    set_code: str = "All",
    family: bool = False,
    art_style: str = "",
    owned_filter: str = "owned",
    foil_filter: str = "all",
    type_filter: str = "all",
    color_filters: str = "",
    compare_date: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str = "",
    rarity_filter: str = "all",
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    power_min: float | None = None,
    toughness_min: float | None = None,
    storage_filters: list[str] | None = None,
    sort: str = "number",
    sort_dir: str = "",
    page: int | None = None,
) -> dict:
    normalized_report = (report or "all").strip().lower()
    if normalized_report not in REPORT_TYPES:
        raise ReportsError("Invalid report type")

    normalized_owned = (owned_filter or "owned").strip().lower()
    if normalized_owned not in OWNED_FILTERS:
        raise ReportsError("Invalid owned filter")

    normalized_foil = (foil_filter or "all").strip().lower()
    if normalized_foil not in FOIL_FILTERS:
        raise ReportsError("Invalid foil filter")

    normalized_type = (type_filter or "all").strip().lower()
    if normalized_type not in TYPE_FILTERS:
        raise ReportsError("Invalid type filter")

    parsed_colors = parse_collection_color_filters(color_filters)
    use_family = bool(family) and (set_code or "").strip().upper() not in {"", "ALL"}

    settings = settings_service.get_settings(conn)
    strategy = settings["priceStrategy"]
    selected_compare = compare_date or settings["compareDate"]
    set_codes = _resolve_set_codes(conn, set_code=set_code, family=use_family)
    cards, selected_compare = _load_enriched_report_cards(
        conn,
        set_codes=set_codes,
        strategy=strategy,
        compare_date=selected_compare,
    )

    effective_art = "" if use_family else art_style
    art_styles = [] if use_family else build_art_style_options(conn, set_code)

    scope_cards = _apply_filters(
        cards,
        set_code=set_code,
        family=use_family,
        art_style=effective_art,
        owned_filter="all",
        foil_filter="all",
        type_filter="all",
        color_filters=[],
    )
    filtered = _apply_filters(
        scope_cards,
        set_code=set_code,
        family=use_family,
        art_style=effective_art,
        owned_filter=normalized_owned,
        foil_filter=normalized_foil,
        type_filter=normalized_type,
        color_filters=parsed_colors,
        storage_filters=storage_filters or [],
    )
    filtered = _apply_all_view_extra_filters(
        filtered,
        rarity_filter=rarity_filter,
        cmc_min=cmc_min,
        cmc_max=cmc_max,
        price_min=price_min,
        price_max=price_max,
        power_min=power_min,
        toughness_min=toughness_min,
        search=search,
    )
    scoped = _cards_for_report(filtered, normalized_report)

    result: dict = {
        "report": normalized_report,
        "setCode": set_code,
        "family": use_family,
        "artStyle": effective_art,
        "ownedFilter": normalized_owned,
        "foilFilter": normalized_foil,
        "typeFilter": normalized_type,
        "colorFilters": parsed_colors,
        "compareDate": selected_compare,
        "pageSize": page_size,
        "artStyles": art_styles,
        "priceStrategy": strategy,
    }

    if normalized_report == "all":
        normalized_sort = sort if sort in {"number", "value"} else "number"
        ascending = (sort_dir or "").strip().lower() == "asc"
        ranked = sorted(
            scoped,
            key=_all_view_sort_key(normalized_sort, ascending),
        )
        total = len(ranked)
        if page is None:
            limited = ranked
            result["page"] = 1
            result["totalPages"] = 1
            result["hasMore"] = False
        else:
            safe_page_size = max(1, min(int(page_size), 500))
            safe_page = max(1, int(page))
            start = (safe_page - 1) * safe_page_size
            limited = ranked[start : start + safe_page_size]
            total_pages = max(1, (total + safe_page_size - 1) // safe_page_size) if total else 1
            result["page"] = safe_page
            result["totalPages"] = total_pages
            result["hasMore"] = safe_page < total_pages
        result["totalMatches"] = total
        result["cards"] = limited
        result["scopeStats"] = compute_collection_scope_stats(scope_cards)
        return result

    ranked = _rank_cards(scoped, normalized_report)
    limited = _apply_page_size_limit(
        ranked,
        page_size,
        include_unpriced_owned=normalized_owned == "owned",
    )
    result["totalMatches"] = len(ranked)
    result["cards"] = limited
    return result


def compute_collection_scope_stats(cards: list[dict]) -> dict:
    """Mirror frontend `computeCollectionScopeStats` (owned/missing counts + value totals)."""
    owned_count = 0
    owned_value = 0.0
    missing_value = 0.0
    for card in cards:
        value = card.get("currentValue") or 0
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        if card.get("owned"):
            owned_count += 1
            owned_value += value
        else:
            missing_value += value

    total_count = len(cards)
    missing_count = total_count - owned_count
    completion_pct = (owned_count / total_count * 100) if total_count else 0
    return {
        "totalCount": total_count,
        "ownedCount": owned_count,
        "missingCount": missing_count,
        "ownedValue": owned_value,
        "missingValue": missing_value,
        "totalValue": owned_value + missing_value,
        "completionPct": completion_pct,
    }


def _apply_all_view_extra_filters(
    cards: list[dict],
    *,
    rarity_filter: str = "all",
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    power_min: float | None = None,
    toughness_min: float | None = None,
    search: str = "",
) -> list[dict]:
    result = [
        card for card in cards
        if card_matches_collection_rarity_filter(card, rarity_filter)
    ]
    result = [
        card for card in result
        if card_matches_collection_cmc_filter(card, cmc_min=cmc_min, cmc_max=cmc_max)
    ]
    result = [
        card for card in result
        if card_matches_collection_price_filter(card, price_min=price_min, price_max=price_max)
    ]
    result = [
        card for card in result
        if card_matches_collection_stat_filter(card, power_min=power_min, toughness_min=toughness_min)
    ]
    term = (search or "").strip().lower()
    if term:
        result = [card for card in result if _card_matches_all_view_search(card, term)]
    return result


def _card_matches_all_view_search(card: dict, term: str) -> bool:
    """Matches frontend `cardMatchesSearchQuery`: collector number, name, or oracle text."""
    number = str(card.get("collectorNumber") or "").lower()
    padded = number.zfill(3)
    name = str(card.get("name") or "").lower()
    oracle_text = str(card.get("oracleText") or "").lower()
    return (
        term in number
        or term in padded
        or term in name
        or term in oracle_text
        or term in f"#{number}"
        or term in f"#{padded}"
    )


def _compare_collector_numbers(left: str, right: str) -> int:
    left_key = collector_sort_key(left)
    right_key = collector_sort_key(right)
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0


def _all_view_tie_break(left: dict, right: dict) -> int:
    """Mirrors frontend `compareCollectionCardTieBreak`: set, then number, then finish."""
    if left["setCode"] != right["setCode"]:
        return -1 if left["setCode"] < right["setCode"] else 1
    number_order = _compare_collector_numbers(left["collectorNumber"], right["collectorNumber"])
    if number_order != 0:
        return number_order
    return int(left["finish"]) - int(right["finish"])


def _all_view_sort_key(sort: str, ascending: bool):
    """Key function mirroring `_all_view_card_comparator` (faster than cmp_to_key)."""

    if sort == "value":
        def key(card: dict):
            value = card.get("currentValue")
            num = value if value is not None else float("-inf")
            primary = num if ascending else -num
            number_key = collector_sort_key(card["collectorNumber"])
            return (primary, card["setCode"], number_key, int(card["finish"]))

        return key

    def key(card: dict):
        number, suffix = collector_sort_key(card["collectorNumber"])
        # Finish stays ascending even when collector number is descending.
        if ascending:
            return (number, suffix, int(card["finish"]))
        return (-number, _reverse_text_sort_key(suffix), int(card["finish"]))

    return key


def _reverse_text_sort_key(text: str) -> tuple:
    """Invert lexicographic order for a short suffix string."""
    return tuple(-ord(char) for char in text)


def _all_view_card_comparator(sort: str, ascending: bool):
    """Mirrors frontend `sortCollectionCards` for the two sorts the All view exposes."""

    def compare(left: dict, right: dict) -> int:
        if sort == "value":
            left_value = left.get("currentValue")
            right_value = right.get("currentValue")
            left_num = left_value if left_value is not None else float("-inf")
            right_num = right_value if right_value is not None else float("-inf")
            diff = (left_num - right_num) if ascending else (right_num - left_num)
            if diff != 0:
                return -1 if diff < 0 else 1
            return _all_view_tie_break(left, right)

        primary = _compare_collector_numbers(left["collectorNumber"], right["collectorNumber"])
        if primary != 0:
            return primary if ascending else -primary
        return int(left["finish"]) - int(right["finish"])

    return compare


def _resolve_set_codes(
    conn: sqlite3.Connection,
    *,
    set_code: str = "All",
    family: bool = False,
    search_term: str | None = None,
) -> list[str]:
    from util.set_families import resolve_set_codes_for_scope

    normalized_set = (set_code or "All").strip()
    if normalized_set.upper() != "ALL":
        if family:
            return resolve_set_codes_for_scope(
                conn,
                set_code=normalized_set,
                family=True,
            )
        return [normalized_set.upper()]

    term = (search_term or "").strip()
    if term:
        return _sets_matching_search(conn, term)

    rows = conn.execute(
        "SELECT DISTINCT set_code FROM cards ORDER BY set_code"
    ).fetchall()
    return [row[0] for row in rows]


def _sets_matching_search(conn: sqlite3.Connection, term: str) -> list[str]:
    pattern = f"%{term.strip()}%"
    rows = conn.execute(
        f"""
        SELECT DISTINCT set_code
        FROM cards
        WHERE name LIKE ? COLLATE NOCASE
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        ORDER BY set_code
        """,
        (pattern,),
    ).fetchall()
    return [row[0] for row in rows]


def _resolve_compare_date(
    conn: sqlite3.Connection,
    compare_date: str | None,
) -> tuple[str | None, object]:
    """Return (selected_compare, snapshot_cache_or_None).

    When compare_date is omitted, resolve the default from the memoized snapshot cache.
    """
    if compare_date:
        return compare_date, None
    snapshot_cache = load_price_snapshot_cache(conn)
    return default_compare_date(snapshot_cache.dates), snapshot_cache


def _strategy_cache_key(set_code: str, compare_date: str | None, strategy: str) -> str:
    return memory_cache.make_key(
        "reports.enriched.set.strategy",
        {
            "setCode": set_code,
            "compareDate": compare_date or "",
            "strategy": strategy,
            "roles": "v1",
        },
        get_cache_epoch(),
    )


def _load_enriched_report_cards(
    conn: sqlite3.Connection,
    *,
    set_codes: list[str],
    strategy: str,
    compare_date: str | None,
) -> tuple[list[dict], str | None]:
    """Load enriched cards with the active price strategy applied.

    Neutral enrichment is cached per set; strategy projection is cached separately so
    within-set search/filter changes do not re-copy thousands of card dicts.
    """
    selected_compare, snapshot_cache = _resolve_compare_date(conn, compare_date)
    if not set_codes:
        return [], selected_compare

    normalized_codes = [code.strip().upper() for code in set_codes]
    cached_parts = [
        memory_cache.get(_strategy_cache_key(code, selected_compare, strategy))
        for code in normalized_codes
    ]
    if all(part is not None for part in cached_parts):
        merged: list[dict] = []
        for part in cached_parts:
            merged.extend(part)
        return merged, selected_compare

    locations_map = _load_card_locations(conn)
    owned_keys = _load_owned_print_keys(conn)
    roles_by_name = load_card_name_roles_map(conn)
    if snapshot_cache is None:
        snapshot_cache = load_price_snapshot_cache(conn)
    snapshot_prices = snapshot_cache.snapshots.get(selected_compare or "", {})

    merged = []
    for code, cached in zip(normalized_codes, cached_parts, strict=True):
        if cached is not None:
            merged.extend(cached)
            continue
        neutral = _load_enriched_set(
            conn,
            code,
            selected_compare,
            locations_map=locations_map,
            owned_keys=owned_keys,
            snapshot_prices=snapshot_prices,
            roles_by_name=roles_by_name,
        )
        applied = _apply_strategy_to_cards(neutral, strategy)
        memory_cache.set(
            _strategy_cache_key(code, selected_compare, strategy),
            applied,
            _ENRICHED_REPORTS_TTL,
        )
        merged.extend(applied)
    return merged, selected_compare


def _load_enriched_sets(
    conn: sqlite3.Connection,
    set_codes: list[str],
    compare_date: str | None,
) -> tuple[list[dict], str | None]:
    selected_compare, snapshot_cache = _resolve_compare_date(conn, compare_date)
    if not set_codes:
        return [], selected_compare

    locations_map = _load_card_locations(conn)
    owned_keys = _load_owned_print_keys(conn)
    roles_by_name = load_card_name_roles_map(conn)
    if snapshot_cache is None:
        snapshot_cache = load_price_snapshot_cache(conn)
    snapshot_prices = snapshot_cache.snapshots.get(selected_compare or "", {})

    merged: list[dict] = []
    for code in set_codes:
        merged.extend(
            _load_enriched_set(
                conn,
                code,
                selected_compare,
                locations_map=locations_map,
                owned_keys=owned_keys,
                snapshot_prices=snapshot_prices,
                roles_by_name=roles_by_name,
            )
        )
    return merged, selected_compare


def _load_enriched_set(
    conn: sqlite3.Connection,
    set_code: str,
    selected_compare: str | None,
    *,
    locations_map: dict[str, list[dict]],
    owned_keys: frozenset[str],
    snapshot_prices: dict[str, float],
    roles_by_name: dict[str, list[str]] | None = None,
) -> list[dict]:
    normalized = set_code.strip().upper()
    epoch = get_cache_epoch()
    cache_key = memory_cache.make_key(
        "reports.enriched.set",
        {"setCode": normalized, "compareDate": selected_compare or "", "roles": "v1"},
        epoch,
    )
    cached = memory_cache.get(cache_key)
    if cached is not None:
        return cached

    name_roles = roles_by_name if roles_by_name is not None else load_card_name_roles_map(conn)
    cards_df = load_ranked_cards_data_for_set(normalized)
    base_cards = serialize_ranked_cards(cards_df)
    enriched = [
        _enrich_card(
            card,
            locations_map=locations_map,
            owned_keys=owned_keys,
            snapshot_prices=snapshot_prices,
            compare_date=selected_compare,
            roles_by_name=name_roles,
        )
        for card in base_cards
    ]
    memory_cache.set(cache_key, enriched, _ENRICHED_REPORTS_TTL)
    return enriched


def _apply_strategy_to_cards(cards: list[dict], strategy: str) -> list[dict]:
    return [_apply_strategy(card, strategy) for card in cards]


def _apply_strategy(card: dict, strategy: str) -> dict:
    result = dict(card)
    finish = int(card["finish"])
    values = card.get("valuesByStrategy") or {}
    current_value = value_from_strategy_map(
        values,
        strategy,
        finish=finish,
        market_value=card.get("marketValue"),
        market_value_foil=card.get("marketValueFoil"),
        market_value_etched=card.get("marketValueEtched"),
    )
    purchase_value = card.get("purchaseValue")
    profit_loss = None
    if purchase_value is not None and purchase_value != 0 and current_value is not None:
        profit_loss = current_value - purchase_value
    previous_value = card.get("previousValue")
    price_change = None
    if current_value is not None and previous_value is not None:
        price_change = current_value - previous_value
    result["currentValue"] = current_value
    result["profitLoss"] = profit_loss
    result["priceChange"] = price_change
    return result


def _load_owned_print_keys(conn: sqlite3.Connection) -> frozenset[str]:
    keys: set[str] = set()
    for set_code, collector_number, finish in conn.execute(
        "SELECT set_code, collector_number, finish FROM purchases"
    ):
        keys.add(card_price_key(set_code, collector_number, finish))

    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
    ).fetchone()
    if table:
        for set_code, collector_number, finish in conn.execute(
            "SELECT DISTINCT set_code, collector_number, finish FROM card_instances"
        ):
            keys.add(card_price_key(set_code, collector_number, finish))
    return frozenset(keys)


def _enrich_card(
    card: dict,
    *,
    locations_map: dict[str, list[dict]],
    owned_keys: frozenset[str],
    snapshot_prices: dict[str, float],
    compare_date: str | None,
    roles_by_name: dict[str, list[str]] | None = None,
) -> dict:
    finish = int(card["finish"])
    values_by_strategy = values_by_strategy_for_finish(card, finish)
    purchase_value = card.get("purchase_value")

    key = card_price_key(card["set_code"], card["collector_number"], finish)
    locations = locations_map.get(key, [])
    previous_value = snapshot_prices.get(key)
    name = card["name"]
    roles = []
    if roles_by_name:
        roles = roles_by_name.get(name) or roles_by_name.get(str(name).casefold()) or []

    return {
        "setCode": card["set_code"],
        "collectorNumber": str(card["collector_number"]),
        "name": name,
        "artStyle": card.get("art_style") or "",
        "finish": finish,
        "foil": finish,
        "purchaseValue": purchase_value,
        "valuesByStrategy": values_by_strategy,
        "previousValue": previous_value,
        "previousDate": compare_date,
        "imageUri": card.get("image_uri") or "",
        "imageUriBack": card.get("image_uri_back") or "",
        "cardmarketUrl": cardmarket_url_for_finish(card, finish) or "",
        "marketValue": card.get("market_value"),
        "marketValueFoil": card.get("market_value_foil"),
        "marketValueEtched": card.get("market_value_etched"),
        "hasNonfoil": bool(card.get("has_nonfoil")),
        "hasFoil": bool(card.get("has_foil")),
        "hasEtched": bool(card.get("has_etched")),
        **card_metadata_api(card),
        "roles": list(roles),
        "owned": purchase_value is not None or key in owned_keys or bool(locations),
        "locations": locations,
    }


def _load_card_locations(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
    ).fetchone()
    if not table:
        return {}

    rows = conn.execute(
        """
        SELECT
            ci.set_code,
            ci.collector_number,
            ci.finish,
            ci.location_slug,
            sl.label,
            sl.location_type,
            COUNT(*) AS copy_count
        FROM card_instances ci
        JOIN storage_locations sl ON sl.location_slug = ci.location_slug
        GROUP BY ci.set_code, ci.collector_number, ci.finish, ci.location_slug
        ORDER BY sl.sort_order, sl.label
        """
    ).fetchall()

    locations: dict[str, list[dict]] = {}
    for set_code, collector_number, finish, slug, label, location_type, copy_count in rows:
        key = card_price_key(set_code, collector_number, finish)
        locations.setdefault(key, []).append({
            "slug": slug,
            "label": label,
            "locationType": location_type,
            "count": int(copy_count),
        })
    return locations


def _has_positive_price(card: dict) -> bool:
    value = card.get("currentValue")
    return value is not None and float(value) > 0


def _cards_for_report(cards: list[dict], report: str) -> list[dict]:
    if report == "all":
        return cards
    return [card for card in cards if _has_positive_price(card)]


def _apply_filters(
    cards: list[dict],
    *,
    set_code: str,
    art_style: str,
    owned_filter: str,
    foil_filter: str,
    type_filter: str = "all",
    color_filters: list[str] | None = None,
    storage_filters: list[str] | None = None,
    family: bool = False,
) -> list[dict]:
    result = cards
    if set_code and set_code != "All" and not family:
        normalized_set = set_code.upper()
        result = [card for card in result if card["setCode"] == normalized_set]
    if art_style:
        result = [card for card in result if card["artStyle"] == art_style]
    if foil_filter == "nonfoil":
        result = [card for card in result if card["finish"] == 0]
    elif foil_filter == "foil":
        result = [card for card in result if card["finish"] == 1]
    elif foil_filter == "etched":
        result = [card for card in result if card["finish"] == 2]
    if owned_filter == "owned":
        result = [card for card in result if card["owned"]]
    elif owned_filter == "unowned":
        result = [card for card in result if not card["owned"]]
    if type_filter and type_filter != "all":
        result = [
            card for card in result
            if card_matches_collection_type_filter(card, type_filter)
        ]
    if color_filters:
        result = [
            card for card in result
            if card_matches_collection_color_filter(card, color_filters)
        ]
    if storage_filters:
        result = [
            card for card in result
            if card_matches_collection_storage_filter(card, storage_filters)
        ]
    return result


def _rank_cards(cards: list[dict], report: str) -> list[dict]:
    if report == "all":
        return sorted(
            cards,
            key=lambda card: (
                card["setCode"],
                collector_sort_key(card["collectorNumber"]),
                card["finish"],
            ),
        )
    if report == "risers":
        risers = [
            card for card in cards
            if card.get("priceChange") is not None and card["priceChange"] > 0
        ]
        return sorted(
            risers,
            key=lambda card: (-card["priceChange"], -(card["currentValue"] or 0)),
        )
    fallers = [
        card for card in cards
        if card.get("priceChange") is not None and card["priceChange"] < 0
    ]
    return sorted(
        fallers,
        key=lambda card: (card["priceChange"], -(card["currentValue"] or 0)),
    )


def _apply_page_size_limit(
    cards: list[dict],
    page_size: int,
    *,
    include_unpriced_owned: bool,
) -> list[dict]:
    limit = max(1, min(int(page_size), 500))
    if limit >= len(cards):
        return cards

    if not include_unpriced_owned:
        return cards[:limit]

    unpriced_owned = [
        card for card in cards
        if card["owned"] and card.get("currentValue") is None
    ]
    priced_or_unowned = [
        card for card in cards
        if not (card["owned"] and card.get("currentValue") is None)
    ]
    limited = priced_or_unowned[:limit]
    seen = {_card_rank_key(card) for card in limited}
    for card in unpriced_owned:
        key = _card_rank_key(card)
        if key not in seen:
            limited.append(card)
            seen.add(key)
    return limited


def _card_rank_key(card: dict) -> str:
    return f"{card['setCode']}|{card['collectorNumber']}|{card['finish']}"
