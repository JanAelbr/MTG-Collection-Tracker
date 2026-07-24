import sqlite3

from report.card_detail_data import collector_sort_key

from api.services.reports_service import (
    OWNED_FILTERS,
    FOIL_FILTERS,
    ReportsError,
    _apply_filters,
    _load_enriched_report_cards,
    _resolve_set_codes,
)
from api.services import settings_service
from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql
from util.card_metadata import (
    card_matches_collection_cmc_filter,
    card_matches_collection_price_filter,
    card_matches_collection_rarity_filter,
    card_matches_collection_stat_filter,
)
from util.set_catalog import load_sets_catalog

SEARCH_PAGE_SIZE = 25
MAX_SEARCH_PAGE_SIZE = 100
SEARCH_SORT_FIELDS = frozenset({"newest", "name", "value", "cmc"})
SEARCH_SORT_DIR_DEFAULTS = {
    "newest": "desc",
    "name": "asc",
    "value": "desc",
    "cmc": "asc",
}

# Keep in sync with frontend CARD_ROLE_LABELS (search UI skips "land").
SEARCHABLE_CARD_ROLES = frozenset({
    "ramp",
    "draw",
    "removal",
    "interaction",
    "protection",
    "tutor",
    "fast_mana",
    "game_changer",
    "combo_piece",
    "synergy",
    "recursion",
    "reanimate",
    "equipment",
    "aura",
    "graveyard_hate",
    "extra_turn",
    "mass_land_destruction",
    "board_wipe",
    "bounce",
    "counterspell",
    "land_destruction",
    "mill",
    "discard",
    "sac_outlet",
    "fog",
})


def _normalize_owned_filter(owned_filter: str) -> str:
    normalized = (owned_filter or "all").strip().lower()
    if normalized not in OWNED_FILTERS:
        raise ReportsError("Invalid owned filter")
    return normalized


def _normalize_foil_filter(foil_filter: str) -> str:
    normalized = (foil_filter or "all").strip().lower()
    if normalized not in FOIL_FILTERS:
        raise ReportsError("Invalid foil filter")
    return normalized


def _load_set_release_dates(conn: sqlite3.Connection) -> dict[str, str]:
    catalog = load_sets_catalog(conn)
    return {
        set_code: meta.get("released_at") or ""
        for set_code, meta in catalog.items()
    }


def _sets_for_exact_name(conn: sqlite3.Connection, name: str) -> list[str]:
    """Sets that print this exact card name — used to avoid enriching the whole catalog."""
    rows = conn.execute(
        f"""
        SELECT DISTINCT set_code
        FROM cards
        WHERE name = ?
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        ORDER BY set_code
        """,
        (name.strip(),),
    ).fetchall()
    return [row[0] for row in rows]


def _newest_first_key(card: dict, release_dates: dict[str, str]) -> tuple:
    set_code = str(card.get("setCode") or "").upper()
    released_at = release_dates.get(set_code) or ""
    return (
        released_at,
        collector_sort_key(card.get("collectorNumber") or ""),
        card.get("artStyle") or "",
    )


def normalize_search_sort(sort: str | None) -> str:
    text = str(sort or "").strip().lower()
    return text if text in SEARCH_SORT_FIELDS else "newest"


def normalize_search_sort_dir(sort: str | None, sort_dir: str | None) -> str:
    normalized_sort = normalize_search_sort(sort)
    text = str(sort_dir or "").strip().lower()
    if text in {"asc", "desc"}:
        return text
    return SEARCH_SORT_DIR_DEFAULTS.get(normalized_sort, "asc")


def _numeric_nulls_last_key(value, *, ascending: bool) -> tuple:
    if value is None:
        return (1, 0.0)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return (1, 0.0)
    return (0, number if ascending else -number)


