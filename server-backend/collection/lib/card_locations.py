import sqlite3

from lib.run_log import get_logger
from util.app_tables import ensure_app_tables

log = get_logger(__name__)

LOTR_SETS = frozenset({"LTR", "LTC"})
LTR_BLACK_MAX = 398
LTR_BLUE_MIN = 399
LTR_BLUE_MAX = 833


def normalize_collector_number(collector_number: str) -> int | None:
    digits = "".join(char for char in str(collector_number) if char.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def binder_location_for_print(set_code: str, collector_number: str) -> str | None:
    set_upper = str(set_code).upper()
    if set_upper == "LTC":
        return "binder:ltc-green"
    if set_upper != "LTR":
        return None

    number = normalize_collector_number(collector_number)
    if number is None:
        return "binder:ltr-black"
    if number <= LTR_BLACK_MAX:
        return "binder:ltr-black"
    if LTR_BLUE_MIN <= number <= LTR_BLUE_MAX:
        return "binder:ltr-blue"
    return "binder:ltr-blue"


def deck_location_slug(deck_slug: str) -> str:
    return f"deck:{str(deck_slug).lower()}"


def _purchase_lookup(conn: sqlite3.Connection) -> dict[tuple[str, str, int], float | None]:
    rows = conn.execute(
        "SELECT set_code, collector_number, finish, purchase_value FROM purchases"
    ).fetchall()
    return {
        (str(set_code).upper(), str(collector_number).strip(), int(finish)): purchase_value
        for set_code, collector_number, finish, purchase_value in rows
    }


def _deck_owned_counts(conn: sqlite3.Connection) -> dict[tuple[str, str, int, str], int]:
    rows = conn.execute(
        """
        SELECT d.slug, dc.set_code, dc.collector_number, dc.finish, dc.owned_qty
        FROM deck_cards dc
        JOIN decks d ON d.deck_id = dc.deck_id
        WHERE dc.owned_qty > 0
          AND dc.set_code IS NOT NULL
          AND dc.collector_number IS NOT NULL
        """
    ).fetchall()
    counts: dict[tuple[str, str, int, str], int] = {}
    for slug, set_code, collector_number, finish, owned_qty in rows:
        key = (
            str(set_code).upper(),
            str(collector_number).strip(),
            int(finish or 0),
            str(slug).lower(),
        )
        counts[key] = counts.get(key, 0) + int(owned_qty)
    return counts


def _lotr_instance_count(
    print_key: tuple[str, str, int],
    deck_totals: dict[tuple[str, str, int], int],
    purchases: dict[tuple[str, str, int], float | None],
) -> int:
    owned_in_decks = deck_totals.get(print_key, 0)
    if owned_in_decks > 0:
        return owned_in_decks
    return 1 if print_key in purchases else 0


def _deck_totals_by_print(
    deck_counts: dict[tuple[str, str, int, str], int],
) -> dict[tuple[str, str, int], int]:
    totals: dict[tuple[str, str, int], int] = {}
    for (set_code, collector_number, finish, _slug), owned_qty in deck_counts.items():
        print_key = (set_code, collector_number, finish)
        totals[print_key] = totals.get(print_key, 0) + owned_qty
    return totals


def _insert_instances(
    cursor: sqlite3.Cursor,
    set_code: str,
    collector_number: str,
    finish: int,
    location_slug: str,
    count: int,
    purchase_value: float | None,
) -> int:
    inserted = 0
    for _ in range(max(count, 0)):
        cursor.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                set_code.upper(),
                str(collector_number).strip(),
                int(finish),
                location_slug,
                purchase_value,
            ),
        )
        inserted += 1
    return inserted


# Rebuild card_instances from purchases and deck ownership rules.
def sync_card_instances(conn: sqlite3.Connection) -> int:
    ensure_app_tables(conn)
    purchases = _purchase_lookup(conn)
    deck_counts = _deck_owned_counts(conn)
    deck_totals = _deck_totals_by_print(deck_counts)

    cursor = conn.cursor()
    cursor.execute("DELETE FROM card_instances")
    inserted = 0

    # Deck-owned copies (all sets, including LOTR) live at their deck location.
    for (set_code, collector_number, finish, deck_slug), owned_qty in sorted(deck_counts.items()):
        location_slug = deck_location_slug(deck_slug)
        exists = cursor.execute(
            "SELECT 1 FROM storage_locations WHERE location_slug = ?",
            (location_slug,),
        ).fetchone()
        if not exists:
            location_slug = "storage:general"
        purchase_value = purchases.get((set_code, collector_number, finish))
        inserted += _insert_instances(
            cursor,
            set_code,
            collector_number,
            finish,
            location_slug,
            owned_qty,
            purchase_value,
        )

    # Remaining LOTR owned copies (not claimed by a deck) stay in binders.
    lotr_prints: set[tuple[str, str, int]] = set()
    for print_key in set(purchases) | set(deck_totals):
        if print_key[0] in LOTR_SETS:
            lotr_prints.add(print_key)

    for set_code, collector_number, finish in sorted(lotr_prints):
        print_key = (set_code, collector_number, finish)
        desired = _lotr_instance_count(print_key, deck_totals, purchases)
        claimed = deck_totals.get(print_key, 0)
        binder_count = max(0, desired - claimed)
        if binder_count <= 0:
            continue
        location_slug = binder_location_for_print(set_code, collector_number)
        if not location_slug:
            continue
        purchase_value = purchases.get(print_key)
        inserted += _insert_instances(
            cursor,
            set_code,
            collector_number,
            finish,
            location_slug,
            binder_count,
            purchase_value,
        )

    for print_key, purchase_value in purchases.items():
        set_code, collector_number, finish = print_key
        if set_code in LOTR_SETS:
            continue
        if deck_totals.get(print_key, 0) > 0:
            continue
        inserted += _insert_instances(
            cursor,
            set_code,
            collector_number,
            finish,
            "storage:general",
            1,
            purchase_value,
        )

    log.info("Synced %s card instance row(s)", inserted)
    return inserted


def load_location_labels(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT location_slug, label FROM storage_locations ORDER BY sort_order, label"
    ).fetchall()
    return {slug: label for slug, label in rows}
