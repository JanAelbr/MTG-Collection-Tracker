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
from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    HAS_FINISH_COLUMNS,
    MARKET_VALUE_COLUMNS,
)
from util.card_metadata import card_metadata_snake
from util.db_migrate import ensure_card_columns

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


def _catalog_allows_finish(frame: pd.DataFrame, finish: int) -> pd.Series:
    """False when Scryfall flags explicitly say this finish does not exist."""
    column = HAS_FINISH_COLUMNS[finish]
    if column not in frame.columns:
        return pd.Series(True, index=frame.index)
    raw = frame[column]
    known = raw.notna()
    enabled = raw.fillna(0).astype(int).ne(0)
    return ~known | enabled


def _priced_unowned_rows(unowned: pd.DataFrame, finish: int) -> pd.DataFrame:
    column = MARKET_VALUE_COLUMNS[finish]
    values = unowned[column]
    mask = values.notna() & (values.astype(float) > 0) & _catalog_allows_finish(unowned, finish)
    return unowned[mask]


def _fallback_finish_for_unpriced(row) -> int:
    """Pick a catalog finish when a print has no usable market prices."""
    has_nonfoil = _optional_int_flag(row.get("has_nonfoil"))
    has_foil = _optional_int_flag(row.get("has_foil"))
    has_etched = _optional_int_flag(row.get("has_etched"))
    if has_nonfoil == 0 and has_foil == 1 and not has_etched:
        return FINISH_FOIL
    if has_nonfoil == 0 and has_etched == 1 and not has_foil:
        return FINISH_ETCHED
    existing = row.get("finish")
    if existing is not None and not pd.isna(existing):
        return int(existing)
    return FINISH_NONFOIL


def _optional_int_flag(value) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        covered_index: set = set()
        nonfoil = _priced_unowned_rows(unowned, FINISH_NONFOIL)
        if not nonfoil.empty:
            covered_index.update(nonfoil.index.tolist())
            parts.append(_finish_frame(nonfoil, finish=0, current_value=nonfoil["market_value"]))

        foil_rows = _priced_unowned_rows(unowned, FINISH_FOIL)
        if not foil_rows.empty:
            covered_index.update(foil_rows.index.tolist())
            parts.append(_finish_frame(foil_rows, finish=1, current_value=foil_rows["market_value_foil"]))

        etched_rows = _priced_unowned_rows(unowned, FINISH_ETCHED)
        if not etched_rows.empty:
            covered_index.update(etched_rows.index.tolist())
            parts.append(_finish_frame(etched_rows, finish=2, current_value=etched_rows["market_value_etched"]))

        remaining = unowned.drop(index=list(covered_index), errors="ignore")
        if not remaining.empty:
            fallback = remaining.copy()
            finishes = fallback.apply(_fallback_finish_for_unpriced, axis=1).astype(int)
            fallback["finish"] = finishes
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
