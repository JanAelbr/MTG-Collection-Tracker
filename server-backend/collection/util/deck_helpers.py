import sqlite3

from lib.config import normalize_set_code
from lib.db import table_schema
from lib.run_log import get_logger
from util.card_finishes import infer_finish_for_print, parse_finish_from_row
from util.alchemy_cards import exclude_alchemy_sql, is_alchemy_collector_number

log = get_logger(__name__)

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


def _deck_cards_table_exists(conn: sqlite3.Connection) -> bool:
    """Real profile deck table; catalog connections only expose a TEMP ownership view."""
    return table_schema(conn, "deck_cards") == "main"


def _refreshed_set_codes(set_codes: list[str] | None) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for raw in set_codes or []:
        code = normalize_set_code(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _is_placeholder_deck_name(card_name: str | None, set_code: str, collector_number: str) -> bool:
    name = str(card_name or "").strip()
    if not name or name == "Unknown":
        return True
    expected = f"{set_code} #{collector_number}"
    return name.upper() == expected.upper()


def _embedded_set_print(collector_number: str | None) -> tuple[str, str] | None:
    text = str(collector_number or "").strip()
    if "-" not in text:
        return None
    prefix, suffix = text.split("-", 1)
    prefix = prefix.strip().upper()
    suffix = suffix.strip()
    if not suffix or not prefix.isalnum() or not 2 <= len(prefix) <= 8:
        return None
    return prefix, suffix


def _catalog_print(conn: sqlite3.Connection, set_code: str, collector_number: str):
    return conn.execute(
        f"""
        SELECT name, has_nonfoil, has_foil, has_etched
        FROM cards
        WHERE set_code = ? AND collector_number = ?
          AND {exclude_alchemy_sql()}
        """,
        (set_code, collector_number),
    ).fetchone()


def _refresh_matched_deck_cards(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        f"""
        SELECT dc.deck_card_id, dc.card_name, dc.set_code, dc.collector_number,
               dc.in_catalog, c.name
        FROM deck_cards dc
        JOIN cards c
          ON c.set_code = dc.set_code
         AND c.collector_number = dc.collector_number
        WHERE {exclude_alchemy_sql("c.collector_number")}
        """
    ).fetchall()
    updated_ids: set[int] = set()
    for deck_card_id, card_name, set_code, collector_number, in_catalog, catalog_name in rows:
        if deck_card_id in updated_ids:
            continue
        placeholder = _is_placeholder_deck_name(card_name, str(set_code), str(collector_number))
        if int(in_catalog or 0) == 1 and not placeholder:
            continue
        next_name = catalog_name if placeholder else card_name
        conn.execute(
            """
            UPDATE deck_cards
            SET card_name = ?, in_catalog = 1
            WHERE deck_card_id = ?
            """,
            (next_name, deck_card_id),
        )
        updated_ids.add(deck_card_id)
    return len(updated_ids)


def _unique_named_print(conn: sqlite3.Connection, card_name: str, set_codes: list[str]):
    placeholders = ",".join("?" * len(set_codes))
    rows = conn.execute(
        f"""
        SELECT set_code, collector_number, name, has_nonfoil, has_foil, has_etched
        FROM cards
        WHERE name = ? COLLATE NOCASE
          AND set_code IN ({placeholders})
          AND {exclude_alchemy_sql()}
        """,
        (card_name, *set_codes),
    ).fetchall()
    if len(rows) != 1:
        return None
    return rows[0]


def _retarget_source(conn: sqlite3.Connection, row, refreshed: set[str]):
    _deck_card_id, _deck_id, card_name, set_code, collector_number, _finish, _qty, _owned, _section = row
    set_code = str(set_code or "").upper()
    embedded = _embedded_set_print(collector_number)
    if embedded and (embedded[0] in refreshed or set_code in refreshed):
        catalog = _catalog_print(conn, embedded[0], embedded[1])
        if catalog is not None:
            return embedded[0], embedded[1], catalog
    if _is_placeholder_deck_name(card_name, set_code, str(collector_number or "")):
        return None
    if set_code and set_code not in refreshed:
        return None
    named = _unique_named_print(conn, str(card_name).strip(), sorted(refreshed))
    if named is None:
        return None
    flags = (named[2], named[3], named[4], named[5])
    return named[0], str(named[1]), flags


def _write_retargeted_deck_card(conn: sqlite3.Connection, row, target: tuple) -> None:
    deck_card_id, deck_id, _name, _set_code, _number, finish, qty, owned_qty, section = row
    target_set, target_number, catalog = target
    catalog_name, has_nonfoil, has_foil, has_etched = catalog[0], catalog[1], catalog[2], catalog[3]
    next_finish = infer_finish_for_print(
        int(finish or 0),
        has_nonfoil=has_nonfoil,
        has_foil=has_foil,
        has_etched=has_etched,
    )
    existing = conn.execute(
        """
        SELECT deck_card_id, qty, owned_qty
        FROM deck_cards
        WHERE deck_id = ? AND set_code = ? AND collector_number = ?
          AND finish = ? AND section = ? AND deck_card_id != ?
        """,
        (deck_id, target_set, target_number, next_finish, section, deck_card_id),
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            UPDATE deck_cards
            SET card_name = ?, set_code = ?, collector_number = ?, finish = ?, in_catalog = 1
            WHERE deck_card_id = ?
            """,
            (catalog_name, target_set, target_number, next_finish, deck_card_id),
        )
        return
    existing_id, existing_qty, existing_owned = existing
    merged_qty = int(existing_qty) + int(qty or 0)
    merged_owned = min(int(existing_owned or 0) + int(owned_qty or 0), merged_qty)
    conn.execute(
        """
        UPDATE deck_cards
        SET qty = ?, owned_qty = ?, card_name = ?, in_catalog = 1
        WHERE deck_card_id = ?
        """,
        (merged_qty, merged_owned, catalog_name, existing_id),
    )
    conn.execute("DELETE FROM deck_cards WHERE deck_card_id = ?", (deck_card_id,))


def _retarget_unlinked_deck_cards(conn: sqlite3.Connection, set_codes: list[str]) -> int:
    refreshed = set(set_codes)
    rows = conn.execute(
        f"""
        SELECT dc.deck_card_id, dc.deck_id, dc.card_name, dc.set_code, dc.collector_number,
               dc.finish, dc.qty, dc.owned_qty, dc.section
        FROM deck_cards dc
        WHERE NOT EXISTS (
            SELECT 1 FROM cards c
            WHERE c.set_code = dc.set_code
              AND c.collector_number = dc.collector_number
              AND {exclude_alchemy_sql("c.collector_number")}
        )
        """
    ).fetchall()
    updated = 0
    for row in rows:
        target = _retarget_source(conn, row, refreshed)
        if target is None:
            continue
        _write_retargeted_deck_card(conn, row, target)
        updated += 1
    return updated


def relink_unresolved_deck_cards(
    conn: sqlite3.Connection,
    set_codes: list[str] | None = None,
) -> int:
    """Fill deck prints that the catalog can now resolve after a set refresh."""
    if not _deck_cards_table_exists(conn):
        return 0
    codes = _refreshed_set_codes(set_codes)
    if not codes:
        return 0
    updated = _refresh_matched_deck_cards(conn)
    updated += _retarget_unlinked_deck_cards(conn, codes)
    if updated:
        log.info(
            "Relinked %s unresolved deck card(s) after refreshing %s",
            updated,
            ", ".join(codes),
        )
    return updated