def _rank_search_pool(
    pool: list[dict],
    *,
    sort: str,
    sort_dir: str,
    release_dates: dict[str, str],
) -> list[dict]:
    normalized_sort = normalize_search_sort(sort)
    normalized_dir = normalize_search_sort_dir(normalized_sort, sort_dir)
    ascending = normalized_dir == "asc"

    def tie_break(card: dict) -> tuple:
        return (
            (card.get("name") or "").lower(),
            _newest_first_key(card, release_dates),
        )

    if normalized_sort == "name":
        return sorted(
            pool,
            key=lambda card: ((card.get("name") or "").lower(), _newest_first_key(card, release_dates)),
            reverse=not ascending,
        )
    if normalized_sort == "value":
        return sorted(
            pool,
            key=lambda card: (
                _numeric_nulls_last_key(card.get("currentValue"), ascending=ascending),
                *tie_break(card),
            ),
        )
    if normalized_sort == "cmc":
        return sorted(
            pool,
            key=lambda card: (
                _numeric_nulls_last_key(card.get("cmc"), ascending=ascending),
                *tie_break(card),
            ),
        )
    return sorted(
        pool,
        key=lambda card: _newest_first_key(card, release_dates),
        reverse=not ascending,
    )


def _parse_optional_float(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _parse_color_filters(colors: str | list[str] | None) -> list[str]:
    if not colors:
        return []
    if isinstance(colors, list):
        items = colors
    else:
        items = str(colors).split(",")
    allowed = {"W", "U", "B", "R", "G", "C"}
    return [
        item.strip().upper()
        for item in items
        if item.strip().upper() in allowed
    ]


def _card_matches_name(card: dict, term: str) -> bool:
    return term in (card.get("name") or "").lower()


def _card_matches_oracle_text(card: dict, term: str) -> bool:
    return term in (card.get("oracleText") or "").lower()


def _card_matches_creature_type(card: dict, term: str) -> bool:
    return term in (card.get("typeLine") or "").lower()


def _parse_storage_filters(storage: str | list[str] | None) -> list[str]:
    if not storage:
        return []
    if isinstance(storage, list):
        items = storage
    else:
        items = str(storage).split(",")
    return [item.strip() for item in items if item.strip()]


def _parse_role_filters(roles: str | list[str] | None) -> list[str]:
    if not roles:
        return []
    if isinstance(roles, list):
        items = roles
    else:
        items = str(roles).split(",")
    parsed: list[str] = []
    seen: set[str] = set()
    for item in items:
        role = str(item).strip().lower().replace(" ", "_").replace("-", "_")
        if role not in SEARCHABLE_CARD_ROLES or role in seen:
            continue
        seen.add(role)
        parsed.append(role)
    return parsed


def _card_matches_role_filters(card: dict, role_filters: list[str]) -> bool:
    if not role_filters:
        return True
    card_roles = {str(role) for role in (card.get("roles") or []) if role}
    return any(role in card_roles for role in role_filters)


def _filter_enriched_cards(
    cards: list[dict],
    *,
    set_code: str,
    owned_filter: str,
    foil_filter: str,
    name_search: str = "",
    exact_name: str = "",
    text_search: str = "",
    creature_type_search: str = "",
    type_filter: str = "all",
    color_filters: list[str] | None = None,
    rarity_filter: str = "all",
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    power_min: float | None = None,
    toughness_min: float | None = None,
    storage_filters: list[str] | None = None,
    role_filters: list[str] | None = None,
) -> list[dict]:
    filtered = _apply_filters(
        cards,
        set_code=set_code,
        art_style="",
        owned_filter=owned_filter,
        foil_filter=foil_filter,
        type_filter=type_filter,
        color_filters=color_filters or [],
        storage_filters=storage_filters or [],
    )
    filtered = [
        card for card in filtered
        if card_matches_collection_rarity_filter(card, rarity_filter)
    ]
    filtered = [
        card for card in filtered
        if card_matches_collection_cmc_filter(card, cmc_min=cmc_min, cmc_max=cmc_max)
    ]
    filtered = [
        card for card in filtered
        if card_matches_collection_price_filter(card, price_min=price_min, price_max=price_max)
    ]
    filtered = [
        card for card in filtered
        if card_matches_collection_stat_filter(
            card,
            power_min=power_min,
            toughness_min=toughness_min,
        )
    ]
    exact = exact_name.strip()
    if exact:
        filtered = [card for card in filtered if (card.get("name") or "") == exact]
    name_term = name_search.strip()
    if name_term:
        lowered = name_term.lower()
        filtered = [card for card in filtered if _card_matches_name(card, lowered)]
    text_term = text_search.strip()
    if text_term:
        lowered = text_term.lower()
        filtered = [card for card in filtered if _card_matches_oracle_text(card, lowered)]
    creature_type_term = creature_type_search.strip()
    if creature_type_term:
        lowered = creature_type_term.lower()
        filtered = [card for card in filtered if _card_matches_creature_type(card, lowered)]
    selected_roles = role_filters or []
    if selected_roles:
        filtered = [
            card for card in filtered
            if _card_matches_role_filters(card, selected_roles)
        ]
    return filtered


def _filtered_pool(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    owned_filter: str,
    foil_filter: str,
    name_search: str = "",
    exact_name: str = "",
    text_search: str = "",
    creature_type_search: str = "",
    type_filter: str = "all",
    color_filters: list[str] | None = None,
    rarity_filter: str = "all",
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    power_min: float | None = None,
    toughness_min: float | None = None,
    storage_filters: list[str] | None = None,
    role_filters: list[str] | None = None,
    set_codes: list[str] | None = None,
) -> list[dict]:
    settings = settings_service.get_settings(conn)
    name_term = name_search.strip()
    resolved_codes = (
        list(set_codes)
        if set_codes is not None
        else _resolve_set_codes(conn, set_code=set_code, search_term=name_term or None)
    )
    cards, _compare_date = _load_enriched_report_cards(
        conn,
        set_codes=resolved_codes,
        strategy=settings["priceStrategy"],
        compare_date=settings["compareDate"],
    )
    return _filter_enriched_cards(
        cards,
        set_code=set_code,
        owned_filter=owned_filter,
        foil_filter=foil_filter,
        name_search=name_search,
        exact_name=exact_name,
        text_search=text_search,
        creature_type_search=creature_type_search,
        type_filter=type_filter,
        color_filters=color_filters,
        rarity_filter=rarity_filter,
        cmc_min=cmc_min,
        cmc_max=cmc_max,
        price_min=price_min,
        price_max=price_max,
        power_min=power_min,
        toughness_min=toughness_min,
        storage_filters=storage_filters,
        role_filters=role_filters,
    )


def _print_key(card: dict) -> tuple:
    return (
        card["setCode"],
        str(card["collectorNumber"]),
        card.get("artStyle") or "",
    )


def _load_print_finish_flags(conn: sqlite3.Connection, name: str) -> dict[tuple, dict]:
    rows = conn.execute(
        """
        SELECT set_code, collector_number, art_style, has_nonfoil, has_foil, has_etched
        FROM cards
        WHERE name = ?
        """,
        (name.strip(),),
    ).fetchall()
    flags: dict[tuple, dict] = {}
    for set_code, collector_number, art_style, has_nonfoil, has_foil, has_etched in rows:
        key = (set_code, str(collector_number), art_style or "")
        flags[key] = {
            "hasNonfoil": bool(has_nonfoil),
            "hasFoil": bool(has_foil),
            "hasEtched": bool(has_etched),
        }
    return flags


def _append_catalog_finish(entry: dict, finish: int) -> None:
    if finish not in entry["finishes"]:
        entry["finishes"].append(finish)


def _apply_print_flags(entry: dict, flags: dict | None) -> None:
    if not flags:
        return
    if flags.get("hasNonfoil"):
        _append_catalog_finish(entry, 0)
    if flags.get("hasFoil"):
        _append_catalog_finish(entry, 1)
    if flags.get("hasEtched"):
        _append_catalog_finish(entry, 2)


def _finish_catalog_for_name(
    pool: list[dict],
    name: str,
    *,
    print_flags: dict[tuple, dict] | None = None,
) -> dict[tuple, dict]:
    catalog: dict[tuple, dict] = {}
    for card in pool:
        if card.get("name") != name:
            continue
        key = _print_key(card)
        entry = catalog.setdefault(key, {"finishes": [], "finishValues": {}, "finishValuesByStrategy": {}})
        finish = int(card["finish"])
        current = card.get("currentValue")
        if current is not None and float(current) > 0:
            _append_catalog_finish(entry, finish)
            entry["finishValues"][finish] = current
            if card.get("valuesByStrategy"):
                entry["finishValuesByStrategy"][finish] = dict(card["valuesByStrategy"])
        _apply_print_flags(entry, {
            "hasNonfoil": card.get("hasNonfoil"),
            "hasFoil": card.get("hasFoil"),
            "hasEtched": card.get("hasEtched"),
        })

    if print_flags:
        for key, flags in print_flags.items():
            entry = catalog.setdefault(key, {"finishes": [], "finishValues": {}, "finishValuesByStrategy": {}})
            _apply_print_flags(entry, flags)

    for entry in catalog.values():
        entry["finishes"] = sorted(set(entry["finishes"]))
    return catalog


def _merge_variant_finishes(
    variants: list[dict],
    finish_catalog: dict[tuple, dict],
    *,
    print_flags: dict[tuple, dict] | None = None,
) -> None:
    for variant in variants:
        key = _print_key(variant)
        catalog_entry = finish_catalog.get(key)
        flags = print_flags.get(key) if print_flags else None
        if flags:
            variant["hasNonfoil"] = flags.get("hasNonfoil", False)
            variant["hasFoil"] = flags.get("hasFoil", False)
            variant["hasEtched"] = flags.get("hasEtched", False)
        if not catalog_entry:
            continue
        variant["availableFinishes"] = list(catalog_entry["finishes"])
        variant["finishValues"] = {
            **catalog_entry["finishValues"],
            **(variant.get("finishValues") or {}),
        }
        variant["finishValuesByStrategy"] = {
            **catalog_entry.get("finishValuesByStrategy", {}),
            **(variant.get("finishValuesByStrategy") or {}),
        }


def _catalog_variants(
    pool: list[dict],
    name: str,
    *,
    release_dates: dict[str, str],
) -> list[dict]:
    by_print: dict[tuple, dict] = {}
    for card in pool:
        if card.get("name") != name:
            continue
        key = (
            card["setCode"],
            str(card["collectorNumber"]),
            card.get("artStyle") or "",
        )
        if key not in by_print:
            current = card.get("currentValue")
            finish = int(card["finish"])
            image_uri = (card.get("imageUri") or "").strip()
            has_price = current is not None and float(current) > 0
            if not has_price and not image_uri:
                continue
            by_print[key] = {
                **card,
                "availableFinishes": [finish] if has_price else [],
                "finishValues": {finish: current} if has_price else {},
            }
            continue
        finishes = by_print[key]["availableFinishes"]
        finish = int(card["finish"])
        current = card.get("currentValue")
        if finish not in finishes and current is not None and float(current) > 0:
            finishes.append(finish)
        values = by_print[key].setdefault("finishValues", {})
        if current is not None and float(current) > 0:
            values[finish] = current
        if not by_print[key].get("imageUri") and card.get("imageUri"):
            by_print[key]["imageUri"] = card["imageUri"]
    for item in by_print.values():
        item["availableFinishes"] = [
            finish for finish in item["availableFinishes"]
            if finish in item.get("finishValues", {})
        ]
    return sorted(
        by_print.values(),
        key=lambda item: _newest_first_key(item, release_dates),
        reverse=True,
    )


def _pool_variants_by_print(pool: list[dict], name: str) -> dict[tuple, dict]:
    by_print: dict[tuple, dict] = {}
    for card in pool:
        if card.get("name") != name:
            continue
        key = _print_key(card)
        if key not in by_print:
            by_print[key] = card
            continue
        existing = by_print[key]
        if not existing.get("imageUri") and card.get("imageUri"):
            by_print[key] = {**existing, "imageUri": card["imageUri"]}
    return by_print


def _variant_from_catalog_row(row: sqlite3.Row, pool_card: dict | None) -> dict:
    variant = dict(pool_card) if pool_card else {}
    variant.update({
        "setCode": row["set_code"],
        "collectorNumber": str(row["collector_number"]),
        "name": row["name"],
        "artStyle": row["art_style"] or "",
        "imageUri": row["image_uri"] or variant.get("imageUri") or "",
        "imageUriBack": row["image_uri_back"] or variant.get("imageUriBack") or "",
        "typeLine": row["type_line"] or variant.get("typeLine") or "",
        "hasNonfoil": bool(row["has_nonfoil"]),
        "hasFoil": bool(row["has_foil"]),
        "hasEtched": bool(row["has_etched"]),
        "marketValue": row["market_value"],
        "marketValueFoil": row["market_value_foil"],
        "marketValueEtched": row["market_value_etched"],
    })
    if "finish" not in variant:
        variant["finish"] = 0
        variant["foil"] = 0
    return variant


def _catalog_variants_for_name(
    conn: sqlite3.Connection,
    name: str,
    pool: list[dict],
    *,
    release_dates: dict[str, str],
) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT
            set_code,
            collector_number,
            name,
            art_style,
            image_uri,
            image_uri_back,
            market_value,
            market_value_foil,
            market_value_etched,
            has_nonfoil,
            has_foil,
            has_etched,
            type_line
        FROM cards
        WHERE name = ?
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        ORDER BY set_code, CAST(collector_number AS INTEGER)
        """,
        (name.strip(),),
    ).fetchall()
    if not rows:
        return _catalog_variants(pool, name, release_dates=release_dates)

    pool_by_print = _pool_variants_by_print(pool, name)
    variants = [
        _variant_from_catalog_row(row, pool_by_print.get((
            row["set_code"],
            str(row["collector_number"]),
            row["art_style"] or "",
        )))
        for row in rows
    ]
    return sorted(
        variants,
        key=lambda item: _newest_first_key(item, release_dates),
        reverse=True,
    )


def _build_variants(
    conn: sqlite3.Connection,
    name: str,
    pool: list[dict],
    *,
    release_dates: dict[str, str],
) -> list[dict]:
    variants = _catalog_variants_for_name(
        conn,
        name,
        pool,
        release_dates=release_dates,
    )
    if variants:
        return variants
    return _catalog_variants(pool, name, release_dates=release_dates)


def _unique_names(pool: list[dict]) -> list[str]:
    return sorted({card["name"] for card in pool if card.get("name")})


def _dedupe_ranked_by_name(cards: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    order: list[str] = []
    for card in cards:
        name = card.get("name")
        if not name or name in seen:
            continue
        seen[name] = card
        order.append(name)
    return [seen[name] for name in order]


def list_name_variants(
    conn: sqlite3.Connection,
    *,
    name: str,
    set_code: str = "All",
    owned_filter: str = "all",
    foil_filter: str = "all",
    type_filter: str = "all",
    color_filters: list[str] | None = None,
    rarity_filter: str = "all",
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    power_min: float | None = None,
    toughness_min: float | None = None,
    storage_filters: list[str] | None = None,
) -> dict:
    normalized_owned = _normalize_owned_filter(owned_filter)
    normalized_foil = _normalize_foil_filter(foil_filter)
    trimmed_name = (name or "").strip()
    if not trimmed_name:
        raise ReportsError("Card name is required")

    filter_kwargs = {
        "type_filter": type_filter,
        "color_filters": color_filters or [],
        "rarity_filter": rarity_filter,
        "cmc_min": cmc_min,
        "cmc_max": cmc_max,
        "price_min": price_min,
        "price_max": price_max,
        "power_min": power_min,
        "toughness_min": toughness_min,
        "storage_filters": storage_filters or [],
    }
    # Selecting one search result must not re-enrich every set in the catalog.
    # Scope enrichment to sets that actually print this exact name.
    name_set_codes = _sets_for_exact_name(conn, trimmed_name)
    if (set_code or "All").strip().upper() != "ALL":
        scoped = set(_resolve_set_codes(conn, set_code=set_code))
        name_set_codes = [code for code in name_set_codes if code in scoped]

    # Variant browsing should always include every printing of the name (with
    # prices), even when the search results list is scoped to owned-only.
    # Ownership flags still come from enrichment; we simply do not drop
    # unowned prints from the pool used for finish/price overlay.
    pool = _filtered_pool(
        conn,
        set_code=set_code,
        owned_filter="all",
        foil_filter=normalized_foil,
        exact_name=trimmed_name,
        set_codes=name_set_codes,
        **filter_kwargs,
    )
    release_dates = _load_set_release_dates(conn)
    variants = _build_variants(
        conn,
        trimmed_name,
        pool,
        release_dates=release_dates,
    )
    if not variants:
        raise ReportsError("No variants found for this card name", status_code=404)

    if normalized_foil == "all":
        full_pool = pool
    else:
        full_pool = _filtered_pool(
            conn,
            set_code=set_code,
            owned_filter="all",
            foil_filter="all",
            exact_name=trimmed_name,
            set_codes=name_set_codes,
            **filter_kwargs,
        )
    print_flags = _load_print_finish_flags(conn, trimmed_name)
    finish_catalog = _finish_catalog_for_name(
        full_pool,
        trimmed_name,
        print_flags=print_flags,
    )
    _merge_variant_finishes(variants, finish_catalog, print_flags=print_flags)

    return {
        "name": trimmed_name,
        "setCode": set_code,
        "ownedFilter": normalized_owned,
        "foilFilter": normalized_foil,
        "variants": variants,
        "totalVariants": len(variants),
    }


def search_cards(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    text_search: str = "",
    creature_type_search: str = "",
    set_code: str = "All",
    owned_filter: str = "all",
    foil_filter: str = "all",
    type_filter: str = "all",
    color_filters: list[str] | None = None,
    rarity_filter: str = "all",
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    power_min: float | None = None,
    toughness_min: float | None = None,
    storage_filters: list[str] | None = None,
    role_filters: list[str] | None = None,
    sort: str = "newest",
    sort_dir: str = "",
    page: int = 1,
    page_size: int = SEARCH_PAGE_SIZE,
) -> dict:
    normalized_owned = _normalize_owned_filter(owned_filter)
    normalized_foil = _normalize_foil_filter(foil_filter)
    normalized_sort = normalize_search_sort(sort)
    normalized_sort_dir = normalize_search_sort_dir(normalized_sort, sort_dir)
    name_term = search.strip()
    text_term = text_search.strip()
    creature_type_term = creature_type_search.strip()
    selected_roles = list(role_filters or [])
    empty_payload = {
        "search": name_term,
        "textSearch": text_term,
        "creatureTypeSearch": creature_type_term,
        "roleFilters": selected_roles,
        "setCode": set_code,
        "ownedFilter": normalized_owned,
        "foilFilter": normalized_foil,
        "sort": normalized_sort,
        "dir": normalized_sort_dir,
        "page": 1,
        "pageSize": max(1, min(int(page_size), MAX_SEARCH_PAGE_SIZE)),
        "totalMatches": 0,
        "totalPages": 1,
        "cards": [],
    }
    if not name_term and not text_term and not creature_type_term and not selected_roles:
        return empty_payload

    filter_kwargs = {
        "type_filter": type_filter,
        "color_filters": color_filters or [],
        "rarity_filter": rarity_filter,
        "cmc_min": cmc_min,
        "cmc_max": cmc_max,
        "price_min": price_min,
        "price_max": price_max,
        "power_min": power_min,
        "toughness_min": toughness_min,
        "storage_filters": storage_filters or [],
        "role_filters": selected_roles,
    }
    pool = _filtered_pool(
        conn,
        set_code=set_code,
        owned_filter=normalized_owned,
        foil_filter=normalized_foil,
        name_search=name_term,
        text_search=text_term,
        creature_type_search=creature_type_term,
        **filter_kwargs,
    )
    release_dates = _load_set_release_dates(conn)
    ranked = _rank_search_pool(
        pool,
        sort=normalized_sort,
        sort_dir=normalized_sort_dir,
        release_dates=release_dates,
    )
    unique_ranked = _dedupe_ranked_by_name(ranked)
    total = len(unique_ranked)
    safe_page_size = max(1, min(int(page_size), MAX_SEARCH_PAGE_SIZE))
    safe_page = max(1, page)
    start = (safe_page - 1) * safe_page_size
    page_cards = unique_ranked[start : start + safe_page_size]
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size) if total else 1

    return {
        "search": name_term,
        "textSearch": text_term,
        "creatureTypeSearch": creature_type_term,
        "roleFilters": selected_roles,
        "setCode": set_code,
        "ownedFilter": normalized_owned,
        "foilFilter": normalized_foil,
        "sort": normalized_sort,
        "dir": normalized_sort_dir,
        "page": safe_page,
        "pageSize": safe_page_size,
        "totalMatches": total,
        "totalPages": total_pages,
        "cards": page_cards,
    }
