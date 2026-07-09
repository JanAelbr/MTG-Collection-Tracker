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
