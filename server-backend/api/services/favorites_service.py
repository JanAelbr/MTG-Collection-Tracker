"""Favourite cards / art styles toggles and home hydration."""

from __future__ import annotations

import sqlite3

from api.services import reports_service, settings_service
from report.report_data import build_art_style_options_for_set, build_sorted_set_options
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


def _collection_cards_for_set(
    conn: sqlite3.Connection,
    set_code: str,
    *,
    art_style: str = "",
) -> list[dict]:
    payload = reports_service.list_report_cards(
        conn,
        report="all",
        set_code=set_code,
        art_style=art_style,
        owned_filter="all",
        foil_filter="all",
    )
    return list(payload.get("cards") or [])


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


def _hydrate_favorite_art_styles(
    conn: sqlite3.Connection,
    favorite_art_styles: list[dict],
) -> list[dict]:
    if not favorite_art_styles:
        return []
    icon_uris = load_set_icon_uris(conn)
    option_cache: dict[str, dict[str, dict]] = {}
    result: list[dict] = []
    for item in favorite_art_styles:
        set_code = item["setCode"]
        art_style = item["artStyle"]
        if set_code not in option_cache:
            options = build_art_style_options_for_set(conn, set_code)
            option_cache[set_code] = {
                str(opt.get("artStyle") or ""): opt
                for opt in options
            }
        option = option_cache[set_code].get(art_style)
        cards = _collection_cards_for_set(conn, set_code, art_style=art_style)
        for card in cards:
            card["favorite"] = True
        result.append({
            "setCode": set_code,
            "artStyle": art_style,
            "label": art_style,
            "favorite": True,
            "ownedCount": option.get("ownedCount") if option else 0,
            "catalogCount": option.get("catalogCount") if option else len(cards),
            "iconUri": icon_uris.get(set_code) or "",
            "missing": option is None and not cards,
            "cards": cards,
        })
    return result


def _hydrate_favorite_cards(
    conn: sqlite3.Connection,
    favorite_cards: list[dict],
) -> list[dict]:
    if not favorite_cards:
        return []
    by_set: dict[str, list[dict]] = {}
    for item in favorite_cards:
        by_set.setdefault(item["setCode"], []).append(item)

    indexed: dict[str, dict] = {}
    for set_code in by_set:
        for card in _collection_cards_for_set(conn, set_code):
            key = favorite_card_key(card["setCode"], card["collectorNumber"], card["finish"])
            indexed[key] = card

    result: list[dict] = []
    for item in favorite_cards:
        set_code = item["setCode"]
        collector_number = item["collectorNumber"]
        finish = normalize_finish(item["finish"])
        key = favorite_card_key(set_code, collector_number, finish)
        match = indexed.get(key)
        if match:
            result.append({**match, "favorite": True, "missing": False})
            continue
        result.append({
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
        })
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


def list_favorites(conn: sqlite3.Connection) -> dict:
    favorite_sets = settings_service.get_favorite_sets(conn)
    favorite_art_styles = settings_service.get_favorite_art_styles(conn)
    favorite_cards = settings_service.get_favorite_cards(conn)
    return {
        "sets": _hydrate_favorite_sets(conn, favorite_sets),
        "artStyles": _hydrate_favorite_art_styles(conn, favorite_art_styles),
        "cards": _hydrate_favorite_cards(conn, favorite_cards),
        "favoriteSets": favorite_sets,
        "favoriteArtStyles": favorite_art_styles,
        "favoriteCards": favorite_cards,
    }
