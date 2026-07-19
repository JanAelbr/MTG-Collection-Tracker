import sqlite3

import pandas as pd

from lib.config import DB_PATH
from report.report_queries import (
    ALL_CARDS_QUERY,
    ORPHAN_PURCHASES_QUERY,
    SET_CARDS_QUERY,
    SET_ORPHAN_PURCHASES_QUERY,
)
from report.serialize_helpers import str_or_empty
from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, MARKET_VALUE_COLUMNS
from util.card_metadata import card_metadata_snake
from util.db_migrate import ensure_card_columns
from util.price_history import load_price_snapshot_payload

DEFAULT_PAGE_SIZE = 25


def _float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _display_name(set_code, collector_number, name) -> str:
    text = str_or_empty(name)
    if text:
        return text
    set_label = str_or_empty(set_code)
    number_label = str_or_empty(collector_number)
    if set_label and number_label:
        return f"{set_label} #{number_label}"
    return "Unknown"


def _finish_frame(source: pd.DataFrame, *, finish: int, current_value) -> pd.DataFrame:
    frame = source.copy()
    frame["finish"] = finish
    frame["purchase_value"] = pd.NA
    frame["current_value"] = current_value
    frame["profit_loss"] = pd.NA
    return frame


def _priced_unowned_rows(unowned: pd.DataFrame, finish: int) -> pd.DataFrame:
    column = MARKET_VALUE_COLUMNS[finish]
    values = unowned[column]
    return unowned[values.notna() & (values.astype(float) > 0)]


# Expand catalog rows into finish rows, including cards without prices.
def expand_cards_for_ranking(cards_df: pd.DataFrame) -> pd.DataFrame:
    if cards_df.empty:
        return cards_df

    owned = cards_df[cards_df["purchase_value"].notna()]
    unowned = cards_df[cards_df["purchase_value"].isna()]
    parts: list[pd.DataFrame] = []
    if not owned.empty:
        parts.append(owned)

    if not unowned.empty:
        nonfoil = _priced_unowned_rows(unowned, FINISH_NONFOIL)
        if not nonfoil.empty:
            parts.append(_finish_frame(nonfoil, finish=0, current_value=nonfoil["market_value"]))

        foil_rows = _priced_unowned_rows(unowned, FINISH_FOIL)
        if not foil_rows.empty:
            parts.append(_finish_frame(foil_rows, finish=1, current_value=foil_rows["market_value_foil"]))

        etched_rows = _priced_unowned_rows(unowned, FINISH_ETCHED)
        if not etched_rows.empty:
            parts.append(_finish_frame(etched_rows, finish=2, current_value=etched_rows["market_value_etched"]))

        neither = unowned[
            unowned["market_value"].isna()
            & unowned["market_value_foil"].isna()
            & unowned["market_value_etched"].isna()
        ]
        if not neither.empty:
            fallback = neither.copy()
            fallback["finish"] = fallback["finish"].fillna(0).astype(int)
            fallback["purchase_value"] = pd.NA
            fallback["current_value"] = pd.NA
            fallback["profit_loss"] = pd.NA
            parts.append(fallback)

    if not parts:
        return pd.DataFrame(columns=cards_df.columns)
    return pd.concat(parts, ignore_index=True)


# Load owned and unowned finish rows for ranked reports.
def load_ranked_cards_data() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        ensure_card_columns(conn)
        cards_df = pd.read_sql_query(ALL_CARDS_QUERY, conn)
        orphan_df = pd.read_sql_query(ORPHAN_PURCHASES_QUERY, conn)
    if not orphan_df.empty:
        cards_df = pd.concat([cards_df, orphan_df], ignore_index=True)
    return expand_cards_for_ranking(cards_df)


# Load finish rows for a single set.
def load_ranked_cards_data_for_set(set_code: str) -> pd.DataFrame:
    normalized = (set_code or "").strip().upper()
    if not normalized:
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        ensure_card_columns(conn)
        cards_df = pd.read_sql_query(SET_CARDS_QUERY, conn, params=(normalized,))
        orphan_df = pd.read_sql_query(SET_ORPHAN_PURCHASES_QUERY, conn, params=(normalized,))
    if not orphan_df.empty:
        cards_df = pd.concat([cards_df, orphan_df], ignore_index=True)
    return expand_cards_for_ranking(cards_df)


def _int_flag(value) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


# Build compact card rows for client-side ranked report rendering.
def serialize_ranked_cards(cards_df: pd.DataFrame) -> list[dict]:
    if cards_df.empty:
        return []

    cards = []
    for row in cards_df.itertuples(index=False):
        purchase_value = _float_or_none(row.purchase_value)
        profit_loss = None
        if purchase_value is not None and purchase_value != 0:
            profit_loss = _float_or_none(row.profit_loss)
        cards.append({
            "set_code": row.set_code,
            "collector_number": str(row.collector_number),
            "name": _display_name(row.set_code, row.collector_number, row.name),
            "art_style": str_or_empty(row.art_style),
            "finish": int(row.finish),
            "foil": int(row.finish),
            "purchase_value": purchase_value,
            "current_value": _float_or_none(row.current_value),
            "profit_loss": profit_loss,
            "market_value": _float_or_none(row.market_value),
            "market_value_foil": _float_or_none(row.market_value_foil),
            "market_value_etched": _float_or_none(row.market_value_etched),
            "has_nonfoil": _int_flag(row.has_nonfoil),
            "has_foil": _int_flag(row.has_foil),
            "has_etched": _int_flag(row.has_etched),
            "image_uri": str_or_empty(row.image_uri),
            "image_uri_back": str_or_empty(getattr(row, "image_uri_back", "")),
            "cardmarket_url": str_or_empty(row.cardmarket_url),
            "cardmarket_url_foil": str_or_empty(row.cardmarket_url_foil),
            **card_metadata_snake(row),
        })
    return cards


# Build the client payload shared by top, risers, and fallers reports.
def load_ranked_client_payload(cards_df: pd.DataFrame) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        snapshot_payload = load_price_snapshot_payload(conn)

    return {
        "defaultPageSize": DEFAULT_PAGE_SIZE,
        "cards": serialize_ranked_cards(cards_df),
        **snapshot_payload,
    }
