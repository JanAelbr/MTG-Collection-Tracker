import random
import sqlite3

from report.card_detail_data import collector_sort_key

from api.services.reports_service import (
    OWNED_FILTERS,
    FOIL_FILTERS,
    ReportsError,
    _apply_filters,
    _load_enriched_report_cards,
)
from api.services import settings_service
from util.set_catalog import load_sets_catalog

SEARCH_PAGE_SIZE = 25
MAX_SEARCH_PAGE_SIZE = 100


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


def _newest_first_key(card: dict, release_dates: dict[str, str]) -> tuple:
    set_code = str(card.get("setCode") or "").upper()
    released_at = release_dates.get(set_code) or ""
    return (
        released_at,
        collector_sort_key(card.get("collectorNumber") or ""),
        card.get("artStyle") or "",
    )


def _card_matches_term(card: dict, term: str) -> bool:
    haystacks = [
        card.get("name") or "",
        card.get("collectorNumber") or "",
        card.get("artStyle") or "",
        card.get("setCode") or "",
        card.get("typeLine") or "",
        card.get("cardType") or "",
    ]
    card_types = card.get("cardTypes") or []
    if isinstance(card_types, list):
        haystacks.extend(str(item) for item in card_types)
    return any(term in str(value).lower() for value in haystacks if value)


def _filtered_pool(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    owned_filter: str,
    foil_filter: str,
    search: str = "",
) -> list[dict]:
    settings = settings_service.get_settings(conn)
    cards, _compare_date = _load_enriched_report_cards(
        conn,
        strategy=settings["priceStrategy"],
        compare_date=settings["compareDate"],
    )
    filtered = _apply_filters(
        cards,
        set_code=set_code,
        art_style="",
        owned_filter=owned_filter,
        foil_filter=foil_filter,
    )
    term = search.strip().lower()
    if not term:
        return filtered
    return [card for card in filtered if _card_matches_term(card, term)]


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
            by_print[key] = {
                **card,
                "availableFinishes": [finish],
                "finishValues": {finish: current} if current is not None else {},
            }
            continue
        finishes = by_print[key]["availableFinishes"]
        finish = int(card["finish"])
        if finish not in finishes:
            finishes.append(finish)
        values = by_print[key].setdefault("finishValues", {})
        current = card.get("currentValue")
        if current is not None:
            values[int(card["finish"])] = current
    return sorted(
        by_print.values(),
        key=lambda item: _newest_first_key(item, release_dates),
        reverse=True,
    )


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
    search: str = "",
    set_code: str = "All",
    owned_filter: str = "all",
    foil_filter: str = "all",
) -> dict:
    normalized_owned = _normalize_owned_filter(owned_filter)
    normalized_foil = _normalize_foil_filter(foil_filter)
    trimmed_name = (name or "").strip()
    if not trimmed_name:
        raise ReportsError("Card name is required")

    pool = _filtered_pool(
        conn,
        set_code=set_code,
        owned_filter=normalized_owned,
        foil_filter=normalized_foil,
        search=search,
    )
    release_dates = _load_set_release_dates(conn)
    variants = _catalog_variants(pool, trimmed_name, release_dates=release_dates)
    if not variants:
        raise ReportsError("No variants found for this card name", status_code=404)

    return {
        "name": trimmed_name,
        "search": search.strip(),
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
    set_code: str = "All",
    owned_filter: str = "all",
    foil_filter: str = "all",
    page: int = 1,
    page_size: int = SEARCH_PAGE_SIZE,
) -> dict:
    normalized_owned = _normalize_owned_filter(owned_filter)
    normalized_foil = _normalize_foil_filter(foil_filter)
    term = search.strip()
    if not term:
        return {
            "search": "",
            "setCode": set_code,
            "ownedFilter": normalized_owned,
            "foilFilter": normalized_foil,
            "page": 1,
            "pageSize": max(1, min(int(page_size), MAX_SEARCH_PAGE_SIZE)),
            "totalMatches": 0,
            "totalPages": 1,
            "cards": [],
        }

    pool = _filtered_pool(
        conn,
        set_code=set_code,
        owned_filter=normalized_owned,
        foil_filter=normalized_foil,
        search=term,
    )
    release_dates = _load_set_release_dates(conn)
    ranked = sorted(
        pool,
        key=lambda card: _newest_first_key(card, release_dates),
        reverse=True,
    )
    unique_ranked = _dedupe_ranked_by_name(ranked)
    total = len(unique_ranked)
    safe_page_size = max(1, min(int(page_size), MAX_SEARCH_PAGE_SIZE))
    safe_page = max(1, page)
    start = (safe_page - 1) * safe_page_size
    page_cards = unique_ranked[start : start + safe_page_size]
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size) if total else 1

    return {
        "search": term,
        "setCode": set_code,
        "ownedFilter": normalized_owned,
        "foilFilter": normalized_foil,
        "page": safe_page,
        "pageSize": safe_page_size,
        "totalMatches": total,
        "totalPages": total_pages,
        "cards": page_cards,
    }


def random_name_explore(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    set_code: str = "All",
    owned_filter: str = "all",
    foil_filter: str = "all",
) -> dict:
    normalized_owned = _normalize_owned_filter(owned_filter)
    normalized_foil = _normalize_foil_filter(foil_filter)
    pool = _filtered_pool(
        conn,
        set_code=set_code,
        owned_filter=normalized_owned,
        foil_filter=normalized_foil,
        search=search,
    )
    names = _unique_names(pool)
    if not names:
        raise ReportsError("No cards match these filters", status_code=404)
    name = random.choice(names)
    release_dates = _load_set_release_dates(conn)
    variants = _catalog_variants(pool, name, release_dates=release_dates)
    return {
        "name": name,
        "search": search.strip(),
        "setCode": set_code,
        "ownedFilter": normalized_owned,
        "foilFilter": normalized_foil,
        "variants": variants,
        "selectedIndex": 0,
        "totalVariants": len(variants),
    }


def random_card(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    set_code: str = "All",
    owned_filter: str = "all",
    foil_filter: str = "all",
) -> dict:
    normalized_owned = _normalize_owned_filter(owned_filter)
    normalized_foil = _normalize_foil_filter(foil_filter)
    pool = _filtered_pool(
        conn,
        set_code=set_code,
        owned_filter=normalized_owned,
        foil_filter=normalized_foil,
        search=search,
    )
    if not pool:
        raise ReportsError("No cards match these filters", status_code=404)
    return {
        "search": search.strip(),
        "setCode": set_code,
        "ownedFilter": normalized_owned,
        "foilFilter": normalized_foil,
        "card": random.choice(pool),
    }
