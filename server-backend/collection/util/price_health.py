"""Detect Cardmarket URL / price gaps for owned finishes."""

from __future__ import annotations

from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, has_finish_flag
from util.cardmarket_urls import cardmarket_url_for_finish, coerce_cardmarket_url


def _row_value(row: dict, key: str):
    if isinstance(row, dict):
        return row.get(key)
    return row[key]


def _market_value_for_finish(row: dict, finish: int):
    if finish == FINISH_FOIL:
        return _row_value(row, "market_value_foil")
    if finish == FINISH_ETCHED:
        etched = _row_value(row, "market_value_etched")
        if etched is not None:
            return etched
        return _row_value(row, "market_value_foil")
    return _row_value(row, "market_value")


def _owned_finish(row: dict, finish: int) -> bool:
    if finish == FINISH_NONFOIL:
        return bool(
            _row_value(row, "owned_nonfoil")
            or _row_value(row, "purchase_value_nonfoil") is not None
            or int(_row_value(row, "instance_count_nonfoil") or 0) > 0
        )
    if finish == FINISH_FOIL:
        return bool(
            _row_value(row, "owned_foil")
            or _row_value(row, "purchase_value_foil") is not None
            or int(_row_value(row, "instance_count_foil") or 0) > 0
        )
    return bool(
        _row_value(row, "owned_etched")
        or _row_value(row, "purchase_value_etched") is not None
        or int(_row_value(row, "instance_count_etched") or 0) > 0
    )


def price_issues_for_card(row: dict) -> list[str]:
    """Return issue codes like missing_url:foil or no_price:nonfoil."""
    issues: list[str] = []
    checks = (
        (FINISH_NONFOIL, "nonfoil"),
        (FINISH_FOIL, "foil"),
        (FINISH_ETCHED, "etched"),
    )
    for finish, label in checks:
        if not _owned_finish(row, finish):
            continue
        if not has_finish_flag(row, finish) and finish != FINISH_ETCHED:
            continue
        url = cardmarket_url_for_finish(row, finish)
        if not coerce_cardmarket_url(url):
            issues.append(f"missing_url:{label}")
            continue
        if _market_value_for_finish(row, finish) is None:
            issues.append(f"no_price:{label}")
    return issues


def card_has_price_issues(row: dict) -> bool:
    return bool(price_issues_for_card(row))
