import sqlite3

import pandas as pd

from report.deck_queries import deck_scope
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.card_metadata import card_metadata_snake
from util.price_history import PriceSnapshotCache


def _float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _serialize_deck_cards(deck_df: pd.DataFrame) -> list[dict]:
    cards = []
    for _, row in deck_df.iterrows():
        cards.append({
            "deck_id": int(row["deck_id"]),
            "deck_name": row["deck_name"],
            "card_name": str_or_empty(row["card_name"]) or deck_card_display_name(row),
            "set_code": row["set_code"] or "",
            "collector_number": str(row["collector_number"]) if row["collector_number"] else "",
            "finish": int(row["finish"]),
            "foil": int(row["finish"]),
            "qty": int(row["qty"]),
            "section": row["section"],
            "in_catalog": bool(int(row["in_catalog"])),
            "catalog_name": deck_card_display_name(row),
            "art_style": str_or_empty(row["art_style"]),
            "sort_order": int(row["sort_order"]),
            "current_value": _float_or_none(row["current_value"]),
            "unit_value": _float_or_none(row["unit_value"]),
            "owned_qty": int(row["owned_qty"]),
            "invested": _float_or_none(row["invested"]),
            "purchase_value": _float_or_none(row.get("purchase_value")),
            "profit_loss": _float_or_none(row["profit_loss"]),
            "image_uri": str_or_empty(row["image_uri"]),
            "cardmarket_url": str_or_empty(row["cardmarket_url"]),
            **card_metadata_snake(row),
        })
    return cards


def _serialize_unknown_cards(deck_df: pd.DataFrame) -> list[dict]:
    unknown = deck_df[deck_df["current_value"].isna()]
    cards = []
    for _, row in unknown.iterrows():
        cards.append({
            "card_name": str_or_empty(row["card_name"]) or deck_card_display_name(row),
            "qty": int(row["qty"]),
            "section": row["section"],
            "set_code": row["set_code"] or "",
            "collector_number": str(row["collector_number"]) if row["collector_number"] else "",
            "finish": int(row["finish"]),
            "foil": int(row["finish"]),
        })
    return cards


def _aggregate_deck_purchase_price(deck_df: pd.DataFrame):
    if deck_df.empty or "deck_purchase_price" not in deck_df.columns:
        return None
    per_deck = deck_df.groupby("deck_id")["deck_purchase_price"].first()
    priced = per_deck.dropna()
    if priced.empty:
        return None
    return float(priced.sum())


def compute_deck_stats(
    deck_df: pd.DataFrame,
    conn: sqlite3.Connection,
    *,
    snapshot_cache: PriceSnapshotCache | None = None,
    include_portfolio_history: bool = True,
) -> dict:
    deck_size = int(deck_df["qty"].sum()) if not deck_df.empty else 0
    tracked_rows = deck_df[deck_df["in_catalog"] == 1] if not deck_df.empty else deck_df
    tracked_qty = int(tracked_rows["qty"].sum()) if not tracked_rows.empty else 0
    priced = deck_df[deck_df["current_value"].notna()] if not deck_df.empty else deck_df
    unknown = deck_df[deck_df["current_value"].isna()] if not deck_df.empty else deck_df
    owned = deck_df[deck_df["owned_qty"] > 0] if not deck_df.empty else deck_df

    current = priced["current_value"].sum(min_count=1) if not priced.empty else None
    unit_values = pd.to_numeric(deck_df["unit_value"], errors="coerce")
    owned_values = unit_values * deck_df["owned_qty"].astype("float64")
    owned_current = owned_values.sum(min_count=1) if not deck_df.empty else None
    owned_qty = int(owned["owned_qty"].sum()) if not owned.empty else 0
    average = priced["unit_value"].mean() if not priced.empty else None
    purchase_price = _aggregate_deck_purchase_price(deck_df)
    invested = owned["invested"].sum(min_count=1) if not owned.empty else None
    profit = owned["profit_loss"].sum(min_count=1) if not owned.empty else None

    if purchase_price is not None:
        if invested is None or invested == 0:
            invested = purchase_price
        if current is not None:
            profit = current - purchase_price

    return {
        "current": _float_or_none(current),
        "ownedCurrent": _float_or_none(owned_current),
        "invested": _float_or_none(invested),
        "profit": _float_or_none(profit),
        "purchasePrice": _float_or_none(purchase_price),
        "deckSize": deck_size,
        "trackedQty": tracked_qty,
        "ownedQty": owned_qty,
        "missingQty": max(deck_size - owned_qty, 0),
        "trackedCoverage": (
            round(tracked_qty / deck_size * 100, 1) if deck_size else None
        ),
        "ownedCoverage": (
            round(owned_qty / deck_size * 100, 1) if deck_size else None
        ),
        "average": _float_or_none(average),
        "unknownQty": int(unknown["qty"].sum()) if not unknown.empty else 0,
        "unknownCount": len(unknown),
        "unknownCards": _serialize_unknown_cards(unknown),
        "winners": int(len(owned[owned["profit_loss"] > 0])) if not owned.empty else 0,
        "losers": int(len(owned[owned["profit_loss"] < 0])) if not owned.empty else 0,
        "cards": _serialize_deck_cards(deck_df),
    }


def compute_deck_stats_page(
    deck_id: str,
    deck_df: pd.DataFrame,
    conn: sqlite3.Connection,
    *,
    snapshot_cache: PriceSnapshotCache | None = None,
    include_portfolio_history: bool = True,
) -> dict:
    scoped = deck_scope(deck_df, deck_id)
    return compute_deck_stats(
        scoped,
        conn,
        snapshot_cache=snapshot_cache,
        include_portfolio_history=include_portfolio_history,
    )
