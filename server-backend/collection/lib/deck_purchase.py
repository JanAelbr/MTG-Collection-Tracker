import sqlite3

# Market value is a reliable default purchase basis only for these sets.
MARKET_PURCHASE_DEFAULT_SETS = frozenset({"LTR", "LTC"})


def allows_market_purchase_default(set_code: str) -> bool:
    return str(set_code or "").strip().upper() in MARKET_PURCHASE_DEFAULT_SETS


def lookup_unit_market(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
    finish: int,
) -> float | None:
    try:
        row = cursor.execute(
            """
            SELECT market_value, market_value_foil, market_value_etched
            FROM cards
            WHERE set_code = ? AND collector_number = ?
            """,
            (set_code.upper(), str(collector_number).strip()),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    finish_id = int(finish)
    value = row[2] if finish_id == 2 else (row[1] if finish_id == 1 else row[0])
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def default_purchase_value(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
    finish: int,
) -> float:
    """Market default for LTR/LTC; otherwise 0 until set manually."""
    if not allows_market_purchase_default(set_code):
        return 0.0
    value = lookup_unit_market(cursor, set_code, collector_number, finish)
    return float(value) if value is not None else 0.0


def upsert_purchase_value(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
    finish: int,
    purchase_value: float,
    *,
    overwrite_zero_only: bool = True,
) -> bool:
    if overwrite_zero_only:
        cursor.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(set_code, collector_number, finish) DO UPDATE SET
                purchase_value = CASE
                    WHEN purchases.purchase_value = 0 THEN excluded.purchase_value
                    ELSE purchases.purchase_value
                END
            """,
            (set_code.upper(), str(collector_number).strip(), purchase_value, int(finish)),
        )
    else:
        cursor.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(set_code, collector_number, finish) DO UPDATE SET
                purchase_value = excluded.purchase_value
            """,
            (set_code.upper(), str(collector_number).strip(), purchase_value, int(finish)),
        )
    return cursor.rowcount > 0
