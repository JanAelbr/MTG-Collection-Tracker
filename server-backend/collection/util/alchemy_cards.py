"""Detect and exclude Arena Alchemy cards from the collection UI."""

from __future__ import annotations


def is_alchemy_collector_number(collector_number: str | None) -> bool:
    return str(collector_number or "").strip().upper().startswith("A-")


def is_alchemy_scryfall_card(card: dict) -> bool:
    if is_alchemy_collector_number(card.get("collector_number")):
        return True

    promo_types = {str(value).lower() for value in (card.get("promo_types") or [])}
    if promo_types & {"alchemy", "rebalanced"}:
        return True

    games = {str(value).lower() for value in (card.get("games") or [])}
    if card.get("digital") and games and "paper" not in games:
        return True

    return False


def is_alchemy_art_style(art_style: str | None) -> bool:
    return "alchemy" in str(art_style or "").strip().lower()


def exclude_alchemy_sql(column: str = "collector_number") -> str:
    return f"UPPER({column}) NOT LIKE 'A-%'"


def exclude_alchemy_art_style_sql(column: str = "art_style") -> str:
    return f"LOWER(COALESCE({column}, '')) NOT LIKE '%alchemy%'"


def prune_alchemy_cards(conn) -> int:
    """Remove alchemy prints from the local catalog table."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cards' LIMIT 1"
    ).fetchone():
        return 0
    cursor = conn.execute(
        "DELETE FROM cards WHERE UPPER(collector_number) LIKE 'A-%'"
    )
    return cursor.rowcount
