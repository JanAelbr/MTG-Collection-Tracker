import sqlite3

from util.card_finishes import infer_finish_for_print, parse_finish_from_row
from util.alchemy_cards import exclude_alchemy_sql, is_alchemy_collector_number

# Official precon names that differ from catalog card names in tracked sets.
CARD_NAME_ALIASES = {
    "The Necropolis": "Vault 12: The Necropolis",
    "Forced Evolution": "Vault 87: Forced Evolution",
    "Looter Il-Kor": "Looter il-Kor",
    "An Offer You Can't Refuse": "An Offer You Can\u2019t Refuse",
}


def lookup_card_name(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
) -> str | None:
    row = cursor.execute(
        f"""
        SELECT name FROM cards
        WHERE set_code = ? AND collector_number = ?
          AND {exclude_alchemy_sql()}
        """,
        (set_code.upper(), collector_number),
    ).fetchone()
    return row[0] if row else None


def resolve_card_name(cursor: sqlite3.Cursor, card_name: str) -> tuple[str, str] | None:
    candidates = [card_name.strip()]
    alias = CARD_NAME_ALIASES.get(card_name.strip())
    if alias:
        candidates.append(alias)

    for candidate in candidates:
        rows = cursor.execute(
            f"""
            SELECT set_code, collector_number
            FROM cards
            WHERE name = ? COLLATE NOCASE
              AND {exclude_alchemy_sql()}
            ORDER BY set_code, CAST(collector_number AS INTEGER), collector_number
            """,
            (candidate,),
        ).fetchall()
        if rows:
            return rows[0]

    rows = cursor.execute(
        f"""
        SELECT set_code, collector_number
        FROM cards
        WHERE name LIKE ? ESCAPE '\\'
          AND {exclude_alchemy_sql()}
        ORDER BY set_code, CAST(collector_number AS INTEGER), collector_number
        """,
        (f"%{card_name.strip().replace('%', '\\%').replace('_', '\\_')}",),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    return None


def resolve_deck_row(cursor: sqlite3.Cursor, row: dict) -> dict:
    set_code = row.get("set_code")
    collector_number = row.get("collector_number")
    if set_code:
        set_code = str(set_code).upper()
    if collector_number:
        collector_number = str(collector_number).strip()

    finish = parse_finish_from_row(row)
    in_catalog = 0
    if set_code and collector_number and is_alchemy_collector_number(collector_number):
        set_code = None
        collector_number = None
    if set_code and collector_number:
        exists = cursor.execute(
            f"""
            SELECT has_nonfoil, has_foil, has_etched FROM cards
            WHERE set_code = ? AND collector_number = ?
              AND {exclude_alchemy_sql()}
            """,
            (set_code, collector_number),
        ).fetchone()
        if exists:
            finish = infer_finish_for_print(
                finish,
                has_nonfoil=exists[0],
                has_foil=exists[1],
                has_etched=exists[2],
            )
            in_catalog = 1

    card_name = row.get("card_name")
    if not set_code or not collector_number:
        if card_name:
            resolved = resolve_card_name(cursor, card_name)
            if resolved:
                set_code, collector_number = resolved
                flags = cursor.execute(
                    f"""
                    SELECT has_nonfoil, has_foil, has_etched FROM cards
                    WHERE set_code = ? AND collector_number = ?
                      AND {exclude_alchemy_sql()}
                    """,
                    (set_code, collector_number),
                ).fetchone()
                if flags:
                    finish = infer_finish_for_print(
                        finish,
                        has_nonfoil=flags[0],
                        has_foil=flags[1],
                        has_etched=flags[2],
                    )
                in_catalog = 1

    if not card_name and set_code and collector_number:
        card_name = lookup_card_name(cursor, set_code, collector_number)

    if not card_name and set_code and collector_number:
        card_name = f"{set_code} #{collector_number}"

    return {
        **row,
        "card_name": card_name or "Unknown",
        "set_code": set_code,
        "collector_number": collector_number,
        "finish": finish,
        "in_catalog": in_catalog,
    }


def _market_value_for_owned_finish(row, finish: int) -> float | None:
    if finish == 1:
        value = row["market_value_foil"]
        if value is None:
            value = row["market_value_etched"]
        return float(value) if value is not None else None
    if finish == 2:
        value = row["market_value_etched"]
        if value is None:
            value = row["market_value_foil"]
        return float(value) if value is not None else None
    value = row["market_value"]
    return float(value) if value is not None else None


def sync_deck_cards_in_catalog(
    conn: sqlite3.Connection,
    *,
    deck_id: int | None = None,
    set_codes: list[str] | None = None,
) -> int:
    query = """
        UPDATE deck_cards
        SET in_catalog = 1
        WHERE in_catalog = 0
          AND set_code IS NOT NULL
          AND collector_number IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM cards c
              WHERE c.set_code = deck_cards.set_code
                AND c.collector_number = deck_cards.collector_number
          )
    """
    params: list[object] = []
    if deck_id is not None:
        query += " AND deck_id = ?"
        params.append(deck_id)
    if set_codes:
        placeholders = ",".join("?" * len(set_codes))
        query += f" AND UPPER(set_code) IN ({placeholders})"
        params.extend(code.upper() for code in set_codes)
    cursor = conn.execute(query, params)
    return int(cursor.rowcount)


def cheapest_owned_printing_by_name(
    conn: sqlite3.Connection,
    card_name: str,
) -> dict | None:
    normalized = str(card_name or "").strip()
    if not normalized:
        return None
    rows = conn.execute(
        f"""
        SELECT
            c.set_code,
            c.collector_number,
            c.name,
            p.finish,
            c.market_value,
            c.market_value_foil,
            c.market_value_etched
        FROM purchases p
        JOIN cards c
          ON c.set_code = p.set_code
         AND c.collector_number = p.collector_number
        WHERE LOWER(TRIM(c.name)) = LOWER(TRIM(?))
          AND {exclude_alchemy_sql("c.collector_number")}
        """,
        (normalized,),
    ).fetchall()
    best = None
    best_value = None
    for row in rows:
        finish = int(row["finish"])
        value = _market_value_for_owned_finish(row, finish)
        if value is None:
            continue
        if best_value is None or value < best_value:
            best = {
                "set_code": row["set_code"],
                "collector_number": str(row["collector_number"]),
                "name": row["name"],
                "finish": finish,
                "current_value": value,
            }
            best_value = value
    return best
