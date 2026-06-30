import sqlite3

import pandas as pd

from lib.config import DB_PATH
from report.report_data import get_all_set_codes
from util.db_migrate import ensure_card_columns

from report.card_detail_data import collector_sort_key
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.card_metadata import card_metadata_snake
from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, finish_available

MANAGER_CARDS_QUERY = """
SELECT
    c.set_code,
    c.collector_number,
    c.name,
    c.art_style,
    c.image_uri,
    c.colors,
    c.type_line,
    c.card_type,
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched,
    p0.purchase_value AS purchase_value_nonfoil,
    p1.purchase_value AS purchase_value_foil,
    p2.purchase_value AS purchase_value_etched
FROM cards c
LEFT JOIN purchases p0
    ON p0.set_code = c.set_code
    AND p0.collector_number = c.collector_number
    AND p0.finish = 0
LEFT JOIN purchases p1
    ON p1.set_code = c.set_code
    AND p1.collector_number = c.collector_number
    AND p1.finish = 1
LEFT JOIN purchases p2
    ON p2.set_code = c.set_code
    AND p2.collector_number = c.collector_number
    AND p2.finish = 2
WHERE c.set_code = ?
"""


def _float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _finish_available(row, finish: int, owned: bool) -> bool:
    return finish_available(row, finish, owned=owned)


def _serialize_manager_card(row) -> dict:
    owned_nonfoil = row["purchase_value_nonfoil"] is not None and not pd.isna(row["purchase_value_nonfoil"])
    owned_foil = row["purchase_value_foil"] is not None and not pd.isna(row["purchase_value_foil"])
    owned_etched = row["purchase_value_etched"] is not None and not pd.isna(row["purchase_value_etched"])
    has_nonfoil = _finish_available(row, FINISH_NONFOIL, owned_nonfoil)
    has_foil = _finish_available(row, FINISH_FOIL, owned_foil)
    has_etched = _finish_available(row, FINISH_ETCHED, owned_etched)

    return {
        "set_code": row["set_code"],
        "collector_number": str(row["collector_number"]),
        "name": deck_card_display_name(row),
        "art_style": str_or_empty(row["art_style"]),
        "image_uri": str_or_empty(row["image_uri"]),
        **card_metadata_snake(row),
        "market_value": _float_or_none(row["market_value"]),
        "market_value_foil": _float_or_none(row["market_value_foil"]),
        "market_value_etched": _float_or_none(row["market_value_etched"]),
        "has_nonfoil": has_nonfoil,
        "has_foil": has_foil,
        "has_etched": has_etched,
        "owned_nonfoil": owned_nonfoil,
        "owned_foil": owned_foil,
        "owned_etched": owned_etched,
        "purchase_value_nonfoil": _float_or_none(row["purchase_value_nonfoil"]),
        "purchase_value_foil": _float_or_none(row["purchase_value_foil"]),
        "purchase_value_etched": _float_or_none(row["purchase_value_etched"]),
    }


def load_manager_cards_for_set(conn: sqlite3.Connection, set_code: str) -> list[dict]:
    ensure_card_columns(conn)
    cards_df = pd.read_sql_query(MANAGER_CARDS_QUERY, conn, params=(set_code,))
    cards = [_serialize_manager_card(row) for _, row in cards_df.iterrows()]
    return sorted(cards, key=lambda card: collector_sort_key(card["collector_number"]))


# Build the client payload for collection manager pages.
def load_manager_client_payload() -> dict:
    sets = get_all_set_codes()
    with sqlite3.connect(DB_PATH) as conn:
        ensure_card_columns(conn)
        conn.commit()
        cards_by_set = {
            set_code: load_manager_cards_for_set(conn, set_code)
            for set_code in sets
        }

    return {
        "sets": sets,
        "defaultSet": sets[0] if sets else "",
        "cardsBySet": cards_by_set,
    }
