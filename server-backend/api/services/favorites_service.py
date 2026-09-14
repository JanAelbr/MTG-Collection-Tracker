"""Favourite cards / art styles toggles and home hydration."""

from __future__ import annotations

import sqlite3

from api.services import reports_service, settings_service
from report.card_detail_data import collector_sort_key
from report.report_data import build_art_style_options_for_set, build_sorted_set_options
from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql
from util.card_finishes import finish_label, normalize_finish
from util.favorites import (
    favorite_art_style_key,
    favorite_card_key,
    normalize_favorite_art_style,
    normalize_favorite_art_styles,
    normalize_favorite_card,
    normalize_favorite_cards,
)
from util.set_catalog import load_set_icon_uris


def toggle_favorite_card(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
) -> dict:
    card = normalize_favorite_card({
        "setCode": set_code,
        "collectorNumber": collector_number,
        "finish": finish,
    })
    if card is None:
        raise ValueError("Invalid favourite card")
    key = favorite_card_key(card["setCode"], card["collectorNumber"], card["finish"])
    favorites = settings_service.get_favorite_cards(conn)
    existing_keys = {
        favorite_card_key(item["setCode"], item["collectorNumber"], item["finish"])
        for item in favorites
    }
    if key in existing_keys:
        next_favorites = [
            item for item in favorites
            if favorite_card_key(item["setCode"], item["collectorNumber"], item["finish"]) != key
        ]
        favorite = False
    else:
        next_favorites = [*favorites, card]
        favorite = True
    saved = settings_service.save_favorite_cards(conn, next_favorites)
    return {
        "setCode": card["setCode"],
        "collectorNumber": card["collectorNumber"],
        "finish": card["finish"],
        "favorite": favorite,
        "favoriteCards": saved,
    }


def toggle_favorite_art_style(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    art_style: str,
) -> dict:
    style = normalize_favorite_art_style({
        "setCode": set_code,
        "artStyle": art_style,
    })
    if style is None:
        raise ValueError("Invalid favourite art style")
    key = favorite_art_style_key(style["setCode"], style["artStyle"])
    favorites = settings_service.get_favorite_art_styles(conn)
    existing_keys = {
        favorite_art_style_key(item["setCode"], item["artStyle"])
        for item in favorites
    }
    if key in existing_keys:
        next_favorites = [
            item for item in favorites
            if favorite_art_style_key(item["setCode"], item["artStyle"]) != key
        ]
        favorite = False
    else:
        next_favorites = [*favorites, style]
        favorite = True
    saved = settings_service.save_favorite_art_styles(conn, next_favorites)
    return {
        "setCode": style["setCode"],
        "artStyle": style["artStyle"],
        "favorite": favorite,
        "favoriteArtStyles": saved,
    }


def _hydrate_favorite_sets(conn: sqlite3.Connection, favorite_sets: list[str]) -> list[dict]:
    if not favorite_sets:
        return []
    options = build_sorted_set_options(
        conn,
        favorite_sets=favorite_sets,
        sort_mode=settings_service.get_set_sort_mode(conn),
        include_all=False,
    )
    by_code = {opt["setCode"].upper(): opt for opt in options if opt.get("setCode")}
    result: list[dict] = []
    seen: set[str] = set()
    for code in favorite_sets:
        upper = code.upper()
        if upper in seen:
            continue
        seen.add(upper)
        option = by_code.get(upper)
        if option:
            result.append({**option, "favorite": True})
            continue
        result.append({
            "setCode": upper,
            "label": upper,
            "name": upper,
            "favorite": True,
            "ownedCount": 0,
            "catalogCount": 0,
            "missing": True,
        })
    return result


