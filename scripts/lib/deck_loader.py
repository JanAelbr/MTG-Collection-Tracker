import sqlite3
from datetime import date, datetime

from lib.config import DB_PATH
from lib.deck_csv import (
    CARD_NAME_ALIASES,
    find_deck_entry,
    load_deck_entries,
    read_deck_card_rows,
)
from lib.run_log import get_logger
from util.deck_tables import ensure_deck_tables
from util.card_finishes import infer_finish_for_print, parse_finish_from_row

log = get_logger(__name__)


# Look up a catalog card name from one print identity.
def lookup_card_name(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
) -> str | None:
    row = cursor.execute(
        """
        SELECT name FROM cards
        WHERE set_code = ? AND collector_number = ?
        """,
        (set_code.upper(), collector_number),
    ).fetchone()
    return row[0] if row else None


# Resolve one deck card name to a print in the tracked catalog.
def resolve_card_name(cursor: sqlite3.Cursor, card_name: str) -> tuple[str, str] | None:
    candidates = [card_name.strip()]
    alias = CARD_NAME_ALIASES.get(card_name.strip())
    if alias:
        candidates.append(alias)

    for candidate in candidates:
        rows = cursor.execute(
            """
            SELECT set_code, collector_number
            FROM cards
            WHERE name = ? COLLATE NOCASE
            ORDER BY set_code, CAST(collector_number AS INTEGER), collector_number
            """,
            (candidate,),
        ).fetchall()
        if rows:
            return rows[0]

    rows = cursor.execute(
        """
        SELECT set_code, collector_number
        FROM cards
        WHERE name LIKE ? ESCAPE '\\'
        ORDER BY set_code, CAST(collector_number AS INTEGER), collector_number
        """,
        (f"%{card_name.strip().replace('%', '\\%').replace('_', '\\_')}",),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    return None


# Resolve explicit or name-based print identity for one deck row.
def resolve_deck_row(cursor: sqlite3.Cursor, row: dict) -> dict:
    set_code = row.get("set_code")
    collector_number = row.get("collector_number")
    if set_code:
        set_code = str(set_code).upper()
    if collector_number:
        collector_number = str(collector_number).strip()

    finish = parse_finish_from_row(row)
    in_catalog = 0
    if set_code and collector_number:
        exists = cursor.execute(
            """
            SELECT has_nonfoil, has_foil, has_etched FROM cards
            WHERE set_code = ? AND collector_number = ?
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
                    """
                    SELECT has_nonfoil, has_foil, has_etched FROM cards
                    WHERE set_code = ? AND collector_number = ?
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


# Insert or replace one deck and its cards from a manifest entry.
def import_deck_file(cursor: sqlite3.Cursor, deck_entry) -> tuple[int, int, int]:
    deck_name = deck_entry.name
    deck_purchase_price = deck_entry.purchase_price
    rows = read_deck_card_rows(deck_entry.path)
    slug = deck_entry.slug
    now = datetime.now().isoformat(timespec="seconds")

    existing = cursor.execute(
        "SELECT deck_id FROM decks WHERE slug = ?",
        (slug,),
    ).fetchone()
    if existing:
        deck_id = existing[0]
        cursor.execute(
            "UPDATE decks SET name = ?, purchase_price = ?, updated_at = ? WHERE deck_id = ?",
            (deck_name, deck_purchase_price, now, deck_id),
        )
        cursor.execute("DELETE FROM deck_cards WHERE deck_id = ?", (deck_id,))
    else:
        cursor.execute(
            """
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (deck_name, slug, deck_purchase_price, now, now),
        )
        deck_id = cursor.lastrowid

    tracked = 0
    for row in rows:
        resolved = resolve_deck_row(cursor, row)
        if resolved["in_catalog"]:
            tracked += 1
        cursor.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish, qty, owned_qty,
                section, sort_order, in_catalog
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deck_id,
                resolved["card_name"],
                resolved["set_code"],
                resolved["collector_number"],
                resolved["finish"],
                resolved["qty"],
                resolved.get("owned_qty", min(resolved["qty"], 1)),
                resolved["section"],
                resolved["sort_order"],
                resolved["in_catalog"],
            ),
        )

    return deck_id, len(rows), tracked


# Import one registered deck from data/decks/decks.csv by slug, filename, or name.
def import_deck(deck_key: str) -> dict:
    deck_entry = find_deck_entry(deck_key)
    if deck_entry is None:
        raise ValueError(f"Deck not found in data/decks/decks.csv: {deck_key!r}")
    if not deck_entry.path.is_file():
        raise FileNotFoundError(f"Deck CSV not found: {deck_entry.path}")

    conn = sqlite3.connect(DB_PATH)
    ensure_deck_tables(conn)
    cursor = conn.cursor()
    deck_id, card_count, tracked_count = import_deck_file(cursor, deck_entry)
    conn.commit()
    conn.close()

    unmatched = card_count - tracked_count
    if unmatched:
        log.warning(
            "Deck '%s' (%s): %s cards, %s matched catalog, %s unmatched",
            deck_entry.slug,
            deck_id,
            card_count,
            tracked_count,
            unmatched,
        )
    else:
        log.info(
            "Deck '%s' (%s): %s cards, all matched catalog",
            deck_entry.slug,
            deck_id,
            card_count,
        )

    return {
        "deck_id": deck_id,
        "slug": deck_entry.slug,
        "name": deck_entry.name,
        "card_count": card_count,
        "tracked_count": tracked_count,
        "unmatched_count": unmatched,
    }


# Import all decks registered in data/decks/decks.csv.
def import_decks() -> None:
    deck_entries = load_deck_entries()
    if not deck_entries:
        log.warning("No decks registered in data/decks/decks.csv; skipping deck import")
        return

    log.info("Importing %s deck file(s) from data/decks/", len(deck_entries))
    conn = sqlite3.connect(DB_PATH)
    ensure_deck_tables(conn)
    cursor = conn.cursor()
    total_cards = 0
    total_tracked = 0

    for deck_entry in deck_entries:
        deck_id, card_count, tracked_count = import_deck_file(cursor, deck_entry)
        total_cards += card_count
        total_tracked += tracked_count
        unmatched = card_count - tracked_count
        if unmatched:
            log.warning(
                "Deck '%s' (%s): %s cards, %s matched catalog, %s unmatched",
                deck_entry.slug,
                deck_id,
                card_count,
                tracked_count,
                unmatched,
            )
        else:
            log.info(
                "Deck '%s' (%s): %s cards, all matched catalog",
                deck_entry.slug,
                deck_id,
                card_count,
            )

    conn.commit()
    conn.close()
    log.info(
        "Deck import complete: %s deck(s), %s cards, %s matched catalog",
        len(deck_entries),
        total_cards,
        total_tracked,
    )
