"""Normalize and key favourite cards and art styles."""

from __future__ import annotations

from lib.config import normalize_set_code
from util.card_finishes import normalize_finish


def favorite_card_key(set_code: str, collector_number: str, finish: int) -> str:
    return f"{normalize_set_code(set_code)}|{str(collector_number).strip()}|{int(finish)}"


def favorite_art_style_key(set_code: str, art_style: str) -> str:
    return f"{normalize_set_code(set_code)}|{str(art_style or '').strip()}"


def normalize_favorite_card(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    set_code = normalize_set_code(item.get("setCode") or item.get("set_code") or "")
    collector_number = str(
        item.get("collectorNumber") if item.get("collectorNumber") is not None
        else item.get("collector_number") or ""
    ).strip()
    if not set_code or not collector_number:
        return None
    finish = normalize_finish(item.get("finish"))
    return {
        "setCode": set_code,
        "collectorNumber": collector_number,
        "finish": finish,
    }


def normalize_favorite_cards(items) -> list[dict]:
    if not isinstance(items, list):
        return []
    seen: set[str] = set()
    result: list[dict] = []
    for raw in items:
        card = normalize_favorite_card(raw)
        if card is None:
            continue
        key = favorite_card_key(card["setCode"], card["collectorNumber"], card["finish"])
        if key in seen:
            continue
        seen.add(key)
        result.append(card)
    return result


def normalize_favorite_art_style(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    set_code = normalize_set_code(item.get("setCode") or item.get("set_code") or "")
    art_style = str(item.get("artStyle") if item.get("artStyle") is not None else item.get("art_style") or "").strip()
    if not set_code or not art_style:
        return None
    return {
        "setCode": set_code,
        "artStyle": art_style,
    }


def normalize_favorite_art_styles(items) -> list[dict]:
    if not isinstance(items, list):
        return []
    seen: set[str] = set()
    result: list[dict] = []
    for raw in items:
        style = normalize_favorite_art_style(raw)
        if style is None:
            continue
        key = favorite_art_style_key(style["setCode"], style["artStyle"])
        if key in seen:
            continue
        seen.add(key)
        result.append(style)
    return result
