import sqlite3

from lib.config import DB_PATH
from report.report_data import get_all_set_codes
from util.db_migrate import ensure_card_columns

from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.card_metadata import card_metadata_snake
from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    has_finish_flag,
)
from util.app_tables import ensure_app_tables

MANAGER_CARDS_FROM = """
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
LEFT JOIN (
    SELECT set_code, collector_number, COUNT(*) AS instance_count
    FROM card_instances
    WHERE finish = 0
    GROUP BY set_code, collector_number
) i0
    ON i0.set_code = c.set_code
    AND i0.collector_number = c.collector_number
LEFT JOIN (
    SELECT set_code, collector_number, COUNT(*) AS instance_count
    FROM card_instances
    WHERE finish = 1
    GROUP BY set_code, collector_number
) i1
    ON i1.set_code = c.set_code
    AND i1.collector_number = c.collector_number
LEFT JOIN (
    SELECT set_code, collector_number, COUNT(*) AS instance_count
    FROM card_instances
    WHERE finish = 2
    GROUP BY set_code, collector_number
) i2
    ON i2.set_code = c.set_code
    AND i2.collector_number = c.collector_number
"""

MANAGER_CARDS_SELECT = """
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
    p2.purchase_value AS purchase_value_etched,
    i0.instance_count AS instance_count_nonfoil,
    i1.instance_count AS instance_count_foil,
    i2.instance_count AS instance_count_etched
"""

MANAGER_CARDS_ORDER = (
    "ORDER BY CAST(c.collector_number AS INTEGER), c.collector_number COLLATE NOCASE"
)


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _mapping_row(row) -> dict:
    if isinstance(row, dict):
        return row
    return {key: row[key] for key in row.keys()}


def _serialize_manager_card(row) -> dict:
    data = _mapping_row(row)
    owned_nonfoil = (
        data["purchase_value_nonfoil"] is not None
        or int(data.get("instance_count_nonfoil") or 0) > 0
    )
    owned_foil = (
        data["purchase_value_foil"] is not None
        or int(data.get("instance_count_foil") or 0) > 0
    )
    owned_etched = (
        data["purchase_value_etched"] is not None
        or int(data.get("instance_count_etched") or 0) > 0
    )
    has_nonfoil = has_finish_flag(data, FINISH_NONFOIL)
    has_foil = has_finish_flag(data, FINISH_FOIL)
    has_etched = has_finish_flag(data, FINISH_ETCHED)

    return {
        "set_code": data["set_code"],
        "collector_number": str(data["collector_number"]),
        "name": deck_card_display_name(data),
        "art_style": str_or_empty(data["art_style"]),
        "image_uri": str_or_empty(data["image_uri"]),
        **card_metadata_snake(data),
        "market_value": _float_or_none(data["market_value"]),
        "market_value_foil": _float_or_none(data["market_value_foil"]),
        "market_value_etched": _float_or_none(data["market_value_etched"]),
        "has_nonfoil": has_nonfoil,
        "has_foil": has_foil,
        "has_etched": has_etched,
        "owned_nonfoil": owned_nonfoil,
        "owned_foil": owned_foil,
        "owned_etched": owned_etched,
        "purchase_value_nonfoil": _float_or_none(data["purchase_value_nonfoil"]),
        "purchase_value_foil": _float_or_none(data["purchase_value_foil"]),
        "purchase_value_etched": _float_or_none(data["purchase_value_etched"]),
    }


def _manager_filter_clauses(
    *,
    art_style: str = "",
    search: str = "",
    finish_filter: str = "all",
) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []

    if finish_filter == "foil":
        clauses.append("(c.has_foil = 1 OR p1.purchase_value IS NOT NULL)")
    elif finish_filter == "nonfoil":
        clauses.append("(c.has_nonfoil = 1 OR p0.purchase_value IS NOT NULL)")
    elif finish_filter == "etched":
        clauses.append("(c.has_etched = 1 OR p2.purchase_value IS NOT NULL)")

    if art_style:
        clauses.append("c.art_style = ?")
        params.append(art_style)

    term = search.strip().lower()
    if term:
        like = f"%{term}%"
        clauses.append(
            "("
            "LOWER(c.collector_number) LIKE ? "
            "OR LOWER(c.name) LIKE ? "
            "OR LOWER(COALESCE(c.art_style, '')) LIKE ?"
            ")"
        )
        params.extend([like, like, like])

    if not clauses:
        return "", params
    return " AND " + " AND ".join(clauses), params


def _execute_manager_query(
    conn: sqlite3.Connection,
    set_code: str,
    *,
    art_style: str = "",
    search: str = "",
    finish_filter: str = "all",
    offset: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    ensure_card_columns(conn)
    ensure_app_tables(conn)
    filter_sql, filter_params = _manager_filter_clauses(
        art_style=art_style,
        search=search,
        finish_filter=finish_filter,
    )
    sql = (
        f"{MANAGER_CARDS_SELECT}\n"
        f"{MANAGER_CARDS_FROM}\n"
        f"WHERE c.set_code = ?{filter_sql}\n"
        f"{MANAGER_CARDS_ORDER}"
    )
    params: list = [set_code.upper(), *filter_params]
    if limit is not None:
        sql += "\nLIMIT ? OFFSET ?"
        params.extend([limit, max(0, offset or 0)])

    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    return [_serialize_manager_card(row) for row in rows]


def count_manager_cards_for_set(
    conn: sqlite3.Connection,
    set_code: str,
    *,
    art_style: str = "",
    search: str = "",
    finish_filter: str = "all",
) -> int:
    ensure_card_columns(conn)
    ensure_app_tables(conn)
    filter_sql, filter_params = _manager_filter_clauses(
        art_style=art_style,
        search=search,
        finish_filter=finish_filter,
    )
    sql = (
        f"SELECT COUNT(*)\n"
        f"{MANAGER_CARDS_FROM}\n"
        f"WHERE c.set_code = ?{filter_sql}"
    )
    row = conn.execute(sql, [set_code.upper(), *filter_params]).fetchone()
    return int(row[0]) if row else 0


def query_manager_cards_for_set(
    conn: sqlite3.Connection,
    set_code: str,
    *,
    art_style: str = "",
    search: str = "",
    finish_filter: str = "all",
    offset: int = 0,
    limit: int | None = None,
) -> list[dict]:
    return _execute_manager_query(
        conn,
        set_code,
        art_style=art_style,
        search=search,
        finish_filter=finish_filter,
        offset=offset,
        limit=limit,
    )


def load_manager_cards_for_set(conn: sqlite3.Connection, set_code: str) -> list[dict]:
    return _execute_manager_query(conn, set_code)


# Build the client payload for collection manager pages.
def load_manager_client_payload() -> dict:
    sets = get_all_set_codes()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
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
