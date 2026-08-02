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


def _optional_int_flag(value) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row_flag(row, column: str) -> int | None:
    if column not in row.index:
        return None
    return _optional_int_flag(row[column])


def _fallback_finish_for_unpriced(row) -> int:
    """Pick a catalog finish when finish flags do not allow any explicit finish."""
    has_nonfoil = _row_flag(row, "has_nonfoil")
    has_foil = _row_flag(row, "has_foil")
    has_etched = _row_flag(row, "has_etched")
    if has_nonfoil == 0 and has_foil == 1 and not has_etched:
        return FINISH_FOIL
    if has_nonfoil == 0 and has_etched == 1 and not has_foil:
        return FINISH_ETCHED
    existing = row["finish"] if "finish" in row.index else None
    if existing is not None and not pd.isna(existing):
        return int(existing)
    return FINISH_NONFOIL


def _market_value_for_finish(row, finish: int):
    column = MARKET_VALUE_COLUMNS[finish]
    if column not in row.index:
        return None
    value = row[column]
    if value is None or pd.isna(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _catalog_finishes_for_row(row, owned_finishes: set[int] | None = None) -> list[int]:
    """Return every finish this print should appear as in the all-cards gallery."""
    owned = owned_finishes or set()
    finishes: list[int] = []
    for finish in (FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED):
        flag = _row_flag(row, HAS_FINISH_COLUMNS[finish])
        if flag == 0:
            continue
        if flag == 1:
            finishes.append(finish)
            continue
        # Unknown flag: keep owned finishes and priced finishes only.
        if finish in owned or _market_value_for_finish(row, finish) is not None:
            finishes.append(finish)
    if finishes:
        return finishes
    return [_fallback_finish_for_unpriced(row)]


def _unowned_finish_row(base_row, *, finish: int) -> pd.Series:
    row = base_row.copy()
    row["finish"] = finish
    row["purchase_value"] = pd.NA
    row["current_value"] = _market_value_for_finish(base_row, finish)
    row["profit_loss"] = pd.NA
    return row


def _owned_finish_row(owned_row, base_row, *, finish: int) -> pd.Series:
    row = owned_row.copy()
    row["finish"] = finish
    current = _market_value_for_finish(base_row, finish)
    if current is not None:
        row["current_value"] = current
        purchase = row["purchase_value"] if "purchase_value" in row.index else None
        if purchase is not None and not pd.isna(purchase) and float(purchase) != 0:
            row["profit_loss"] = current - float(purchase)
        else:
            row["profit_loss"] = pd.NA
    return row


# Expand catalog rows into one row per available finish (nonfoil / foil / etched).
def expand_cards_for_ranking(cards_df: pd.DataFrame) -> pd.DataFrame:
    if cards_df.empty:
        return cards_df

    parts: list[pd.Series] = []
    grouped = cards_df.groupby(["set_code", "collector_number"], sort=False, dropna=False)
    for _, group in grouped:
        base_row = group.iloc[0]
        owned_by_finish: dict[int, pd.Series] = {}
        for _, row in group.iterrows():
            purchase = row["purchase_value"] if "purchase_value" in row.index else None
            finish_raw = row["finish"] if "finish" in row.index else None
            if purchase is None or pd.isna(purchase) or finish_raw is None or pd.isna(finish_raw):
                continue
            owned_by_finish[int(finish_raw)] = row

        for finish in _catalog_finishes_for_row(base_row, set(owned_by_finish)):
            owned_row = owned_by_finish.get(finish)
            if owned_row is not None:
                parts.append(_owned_finish_row(owned_row, base_row, finish=finish))
            else:
                parts.append(_unowned_finish_row(base_row, finish=finish))

    if not parts:
        return pd.DataFrame(columns=cards_df.columns)
    return pd.DataFrame(parts).reset_index(drop=True)


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
