import sqlite3

from lib.purchase_csv import parse_purchase_value


def explicit_purchase_from_row(row: dict) -> float | None:
    for key in ("purchase_value", "price", "purchase"):
        if key in row and row.get(key) not in (None, ""):
            return parse_purchase_value(row.get(key))
    return None


def deck_purchase_price_from_row(row: dict) -> float | None:
    for key in ("deck_purchase_price", "deck_price", "purchase_price"):
        if key in row and row.get(key) not in (None, ""):
            value = parse_purchase_value(row.get(key))
            return value if value > 0 else None
    return None


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


def allocate_deck_purchase_prices(
    lines: list[dict],
    total_price: float,
) -> list[float]:
    """Split a deck purchase price into per-line unit purchase prices."""
    if total_price <= 0 or not lines:
        return [0.0] * len(lines)

    weights = []
    for line in lines:
        unit_market = line.get("unit_market")
        qty = int(line["qty"])
        if unit_market is not None and unit_market > 0:
            weights.append(unit_market * qty)
        else:
            weights.append(float(qty))

    total_weight = sum(weights)
    if total_weight <= 0:
        return [0.0] * len(lines)

    unit_prices: list[float] = []
    for line, weight in zip(lines, weights):
        qty = int(line["qty"])
        line_total = total_price * (weight / total_weight)
        unit_prices.append(line_total / qty if qty else 0.0)
    return unit_prices


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
