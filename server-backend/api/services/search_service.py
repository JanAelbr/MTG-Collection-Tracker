import random
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
    name = (card.get("name") or "").lower()
    return term in name


def _filtered_pool(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    owned_filter: str,
    foil_filter: str,
    search: str = "",
) -> list[dict]:
    settings = settings_service.get_settings(conn)
    term = search.strip()
    set_codes = _resolve_set_codes(conn, set_code=set_code, search_term=term or None)
    cards, _compare_date = _load_enriched_report_cards(
        conn,
        set_codes=set_codes,
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
    if not term:
        return filtered
    lowered = term.lower()
    return [card for card in filtered if _card_matches_term(card, lowered)]


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
    variants = _build_variants(
        conn,
        trimmed_name,
        pool,
        release_dates=release_dates,
    )
    if not variants:
        raise ReportsError("No variants found for this card name", status_code=404)

    full_pool = _filtered_pool(
        conn,
        set_code=set_code,
        owned_filter=normalized_owned,
        foil_filter="all",
        search=search,
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
    variants = _build_variants(conn, name, pool, release_dates=release_dates)
    print_flags = _load_print_finish_flags(conn, name)
    finish_catalog = _finish_catalog_for_name(
        _filtered_pool(
            conn,
            set_code=set_code,
            owned_filter=normalized_owned,
            foil_filter="all",
            search=search,
        ),
        name,
        print_flags=print_flags,
    )
    _merge_variant_finishes(variants, finish_catalog, print_flags=print_flags)
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