def _unique_print_tuples(*groups: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for group in groups:
        for set_code, collector_number in group:
            key = (str(set_code or "").strip().upper(), str(collector_number or "").strip())
            if not key[0] or not key[1] or key in seen:
                continue
            seen.add(key)
            result.append(key)
    return result


def _index_cards_by_finish(cards: list[dict]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for card in cards:
        key = favorite_card_key(card["setCode"], card["collectorNumber"], card["finish"])
        indexed[key] = card
    return indexed


def _group_cards_by_print(cards: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for card in cards:
        key = (
            str(card.get("setCode") or "").strip().upper(),
            str(card.get("collectorNumber") or "").strip(),
        )
        grouped.setdefault(key, []).append(card)
    return grouped


def _sort_gallery_cards(cards: list[dict]) -> list[dict]:
    return sorted(
        cards,
        key=lambda card: (
            collector_sort_key(card.get("collectorNumber")),
            int(card.get("finish") or 0),
        ),
    )


def _placeholder_favorite_card(item: dict) -> dict:
    finish = normalize_finish(item["finish"])
    set_code = item["setCode"]
    collector_number = item["collectorNumber"]
    return {
        "setCode": set_code,
        "collectorNumber": collector_number,
        "finish": finish,
        "foil": finish,
        "finishLabel": finish_label(finish),
        "name": f"{set_code} #{collector_number}",
        "imageUri": "",
        "imageUriBack": "",
        "owned": False,
        "currentValue": None,
        "favorite": True,
        "missing": True,
    }


def _query_art_style_print_rows(
    conn: sqlite3.Connection,
    favorite_art_styles: list[dict],
) -> list[tuple]:
    conn.execute("DROP TABLE IF EXISTS _fav_art_style_keys")
    conn.execute(
        """
        CREATE TEMP TABLE _fav_art_style_keys (
            set_code TEXT NOT NULL,
            art_style TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO _fav_art_style_keys (set_code, art_style) VALUES (?, ?)",
        [(item["setCode"], item["artStyle"]) for item in favorite_art_styles],
    )
    try:
        return conn.execute(
            f"""
            SELECT c.set_code, c.collector_number, c.art_style
            FROM cards c
            JOIN _fav_art_style_keys k
                ON k.set_code = c.set_code AND k.art_style = c.art_style
            WHERE {exclude_alchemy_sql("c.collector_number")}
              AND {exclude_alchemy_art_style_sql("c.art_style")}
            """
        ).fetchall()
    finally:
        conn.execute("DROP TABLE IF EXISTS _fav_art_style_keys")


def _load_art_style_print_keys(
    conn: sqlite3.Connection,
    favorite_art_styles: list[dict],
) -> dict[str, list[tuple[str, str]]]:
    grouped: dict[str, list[tuple[str, str]]] = {
        favorite_art_style_key(item["setCode"], item["artStyle"]): []
        for item in favorite_art_styles
    }
    if not favorite_art_styles:
        return grouped
    for set_code, collector_number, art_style in _query_art_style_print_rows(
        conn,
        favorite_art_styles,
    ):
        key = favorite_art_style_key(set_code, art_style)
        grouped.setdefault(key, []).append((set_code, collector_number))
    return grouped


def _art_style_option_cache(conn: sqlite3.Connection, set_codes: list[str]) -> dict[str, dict[str, dict]]:
    cache: dict[str, dict[str, dict]] = {}
    for set_code in set_codes:
        if set_code in cache:
            continue
        options = build_art_style_options_for_set(conn, set_code)
        cache[set_code] = {str(opt.get("artStyle") or ""): opt for opt in options}
    return cache


def _cards_for_prints(
    prints: list[tuple[str, str]],
    by_print: dict[tuple[str, str], list[dict]],
) -> list[dict]:
    cards: list[dict] = []
    for set_code, collector_number in prints:
        key = (str(set_code).upper(), str(collector_number))
        for card in by_print.get(key, []):
            cards.append({**card, "favorite": True})
    return _sort_gallery_cards(cards)


def _hydrate_favorite_art_styles(
    favorite_art_styles: list[dict],
    *,
    prints_by_style: dict[str, list[tuple[str, str]]],
    by_print: dict[tuple[str, str], list[dict]],
    option_cache: dict[str, dict[str, dict]],
    icon_uris: dict[str, str],
    family_roots: dict[str, str],
) -> list[dict]:
    result: list[dict] = []
    for item in favorite_art_styles:
        set_code = item["setCode"]
        art_style = item["artStyle"]
        style_key = favorite_art_style_key(set_code, art_style)
        cards = _cards_for_prints(prints_by_style.get(style_key, []), by_print)
        option = option_cache.get(set_code, {}).get(art_style)
        root = family_roots.get(set_code) or set_code
        result.append({
            "setCode": set_code,
            "artStyle": art_style,
            "label": art_style,
            "favorite": True,
            "ownedCount": option.get("ownedCount") if option else 0,
            "catalogCount": option.get("catalogCount") if option else len(cards),
            "iconUri": icon_uris.get(set_code) or icon_uris.get(root) or "",
            "familyRoot": root,
            "missing": option is None and not cards,
            "cards": cards,
        })
    return result


def _hydrate_favorite_cards(
    favorite_cards: list[dict],
    indexed: dict[str, dict],
) -> list[dict]:
    result: list[dict] = []
    for item in favorite_cards:
        finish = normalize_finish(item["finish"])
        key = favorite_card_key(item["setCode"], item["collectorNumber"], finish)
        match = indexed.get(key)
        if match:
            result.append({**match, "favorite": True, "missing": False})
            continue
        result.append(_placeholder_favorite_card({**item, "finish": finish}))
    return result


def reorder_favorite_cards(conn: sqlite3.Connection, ordered_items: list) -> list[dict]:
    """Persist a new favourite-card order (must be a permutation of current favourites)."""
    current = settings_service.get_favorite_cards(conn)
    current_map = {
        favorite_card_key(item["setCode"], item["collectorNumber"], item["finish"]): item
        for item in current
    }
    ordered = normalize_favorite_cards(ordered_items)
    result: list[dict] = []
    seen: set[str] = set()
    for item in ordered:
        key = favorite_card_key(item["setCode"], item["collectorNumber"], item["finish"])
        existing = current_map.get(key)
        if existing is None or key in seen:
            continue
        seen.add(key)
        result.append(existing)
    for key, item in current_map.items():
        if key not in seen:
            result.append(item)
    return settings_service.save_favorite_cards(conn, result)


def reorder_favorite_art_styles(conn: sqlite3.Connection, ordered_items: list) -> list[dict]:
    """Persist a new favourite-art-style order (must be a permutation of current favourites)."""
    current = settings_service.get_favorite_art_styles(conn)
    current_map = {
        favorite_art_style_key(item["setCode"], item["artStyle"]): item
        for item in current
    }
    ordered = normalize_favorite_art_styles(ordered_items)
    result: list[dict] = []
    seen: set[str] = set()
    for item in ordered:
        key = favorite_art_style_key(item["setCode"], item["artStyle"])
        existing = current_map.get(key)
        if existing is None or key in seen:
            continue
        seen.add(key)
        result.append(existing)
    for key, item in current_map.items():
        if key not in seen:
            result.append(item)
    return settings_service.save_favorite_art_styles(conn, result)


def _enriched_favorite_prints(
    conn: sqlite3.Connection,
    favorite_cards: list[dict],
    prints_by_style: dict[str, list[tuple[str, str]]],
) -> list[dict]:
    card_prints = [(item["setCode"], item["collectorNumber"]) for item in favorite_cards]
    style_prints = [print_key for group in prints_by_style.values() for print_key in group]
    return reports_service._load_enriched_prints(
        conn,
        _unique_print_tuples(card_prints, style_prints),
    )


def list_favorites(conn: sqlite3.Connection) -> dict:
    from util.set_families import load_family_roots

    favorite_sets = settings_service.get_favorite_sets(conn)
    favorite_art_styles = settings_service.get_favorite_art_styles(conn)
    favorite_cards = settings_service.get_favorite_cards(conn)
    prints_by_style = _load_art_style_print_keys(conn, favorite_art_styles)
    enriched = _enriched_favorite_prints(conn, favorite_cards, prints_by_style)
    return {
        "sets": _hydrate_favorite_sets(conn, favorite_sets),
        "artStyles": _hydrate_favorite_art_styles(
            favorite_art_styles,
            prints_by_style=prints_by_style,
            by_print=_group_cards_by_print(enriched),
            option_cache=_art_style_option_cache(
                conn,
                [item["setCode"] for item in favorite_art_styles],
            ),
            icon_uris=load_set_icon_uris(conn),
            family_roots=load_family_roots(conn),
        ),
        "cards": _hydrate_favorite_cards(favorite_cards, _index_cards_by_finish(enriched)),
        "favoriteSets": favorite_sets,
        "favoriteArtStyles": favorite_art_styles,
        "favoriteCards": favorite_cards,
    }
