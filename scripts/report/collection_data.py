import sqlite3

import pandas as pd

from lib.config import DB_PATH
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.card_metadata import card_metadata_snake
from util.price_history import load_price_snapshot_payload


def _float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


# Build compact card rows for client-side collection rendering.
def serialize_collection_cards(cards_df: pd.DataFrame) -> list[dict]:
    cards = []
    for _, row in cards_df.iterrows():
        cards.append({
            "set_code": row["set_code"],
            "art_style": str_or_empty(row["art_style"]),
            "collector_number": str(row["collector_number"]),
            "name": deck_card_display_name(row),
            "finish": int(row["finish"]) if not pd.isna(row["finish"]) else 0,
            "foil": int(row["finish"]) if not pd.isna(row["finish"]) else 0,
            "purchase_value": _float_or_none(row["purchase_value"]),
            "current_value": _float_or_none(row["current_value"]),
            "profit_loss": _float_or_none(row["profit_loss"]),
            "market_value": _float_or_none(row["market_value"]),
            "market_value_foil": _float_or_none(row["market_value_foil"]),
            "market_value_etched": _float_or_none(row["market_value_etched"]),
            "image_uri": str_or_empty(row["image_uri"]),
            "cardmarket_url": str_or_empty(row["cardmarket_url"]),
            **card_metadata_snake(row),
        })
    return cards


# Build compact summary rows for client-side collection rendering.
def serialize_collection_summary(summary_df: pd.DataFrame) -> list[dict]:
    summary = []
    for _, row in summary_df.iterrows():
        summary.append({
            "set_code": row["set_code"],
            "art_style": row["art_style"],
            "cards": int(row["cards"]),
            "current_value": _float_or_none(row["current_value"]),
            "profit_loss": _float_or_none(row["profit_loss"]),
        })
    return summary


# Build the client payload for collection reports.
def load_collection_client_payload(
    cards_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    owned_only: bool,
) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        snapshot_payload = load_price_snapshot_payload(conn)

    return {
        "ownedOnly": owned_only,
        "cards": serialize_collection_cards(cards_df),
        "summary": serialize_collection_summary(summary_df),
        **snapshot_payload,
    }
