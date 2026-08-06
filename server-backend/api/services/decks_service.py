import sqlite3

from report.deck_queries import enrich_deck_cards_df, load_deck_cards_df, load_deck_list
from report.deck_stats_data import compute_deck_stats_page
from api.services import settings_service
from api.services.pricing_helpers import apply_strategy_to_deck_df
from lib.run_log import get_logger
from util.price_history import load_price_snapshot_cache

log = get_logger(__name__)


class DeckError(Exception):
    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _assert_card_matches_deck_color_identity(
    conn: sqlite3.Connection,
    *,
    deck_id: int,
    set_code: str,
    collector_number: str,
    card_name: str = "",
) -> None:
    """Reject maindeck adds outside the commander's color identity."""
    from util.commander_rules import card_is_legal_for_deck, commander_color_identity

    commander_rows = conn.execute(
        """
        SELECT
            COALESCE(c.name, dc.card_name) AS name,
            c.color_identity,
            c.colors,
            c.legalities
        FROM deck_cards dc
        LEFT JOIN cards c
          ON c.set_code = dc.set_code
         AND c.collector_number = dc.collector_number
        WHERE dc.deck_id = ? AND dc.section = 'commander'
        """,
        (deck_id,),
    ).fetchall()
    if not commander_rows:
        return

    commanders = [
        {
            "name": row["name"],
            "color_identity": row["color_identity"],
            "colors": row["colors"],
            "legalities": row["legalities"],
        }
        for row in commander_rows
    ]
    allowed = commander_color_identity(commanders)

    card_row = conn.execute(
        """
        SELECT name, color_identity, colors, legalities
        FROM cards
        WHERE set_code = ? AND collector_number = ?
        LIMIT 1
        """,
        (str(set_code).upper(), str(collector_number)),
    ).fetchone()
    if card_row is None:
        return

    card = {
        "name": card_row["name"] or card_name,
        "color_identity": card_row["color_identity"],
        "colors": card_row["colors"],
        "legalities": card_row["legalities"],
    }
    if card_is_legal_for_deck(card, allowed):
        return

    identity_label = "".join(allowed) if allowed else "colorless"
    raise DeckError(
        f"{card['name']} is outside the commander's color identity ({identity_label}).",
        status_code=400,
    )


def list_decks(conn: sqlite3.Connection) -> dict:

    return {"decks": load_deck_list(conn)}


def load_deck_memberships_for_print(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
) -> list[dict]:
    """Return every deck list row for this print (any finish/section)."""
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    normalized_set = str(set_code or "").strip().upper()
    normalized_number = str(collector_number or "").strip()
    if not normalized_set or not normalized_number:
        return []
    rows = conn.execute(
        """
        SELECT
            d.deck_id,
            d.name,
            d.slug,
            dc.deck_card_id,
            dc.finish,
            dc.qty,
            dc.owned_qty,
            dc.section
        FROM deck_cards dc
        JOIN decks d ON d.deck_id = dc.deck_id
        WHERE UPPER(dc.set_code) = ?
          AND dc.collector_number = ?
        ORDER BY d.name COLLATE NOCASE, dc.finish, dc.section, dc.deck_card_id
        """,
        (normalized_set, normalized_number),
    ).fetchall()
    memberships = []
    for row in rows:
        slug = str(row["slug"] or "").strip().lower()
        memberships.append({
            "deckId": int(row["deck_id"]),
            "deckName": row["name"],
            "deckSlug": slug,
            "locationSlug": f"deck:{slug}" if slug else "",
            "deckCardId": int(row["deck_card_id"]),
            "finish": int(row["finish"] or 0),
            "qty": int(row["qty"] or 0),
            "ownedQty": int(row["owned_qty"] or 0),
            "section": str(row["section"] or "main").strip().lower() or "main",
        })
    return memberships


def _slugify_deck_name(name: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "deck"


def _unique_deck_slug(conn: sqlite3.Connection, base_slug: str) -> str:
    slug = base_slug.lower()
    if not conn.execute("SELECT 1 FROM decks WHERE slug = ?", (slug,)).fetchone():
        return slug
    for index in range(2, 1000):
        candidate = f"{slug}-{index}"
        if not conn.execute("SELECT 1 FROM decks WHERE slug = ?", (candidate,)).fetchone():
            return candidate
    raise DeckError("Could not allocate deck slug", status_code=500)


def create_deck(
    conn: sqlite3.Connection,
    *,
    deck_format: str,
    name: str | None,
    commanders: list[dict],
) -> dict:
    from datetime import datetime, timezone

    from api.cache import bump_cache_epoch
    from util.deck_helpers import resolve_deck_row
    from util.card_finishes import normalize_finish
    from util.deck_tables import ensure_deck_tables
    from util.storage_tables import seed_storage_locations

    ensure_deck_tables(conn)
    format_name = (deck_format or "commander").strip().lower()
    if format_name not in {"commander"}:
        raise DeckError("Unsupported deck format", status_code=400)
    if format_name == "commander" and not commanders:
        raise DeckError("At least one commander is required", status_code=400)

    cursor = conn.cursor()
    resolved_commanders = []
    seen_prints = set()
    for commander in commanders:
        finish_id = normalize_finish(commander.get("finish", 0))
        print_key = (
            str(commander["set_code"]).upper(),
            str(commander["collector_number"]),
            finish_id,
        )
        if print_key in seen_prints:
            continue
        seen_prints.add(print_key)
        resolved = resolve_deck_row(
            cursor,
            {
                "set_code": commander["set_code"],
                "collector_number": commander["collector_number"],
                "finish": finish_id,
                "qty": 1,
                "section": "commander",
                "owned_qty": 0,
                "sort_order": len(resolved_commanders),
            },
        )
        if not resolved.get("set_code") or not resolved.get("collector_number"):
            raise DeckError("Commander print is required", status_code=400)
        resolved_commanders.append(resolved)

    if not resolved_commanders:
        raise DeckError("At least one commander is required", status_code=400)

    deck_name = (name or "").strip() or resolved_commanders[0]["card_name"]
    if not deck_name:
        raise DeckError("Deck name is required", status_code=400)
    if len(deck_name) > 120:
        raise DeckError("Deck name is too long", status_code=400)

    duplicate = conn.execute("SELECT 1 FROM decks WHERE name = ?", (deck_name,)).fetchone()
    if duplicate:
        raise DeckError("A deck with this name already exists", status_code=400)

    slug = _unique_deck_slug(conn, _slugify_deck_name(deck_name))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    insert_cursor = conn.execute(
        """
        INSERT INTO decks (name, slug, format, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (deck_name, slug, format_name, now, now),
    )
    deck_id = insert_cursor.lastrowid
    seed_storage_locations(conn)

    for resolved in resolved_commanders:
        conn.execute(
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
                1,
                0,
                "commander",
                resolved["sort_order"],
                resolved["in_catalog"],
            ),
        )

    conn.commit()
    bump_cache_epoch()
    log.info("Created deck %s (%r, format=%s)", deck_id, deck_name, format_name)

    decks = load_deck_list(conn)
    deck = next((item for item in decks if int(item["id"]) == int(deck_id)), None)
    return {
        "deck": deck,
        "commanders": [
            {
                "setCode": item["set_code"],
                "collectorNumber": item["collector_number"],
                "finish": item["finish"],
                "cardName": item["card_name"],
            }
            for item in resolved_commanders
        ],
    }





def _load_strategy_deck_df(
    conn: sqlite3.Connection,
    *,
    deck_id: str | int | None = None,
) -> tuple[str, object]:

    settings = settings_service.get_settings(conn)

    strategy = settings["priceStrategy"]

    deck_df = apply_strategy_to_deck_df(

        enrich_deck_cards_df(load_deck_cards_df(conn, deck_id=deck_id), conn),

        strategy,

    )

    return strategy, deck_df





def load_deck_stats(

    conn: sqlite3.Connection,

    *,

    deck_id: str = "All",

) -> dict:

    decks = load_deck_list(conn)

    if deck_id not in ("All", "all") and not any(str(d["id"]) == str(deck_id) for d in decks):

        raise DeckError("Deck not found")



    strategy, deck_df = _load_strategy_deck_df(conn)

    snapshot_cache = load_price_snapshot_cache(conn)

    stats = compute_deck_stats_page(

        deck_id,

        deck_df,

        conn,

        snapshot_cache=snapshot_cache,

        include_portfolio_history=False,

    )

    return {

        "deckId": deck_id,

        "priceStrategy": strategy,

        "decks": decks,

        "stats": _serialize_deck_stats(stats, conn),

    }





def load_deck_browse_index(conn: sqlite3.Connection) -> dict:

    strategy, deck_df = _load_strategy_deck_df(conn)

    decks = load_deck_list(conn)

    pages = {

        str(deck["id"]): _serialize_deck_stats(
            compute_deck_stats_page(

                str(deck["id"]),

                deck_df,

                conn,

                include_portfolio_history=False,

            ),
            conn,
            include_cards=False,
        )

        for deck in decks

    }

    return {

        "priceStrategy": strategy,

        "decks": decks,

        "pages": pages,

    }





def load_deck_browse(

    conn: sqlite3.Connection,

    *,

    deck_id: str,

) -> dict:

    decks = load_deck_list(conn)

    deck = next((item for item in decks if str(item["id"]) == str(deck_id)), None)

    if deck is None:

        raise DeckError("Deck not found")



    strategy, deck_df = _load_strategy_deck_df(conn, deck_id=deck_id)

    stats = compute_deck_stats_page(

        deck_id,

        deck_df,

        conn,

        include_portfolio_history=False,

    )

    return {

        "deckId": str(deck_id),

        "deck": deck,

        "decks": decks,

        "priceStrategy": strategy,

        "stats": _serialize_deck_stats(stats, conn),

    }





def add_card_to_deck(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    set_code: str,
    collector_number: str,
    finish: int,
    section: str = "main",
    qty: int = 1,
) -> dict:
    from api.cache import bump_cache_epoch
    from util.deck_helpers import resolve_deck_row
    from util.card_finishes import normalize_finish
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    finish_id = normalize_finish(finish)
    section_name = (section or "main").strip().lower()
    if section_name not in {"commander", "main", "sideboard"}:
        raise DeckError("Invalid section", status_code=400)

    add_qty = max(1, min(int(qty), 99))
    resolved = resolve_deck_row(
        conn.cursor(),
        {
            "set_code": set_code.upper(),
            "collector_number": str(collector_number),
            "finish": finish_id,
            "qty": add_qty,
            "section": section_name,
            "owned_qty": 0,
            "sort_order": 0,
        },
    )

    if not resolved.get("set_code") or not resolved.get("collector_number"):
        raise DeckError("Card print is required", status_code=400)

    if section_name == "main":
        _assert_card_matches_deck_color_identity(
            conn,
            deck_id=deck_row[0],
            set_code=resolved["set_code"],
            collector_number=resolved["collector_number"],
            card_name=resolved.get("card_name") or "",
        )

    owned_default = 0

    existing = conn.execute(
        """
        SELECT deck_card_id, qty, owned_qty
        FROM deck_cards
        WHERE deck_id = ? AND set_code = ? AND collector_number = ?
          AND finish = ? AND section = ?
        """,
        (
            deck_row[0],
            resolved["set_code"],
            resolved["collector_number"],
            resolved["finish"],
            section_name,
        ),
    ).fetchone()

    created = existing is None
    if existing:
        new_qty = int(existing[1]) + add_qty
        conn.execute(
            """
            UPDATE deck_cards
            SET qty = ?, card_name = ?, in_catalog = ?
            WHERE deck_card_id = ?
            """,
            (new_qty, resolved["card_name"], resolved["in_catalog"], existing[0]),
        )
        result_qty = new_qty
        result_owned = int(existing[2])
    else:
        sort_order_row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM deck_cards WHERE deck_id = ?",
            (deck_row[0],),
        ).fetchone()
        sort_order = int(sort_order_row[0]) if sort_order_row else 0
        conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish, qty, owned_qty,
                section, sort_order, in_catalog
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deck_row[0],
                resolved["card_name"],
                resolved["set_code"],
                resolved["collector_number"],
                resolved["finish"],
                add_qty,
                owned_default,
                section_name,
                sort_order,
                resolved["in_catalog"],
            ),
        )
        result_qty = add_qty
        result_owned = owned_default

    conn.commit()
    bump_cache_epoch()

    return {
        "deckId": str(deck_row[0]),
        "deckName": deck_row[1],
        "created": created,
        "qty": result_qty,
        "ownedQty": result_owned,
        "section": section_name,
        "card": {
            "setCode": resolved["set_code"],
            "collectorNumber": resolved["collector_number"],
            "finish": resolved["finish"],
            "cardName": resolved["card_name"],
            "inCatalog": bool(resolved["in_catalog"]),
        },
    }


def _move_instances_between_locations(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    from_location: str,
    to_location: str,
    count: int,
) -> int:
    if count <= 0:
        return 0
    rows = conn.execute(
        """
        SELECT instance_id
        FROM card_instances
        WHERE set_code = ? AND collector_number = ? AND finish = ?
          AND location_slug = ?
        ORDER BY instance_id DESC
        LIMIT ?
        """,
        (set_code, collector_number, finish, from_location, count),
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE card_instances SET location_slug = ? WHERE instance_id = ?",
            (to_location, row[0]),
        )
    return len(rows)


def _resolve_release_destination(
    conn: sqlite3.Connection,
    destination_slug: str | None,
) -> str:
    from api.services.storage_service import StorageError, assert_location_assignable, get_location

    destination = (destination_slug or "").strip() or settings_service.get_default_storage_location(
        conn
    )
    try:
        assert_location_assignable(conn, destination)
        get_location(conn, destination)
    except StorageError as exc:
        raise DeckError(exc.message, status_code=exc.status_code) from exc
    return destination


def _release_owned_copies_to_storage(
    conn: sqlite3.Connection,
    *,
    deck_slug: str,
    set_code: str,
    collector_number: str,
    finish: int,
    count: int,
    destination_slug: str | None = None,
) -> dict:
    from api.services.manager_service import _insert_copy_instance, _instance_count
    from util.app_tables import ensure_app_tables

    if count <= 0:
        return {"movedToStorage": 0, "storageLocation": ""}

    ensure_app_tables(conn)
    destination = _resolve_release_destination(conn, destination_slug)

    deck_location = f"deck:{str(deck_slug).lower()}"
    moved = _move_instances_between_locations(
        conn,
        set_code=set_code,
        collector_number=collector_number,
        finish=finish,
        from_location=deck_location,
        to_location=destination,
        count=count,
    )
    remaining = count - moved
    if remaining > 0:
        total_instances = _instance_count(conn, set_code, collector_number, finish)
        to_materialize = max(0, remaining - max(0, total_instances - moved))
        while to_materialize > 0:
            _insert_copy_instance(
                conn,
                set_code=set_code,
                collector_number=collector_number,
                finish=finish,
                location_slug=destination,
            )
            to_materialize -= 1
            moved += 1

    return {"movedToStorage": moved, "storageLocation": destination}


def _count_instances_at_location(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    location_slug: str,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM card_instances
        WHERE set_code = ? AND collector_number = ? AND finish = ?
          AND location_slug = ?
        """,
        (set_code, collector_number, finish, location_slug),
    ).fetchone()
    return int(row[0]) if row else 0


def _ensure_owned_copies_at_deck(
    conn: sqlite3.Connection,
    *,
    deck_slug: str,
    set_code: str,
    collector_number: str,
    finish: int,
    target_count: int,
) -> int:
    from api.services.manager_service import (
        MAX_OWNED_COPIES,
        _apply_ownership,
        _insert_copy_instance,
        _instance_count,
    )
    from api.services.storage_service import StorageError, get_location
    from util.app_tables import ensure_app_tables

    if target_count <= 0:
        return 0

    ensure_app_tables(conn)
    deck_location = f"deck:{str(deck_slug).lower()}"
    default_storage = settings_service.get_default_storage_location(conn)
    try:
        get_location(conn, default_storage)
    except StorageError as exc:
        raise DeckError(exc.message, status_code=exc.status_code) from exc

    purchase_row = conn.execute(
        """
        SELECT 1 FROM purchases
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (set_code, collector_number, finish),
    ).fetchone()
    if not purchase_row:
        _apply_ownership(
            conn,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            owned=True,
        )

    placed = 0
    while _count_instances_at_location(
        conn,
        set_code=set_code,
        collector_number=collector_number,
        finish=finish,
        location_slug=deck_location,
    ) < target_count:
        if _instance_count(conn, set_code, collector_number, finish) >= MAX_OWNED_COPIES:
            break

        moved = _move_instances_between_locations(
            conn,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            from_location=default_storage,
            to_location=deck_location,
            count=1,
        )
        if moved:
            placed += 1
            continue

        other = conn.execute(
            """
            SELECT instance_id
            FROM card_instances
            WHERE set_code = ? AND collector_number = ? AND finish = ?
              AND location_slug != ?
            ORDER BY instance_id DESC
            LIMIT 1
            """,
            (set_code, collector_number, finish, deck_location),
        ).fetchone()
        if other:
            conn.execute(
                "UPDATE card_instances SET location_slug = ? WHERE instance_id = ?",
                (deck_location, other[0]),
            )
            placed += 1
            continue

        _insert_copy_instance(
            conn,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            location_slug=deck_location,
        )
        placed += 1

    return placed


def _reconcile_deck_owned_storage(
    conn: sqlite3.Connection,
    *,
    deck_slug: str,
    set_code: str,
    collector_number: str,
    finish: int,
    owned_qty: int,
) -> dict:
    """Make card_instances at deck:{slug} match owned_qty for this print."""
    target = max(0, int(owned_qty))
    deck_location = f"deck:{str(deck_slug).lower()}"
    current = _count_instances_at_location(
        conn,
        set_code=set_code,
        collector_number=collector_number,
        finish=finish,
        location_slug=deck_location,
    )
    claimed = 0
    released = {"movedToStorage": 0, "storageLocation": ""}
    if current < target:
        claimed = _ensure_owned_copies_at_deck(
            conn,
            deck_slug=deck_slug,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            target_count=target,
        )
    elif current > target:
        released = _release_owned_copies_to_storage(
            conn,
            deck_slug=deck_slug,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            count=current - target,
        )
    return {
        "claimedToDeck": claimed,
        "movedToStorage": released["movedToStorage"],
        "storageLocation": released.get("storageLocation", ""),
    }


def reconcile_all_deck_owned_storage(conn: sqlite3.Connection) -> dict:
    """Align every deck-owned print's instances with owned_qty (incl. LOTR)."""
    from util.app_tables import ensure_app_tables
    from util.deck_tables import ensure_deck_tables

    ensure_app_tables(conn)
    ensure_deck_tables(conn)
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
    claimed = 0
    released = 0
    for slug, set_code, collector_number, finish, owned_qty in rows:
        result = _reconcile_deck_owned_storage(
            conn,
            deck_slug=str(slug).lower(),
            set_code=str(set_code).upper(),
            collector_number=str(collector_number).strip(),
            finish=int(finish or 0),
            owned_qty=int(owned_qty or 0),
        )
        claimed += int(result["claimedToDeck"] or 0)
        released += int(result["movedToStorage"] or 0)
    if claimed or released:
        conn.commit()
        from api.cache import bump_cache_epoch

        bump_cache_epoch()
        log.info(
            "Reconciled deck storage: claimed=%s released=%s across %s owned row(s)",
            claimed,
            released,
            len(rows),
        )
    return {
        "ownedRows": len(rows),
        "claimedToDeck": claimed,
        "movedToStorage": released,
    }


def set_deck_card_owned(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    set_code: str,
    collector_number: str,
    finish: int,
    section: str = "main",
    owned: bool,
) -> dict:
    from api.cache import bump_cache_epoch
    from util.card_finishes import normalize_finish
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name, slug FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    finish_id = normalize_finish(finish)
    section_name = (section or "main").strip().lower()
    if section_name not in {"commander", "main", "sideboard"}:
        raise DeckError("Invalid section", status_code=400)

    normalized_set = str(set_code).upper()
    normalized_number = str(collector_number).strip()
    if not normalized_set or not normalized_number:
        raise DeckError("Card print is required", status_code=400)

    existing = conn.execute(
        """
        SELECT deck_card_id, qty, owned_qty, card_name, in_catalog
        FROM deck_cards
        WHERE deck_id = ? AND set_code = ? AND collector_number = ?
          AND finish = ? AND section = ?
        """,
        (deck_key, normalized_set, normalized_number, finish_id, section_name),
    ).fetchone()
    if existing is None:
        raise DeckError("Card not in deck", status_code=404)

    current_qty = int(existing[1])
    new_owned = current_qty if owned else 0
    storage_result = _reconcile_deck_owned_storage(
        conn,
        deck_slug=deck_row[2],
        set_code=normalized_set,
        collector_number=normalized_number,
        finish=finish_id,
        owned_qty=new_owned,
    )

    conn.execute(
        "UPDATE deck_cards SET owned_qty = ? WHERE deck_card_id = ?",
        (new_owned, existing[0]),
    )
    conn.commit()
    bump_cache_epoch()

    return {
        "deckId": str(deck_row[0]),
        "deckName": deck_row[1],
        "removed": False,
        "qty": current_qty,
        "ownedQty": new_owned,
        "section": section_name,
        "claimedToDeck": storage_result["claimedToDeck"],
        "movedToStorage": storage_result["movedToStorage"],
        "storageLocation": storage_result["storageLocation"],
        "card": {
            "setCode": normalized_set,
            "collectorNumber": normalized_number,
            "finish": finish_id,
            "cardName": existing[3],
            "inCatalog": bool(existing[4]),
        },
    }


def remove_card_from_deck(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    set_code: str,
    collector_number: str,
    finish: int,
    section: str = "main",
    qty: int = 1,
) -> dict:
    from api.cache import bump_cache_epoch
    from util.card_finishes import normalize_finish
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name, slug FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    finish_id = normalize_finish(finish)
    section_name = (section or "main").strip().lower()
    if section_name not in {"commander", "main", "sideboard"}:
        raise DeckError("Invalid section", status_code=400)

    normalized_set = str(set_code).upper()
    normalized_number = str(collector_number).strip()
    remove_qty = max(1, min(int(qty), 99))

    existing = conn.execute(
        """
        SELECT deck_card_id, qty, owned_qty, card_name, in_catalog
        FROM deck_cards
        WHERE deck_id = ? AND set_code = ? AND collector_number = ?
          AND finish = ? AND section = ?
        """,
        (deck_key, normalized_set, normalized_number, finish_id, section_name),
    ).fetchone()
    if existing is None:
        raise DeckError("Card not in deck", status_code=404)

    current_qty = int(existing[1])
    current_owned = int(existing[2])
    if remove_qty > current_qty:
        raise DeckError("Cannot remove more copies than are in the deck", status_code=400)

    owned_to_release = 0
    unowned_in_deck = max(0, current_qty - current_owned)
    if remove_qty <= unowned_in_deck:
        owned_to_release = 0
    else:
        owned_to_release = min(current_owned, remove_qty - unowned_in_deck)
    storage_result = {"movedToStorage": 0, "storageLocation": ""}
    if owned_to_release > 0:
        storage_result = _release_owned_copies_to_storage(
            conn,
            deck_slug=deck_row[2],
            set_code=normalized_set,
            collector_number=normalized_number,
            finish=finish_id,
            count=owned_to_release,
        )

    new_qty = current_qty - remove_qty
    new_owned = current_owned - owned_to_release
    removed_completely = new_qty <= 0

    if removed_completely:
        conn.execute("DELETE FROM deck_cards WHERE deck_card_id = ?", (existing[0],))
        result_qty = 0
    else:
        conn.execute(
            """
            UPDATE deck_cards
            SET qty = ?, owned_qty = ?
            WHERE deck_card_id = ?
            """,
            (new_qty, new_owned, existing[0]),
        )
        result_qty = new_qty

    conn.commit()
    bump_cache_epoch()

    return {
        "deckId": str(deck_row[0]),
        "deckName": deck_row[1],
        "removed": removed_completely,
        "qty": result_qty,
        "ownedQty": new_owned if not removed_completely else 0,
        "section": section_name,
        "movedToStorage": storage_result["movedToStorage"],
        "storageLocation": storage_result["storageLocation"],
        "card": {
            "setCode": normalized_set,
            "collectorNumber": normalized_number,
            "finish": finish_id,
            "cardName": existing[3],
            "inCatalog": bool(existing[4]),
        },
    }


def _count_non_deck_instances(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM card_instances
        WHERE set_code = ? AND collector_number = ? AND finish = ?
          AND location_slug NOT LIKE 'deck:%'
        """,
        (set_code, collector_number, finish),
    ).fetchone()
    return int(row[0]) if row else 0


def _claim_one_non_deck_copy_to_deck(
    conn: sqlite3.Connection,
    *,
    deck_slug: str,
    set_code: str,
    collector_number: str,
    finish: int,
) -> int:
    """Move one non-deck instance into deck storage. Raises if none available."""
    from api.services.manager_service import _apply_ownership
    from util.app_tables import ensure_app_tables

    ensure_app_tables(conn)
    deck_location = f"deck:{str(deck_slug).lower()}"
    purchase_row = conn.execute(
        """
        SELECT 1 FROM purchases
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (set_code, collector_number, finish),
    ).fetchone()
    if not purchase_row:
        _apply_ownership(
            conn,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            owned=True,
        )

    row = conn.execute(
        """
        SELECT instance_id
        FROM card_instances
        WHERE set_code = ? AND collector_number = ? AND finish = ?
          AND location_slug NOT LIKE 'deck:%'
        ORDER BY
          CASE WHEN location_slug = ? THEN 0 ELSE 1 END,
          instance_id DESC
        LIMIT 1
        """,
        (
            set_code,
            collector_number,
            finish,
            settings_service.get_default_storage_location(conn),
        ),
    ).fetchone()
    if not row:
        raise DeckError(
            "No owned copy available in storage for the replacement card",
            status_code=400,
        )
    conn.execute(
        "UPDATE card_instances SET location_slug = ? WHERE instance_id = ?",
        (deck_location, row[0]),
    )
    return 1


def _remove_one_deck_card_inplace(
    conn: sqlite3.Connection,
    *,
    deck_id: int,
    deck_slug: str,
    set_code: str,
    collector_number: str,
    finish: int,
    section: str,
    qty: int,
    destination_slug: str | None,
) -> dict:
    """Remove qty from a deck row without committing. Returns remove result fields."""
    existing = conn.execute(
        """
        SELECT deck_card_id, qty, owned_qty, card_name, in_catalog
        FROM deck_cards
        WHERE deck_id = ? AND set_code = ? AND collector_number = ?
          AND finish = ? AND section = ?
        """,
        (deck_id, set_code, collector_number, finish, section),
    ).fetchone()
    if existing is None:
        raise DeckError("Card not in deck", status_code=404)

    current_qty = int(existing[1])
    current_owned = int(existing[2])
    remove_qty = max(1, min(int(qty), 99))
    if remove_qty > current_qty:
        raise DeckError("Cannot remove more copies than are in the deck", status_code=400)

    unowned_in_deck = max(0, current_qty - current_owned)
    if remove_qty <= unowned_in_deck:
        owned_to_release = 0
    else:
        owned_to_release = min(current_owned, remove_qty - unowned_in_deck)

    storage_result = {"movedToStorage": 0, "storageLocation": ""}
    if owned_to_release > 0:
        storage_result = _release_owned_copies_to_storage(
            conn,
            deck_slug=deck_slug,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            count=owned_to_release,
            destination_slug=destination_slug,
        )

    new_qty = current_qty - remove_qty
    new_owned = current_owned - owned_to_release
    removed_completely = new_qty <= 0
    if removed_completely:
        conn.execute("DELETE FROM deck_cards WHERE deck_card_id = ?", (existing[0],))
        result_qty = 0
        result_owned = 0
    else:
        conn.execute(
            """
            UPDATE deck_cards
            SET qty = ?, owned_qty = ?
            WHERE deck_card_id = ?
            """,
            (new_qty, new_owned, existing[0]),
        )
        result_qty = new_qty
        result_owned = new_owned

    return {
        "removed": removed_completely,
        "qty": result_qty,
        "ownedQty": result_owned,
        "section": section,
        "movedToStorage": storage_result["movedToStorage"],
        "storageLocation": storage_result.get("storageLocation", ""),
        "card": {
            "setCode": set_code,
            "collectorNumber": collector_number,
            "finish": finish,
            "cardName": existing[3],
            "inCatalog": bool(existing[4]),
        },
    }


def _add_owned_deck_card_inplace(
    conn: sqlite3.Connection,
    *,
    deck_id: int,
    deck_slug: str,
    deck_name: str,
    set_code: str,
    collector_number: str,
    finish: int,
    section: str,
    qty: int = 1,
) -> dict:
    """Add qty as owned to a deck section without committing."""
    from util.deck_helpers import resolve_deck_row

    add_qty = max(1, min(int(qty), 99))
    resolved = resolve_deck_row(
        conn.cursor(),
        {
            "set_code": set_code.upper(),
            "collector_number": str(collector_number),
            "finish": finish,
            "qty": add_qty,
            "section": section,
            "owned_qty": add_qty,
            "sort_order": 0,
        },
    )
    if not resolved.get("set_code") or not resolved.get("collector_number"):
        raise DeckError("Card print is required", status_code=400)

    if section == "main":
        _assert_card_matches_deck_color_identity(
            conn,
            deck_id=deck_id,
            set_code=resolved["set_code"],
            collector_number=resolved["collector_number"],
            card_name=resolved.get("card_name") or "",
        )

    if _count_non_deck_instances(
        conn,
        set_code=resolved["set_code"],
        collector_number=resolved["collector_number"],
        finish=resolved["finish"],
    ) < add_qty:
        raise DeckError(
            "No owned copy available in storage for the replacement card",
            status_code=400,
        )

    existing = conn.execute(
        """
        SELECT deck_card_id, qty, owned_qty
        FROM deck_cards
        WHERE deck_id = ? AND set_code = ? AND collector_number = ?
          AND finish = ? AND section = ?
        """,
        (
            deck_id,
            resolved["set_code"],
            resolved["collector_number"],
            resolved["finish"],
            section,
        ),
    ).fetchone()

    created = existing is None
    if existing:
        new_qty = int(existing[1]) + add_qty
        new_owned = int(existing[2]) + add_qty
        conn.execute(
            """
            UPDATE deck_cards
            SET qty = ?, owned_qty = ?, card_name = ?, in_catalog = ?
            WHERE deck_card_id = ?
            """,
            (
                new_qty,
                new_owned,
                resolved["card_name"],
                resolved["in_catalog"],
                existing[0],
            ),
        )
        result_qty = new_qty
        result_owned = new_owned
    else:
        sort_order_row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM deck_cards WHERE deck_id = ?",
            (deck_id,),
        ).fetchone()
        sort_order = int(sort_order_row[0]) if sort_order_row else 0
        conn.execute(
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
                add_qty,
                add_qty,
                section,
                sort_order,
                resolved["in_catalog"],
            ),
        )
        result_qty = add_qty
        result_owned = add_qty

    claimed = 0
    for _ in range(add_qty):
        claimed += _claim_one_non_deck_copy_to_deck(
            conn,
            deck_slug=deck_slug,
            set_code=resolved["set_code"],
            collector_number=resolved["collector_number"],
            finish=resolved["finish"],
        )

    return {
        "deckId": str(deck_id),
        "deckName": deck_name,
        "created": created,
        "qty": result_qty,
        "ownedQty": result_owned,
        "section": section,
        "claimedToDeck": claimed,
        "card": {
            "setCode": resolved["set_code"],
            "collectorNumber": resolved["collector_number"],
            "finish": resolved["finish"],
            "cardName": resolved["card_name"],
            "inCatalog": bool(resolved["in_catalog"]),
        },
    }


def swap_deck_card(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    remove_set_code: str,
    remove_collector_number: str,
    remove_finish: int,
    remove_section: str = "main",
    remove_qty: int = 1,
    add_set_code: str,
    add_collector_number: str,
    add_finish: int,
    destination_storage_location: str | None = None,
) -> dict:
    """Atomically swap one deck card for an owned non-deck replacement."""
    from api.cache import bump_cache_epoch
    from util.card_finishes import normalize_finish
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name, slug FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    section_name = (remove_section or "main").strip().lower()
    if section_name not in {"commander", "main", "sideboard"}:
        raise DeckError("Invalid section", status_code=400)

    rem_set = str(remove_set_code).upper()
    rem_num = str(remove_collector_number).strip()
    rem_finish = normalize_finish(remove_finish)
    add_set = str(add_set_code).upper()
    add_num = str(add_collector_number).strip()
    add_fin = normalize_finish(add_finish)
    qty = max(1, min(int(remove_qty), 99))

    if rem_set == add_set and rem_num == add_num and rem_finish == add_fin:
        raise DeckError("Cannot swap a card for the same printing", status_code=400)

    # Validate destination up front so a bad slug fails before mutating.
    _resolve_release_destination(conn, destination_storage_location)

    try:
        removed = _remove_one_deck_card_inplace(
            conn,
            deck_id=deck_row[0],
            deck_slug=deck_row[2],
            set_code=rem_set,
            collector_number=rem_num,
            finish=rem_finish,
            section=section_name,
            qty=qty,
            destination_slug=destination_storage_location,
        )
        added = _add_owned_deck_card_inplace(
            conn,
            deck_id=deck_row[0],
            deck_slug=deck_row[2],
            deck_name=deck_row[1],
            set_code=add_set,
            collector_number=add_num,
            finish=add_fin,
            section=section_name,
            qty=qty,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    bump_cache_epoch()

    return {
        "deckId": str(deck_row[0]),
        "deckName": deck_row[1],
        "section": section_name,
        "removed": removed,
        "added": added,
        "movedToStorage": removed["movedToStorage"],
        "storageLocation": removed["storageLocation"],
        "claimedToDeck": added["claimedToDeck"],
    }


def adjust_deck_card_qty(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    set_code: str,
    collector_number: str,
    finish: int,
    section: str = "main",
    delta: int = 0,
) -> dict:
    if delta not in (-1, 1):
        raise DeckError("Copy adjustment must be -1 or 1", status_code=400)
    if delta < 0:
        return remove_card_from_deck(
            conn,
            deck_id=deck_id,
            set_code=set_code,
            collector_number=collector_number,
            finish=finish,
            section=section,
            qty=1,
        )

    from api.cache import bump_cache_epoch
    from util.card_finishes import normalize_finish
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    finish_id = normalize_finish(finish)
    section_name = (section or "main").strip().lower()
    if section_name not in {"commander", "main", "sideboard"}:
        raise DeckError("Invalid section", status_code=400)

    normalized_set = str(set_code).upper()
    normalized_number = str(collector_number).strip()

    existing = conn.execute(
        """
        SELECT deck_card_id, qty, owned_qty, card_name, in_catalog
        FROM deck_cards
        WHERE deck_id = ? AND set_code = ? AND collector_number = ?
          AND finish = ? AND section = ?
        """,
        (deck_key, normalized_set, normalized_number, finish_id, section_name),
    ).fetchone()
    if existing is None:
        raise DeckError("Card not in deck", status_code=404)

    current_qty = int(existing[1])
    if current_qty >= 99:
        raise DeckError("At most 99 copies are allowed in a deck", status_code=400)

    new_qty = current_qty + 1
    conn.execute(
        "UPDATE deck_cards SET qty = ? WHERE deck_card_id = ?",
        (new_qty, existing[0]),
    )
    conn.commit()
    bump_cache_epoch()

    return {
        "deckId": str(deck_row[0]),
        "deckName": deck_row[1],
        "removed": False,
        "qty": new_qty,
        "ownedQty": int(existing[2]),
        "section": section_name,
        "movedToStorage": 0,
        "storageLocation": "",
        "card": {
            "setCode": normalized_set,
            "collectorNumber": normalized_number,
            "finish": finish_id,
            "cardName": existing[3],
            "inCatalog": bool(existing[4]),
        },
    }


def rename_deck(conn: sqlite3.Connection, *, deck_id: str, name: str) -> dict:
    from datetime import datetime, timezone

    from api.cache import bump_cache_epoch
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    cleaned = (name or "").strip()
    if not cleaned:
        raise DeckError("Deck name is required", status_code=400)
    if len(cleaned) > 120:
        raise DeckError("Deck name is too long", status_code=400)

    deck_row = conn.execute(
        "SELECT deck_id, name, slug FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    duplicate = conn.execute(
        "SELECT 1 FROM decks WHERE name = ? AND deck_id != ?",
        (cleaned, deck_key),
    ).fetchone()
    if duplicate:
        raise DeckError("A deck with this name already exists", status_code=400)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    slug = str(deck_row[2]).lower()

    conn.execute(
        "UPDATE decks SET name = ?, updated_at = ? WHERE deck_id = ?",
        (cleaned, now, deck_key),
    )
    conn.execute(
        """
        UPDATE storage_locations
        SET label = ?, description = ?
        WHERE location_slug = ?
        """,
        (cleaned, f"Cards stored with the {cleaned} deck", f"deck:{slug}"),
    )
    conn.commit()
    bump_cache_epoch()
    log.info("Renamed deck %s from %r to %r", deck_key, deck_row[1], cleaned)

    decks = load_deck_list(conn)
    deck = next((item for item in decks if item["id"] == deck_key), None)
    return {"deck": deck}


def delete_deck(conn: sqlite3.Connection, *, deck_id: str) -> dict:
    from api.cache import bump_cache_epoch
    from api.services.settings_service import get_default_storage_location
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, slug FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    deck_location = f"deck:{str(deck_row[1]).lower()}"
    default_location = get_default_storage_location(conn)
    conn.execute(
        """
        UPDATE card_instances
        SET location_slug = ?
        WHERE location_slug = ?
        """,
        (default_location, deck_location),
    )
    conn.execute("DELETE FROM deck_cards WHERE deck_id = ?", (deck_key,))
    conn.execute("DELETE FROM decks WHERE deck_id = ?", (deck_key,))
    conn.execute(
        "DELETE FROM storage_locations WHERE location_slug = ?",
        (deck_location,),
    )
    conn.commit()
    bump_cache_epoch()
    log.info("Deleted deck %s (slug=%s)", deck_key, deck_row[1])
    return {"deletedDeckId": str(deck_key)}


def _serialize_deck_card(card: dict, conn: sqlite3.Connection | None = None, *, include_alternatives: bool = True) -> dict:
    from util.card_role_seed import card_roles_for
    from util.deck_helpers import cheapest_owned_printing_by_name

    owned_qty = int(card.get("owned_qty") or 0)
    qty = int(card.get("qty") or 0)
    entry = {
        "deckId": card.get("deck_id"),
        "deckName": card.get("deck_name"),
        "cardName": card.get("card_name"),
        "setCode": card.get("set_code"),
        "collectorNumber": card.get("collector_number"),
        "finish": card.get("finish"),
        "foil": card.get("finish"),
        "qty": card.get("qty"),
        "section": card.get("section"),
        "ownedQty": card.get("owned_qty"),
        "currentValue": card.get("current_value"),
        "unitValue": card.get("unit_value"),
        "invested": card.get("invested"),
        "profitLoss": card.get("profit_loss"),
        "imageUri": card.get("image_uri"),
        "imageUriBack": card.get("image_uri_back") or "",
        "colors": card.get("colors") or [],
        "colorIdentity": card.get("color_identity") or card.get("colorIdentity") or [],
        "typeLine": card.get("type_line") or "",
        "cardType": card.get("card_type") or "",
        "cardTypes": card.get("card_types") or [],
        "manaCost": card.get("mana_cost") or "",
        "cmc": card.get("cmc"),
        "rarity": (str(card.get("rarity") or "").strip().lower() or None),
        "oracleText": card.get("oracle_text") or "",
        "isBasicLand": bool(card.get("is_basic_land")),
        "roles": card_roles_for(card),
        "cardmarketUrl": card.get("cardmarket_url"),
        "inCatalog": card.get("in_catalog"),
    }
    if include_alternatives and conn is not None and owned_qty < qty:
        alternative = cheapest_owned_printing_by_name(conn, card.get("card_name"))
        if alternative:
            entry["cheapestOwnedAlternative"] = {
                "setCode": alternative["set_code"],
                "collectorNumber": alternative["collector_number"],
                "finish": alternative["finish"],
                "currentValue": alternative["current_value"],
            }
    return entry


def _serialize_deck_preview_cards(stats: dict, *, limit: int = 2) -> list[dict]:
    preview = []
    for card in stats.get("cards") or []:
        if str(card.get("section") or "") != "commander":
            continue
        preview.append(_serialize_deck_card(card, include_alternatives=False))
        if len(preview) >= limit:
            break
    return preview


def _serialize_deck_stats(
    stats: dict,
    conn: sqlite3.Connection | None = None,
    *,
    include_cards: bool = True,
) -> dict:
    payload = {
        "current": stats.get("current"),
        "ownedCurrent": stats.get("ownedCurrent"),
        "invested": stats.get("invested"),
        "profit": stats.get("profit"),
        "purchasePrice": stats.get("purchasePrice"),
        "deckSize": stats.get("deckSize"),
        "trackedQty": stats.get("trackedQty"),
        "ownedQty": stats.get("ownedQty"),
        "missingQty": stats.get("missingQty"),
        "trackedCoverage": stats.get("trackedCoverage"),
        "ownedCoverage": stats.get("ownedCoverage"),
        "average": stats.get("average"),
        "unknownQty": stats.get("unknownQty"),
        "unknownCount": stats.get("unknownCount"),
        "unknownCards": stats.get("unknownCards") or [],
        "winners": stats.get("winners"),
        "losers": stats.get("losers"),
        "previewCards": _serialize_deck_preview_cards(stats),
    }
    if include_cards:
        payload["cards"] = [
            _serialize_deck_card(card, conn)
            for card in (stats.get("cards") or [])
        ]
    return payload


def bulk_add_cards_to_deck(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    cards: list[dict],
    replace_main: bool = False,
) -> dict:
    from api.cache import bump_cache_epoch
    from util.card_finishes import normalize_finish
    from util.deck_helpers import resolve_deck_row
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name, slug FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    deck_slug = str(deck_row[2]).lower()

    if replace_main:
        owned_rows = conn.execute(
            """
            SELECT set_code, collector_number, finish, owned_qty
            FROM deck_cards
            WHERE deck_id = ? AND section = 'main' AND owned_qty > 0
            """,
            (deck_key,),
        ).fetchall()
        for set_code, collector_number, finish, owned_qty in owned_rows:
            _reconcile_deck_owned_storage(
                conn,
                deck_slug=deck_slug,
                set_code=str(set_code).upper(),
                collector_number=str(collector_number).strip(),
                finish=int(finish or 0),
                owned_qty=0,
            )
        conn.execute(
            "DELETE FROM deck_cards WHERE deck_id = ? AND section = 'main'",
            (deck_key,),
        )

    cursor = conn.cursor()
    added = 0
    sort_order_row = cursor.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM deck_cards WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    sort_order = int(sort_order_row[0]) if sort_order_row else 0

    for card in cards:
        section = str(card.get("section") or "main").strip().lower()
        if section not in {"commander", "main", "sideboard"}:
            section = "main"
        owned_flag = card.get("owned")
        if owned_flag is None:
            owned_flag = card.get("suggested") is False

        resolved = resolve_deck_row(
            cursor,
            {
                "set_code": card.get("set_code") or card.get("setCode") or "",
                "collector_number": card.get("collector_number") or card.get("collectorNumber") or "",
                "card_name": card.get("card_name") or card.get("cardName") or card.get("name") or "",
                "finish": normalize_finish(card.get("finish") or 0),
                "qty": int(card.get("qty") or 1),
                "section": section,
                "owned_qty": 1 if owned_flag else 0,
                "sort_order": sort_order,
            },
        )
        if not resolved.get("card_name"):
            continue
        qty = max(1, min(int(card.get("qty") or 1), 99))
        owned_qty = min(qty, 1) if owned_flag else 0
        cursor.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish, qty, owned_qty,
                section, sort_order, in_catalog
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deck_key,
                resolved["card_name"],
                resolved.get("set_code") or "",
                resolved.get("collector_number") or "",
                resolved.get("finish") or 0,
                qty,
                owned_qty,
                section,
                sort_order,
                resolved.get("in_catalog") or 0,
            ),
        )
        if owned_qty > 0 and resolved.get("set_code") and resolved.get("collector_number"):
            _reconcile_deck_owned_storage(
                conn,
                deck_slug=deck_slug,
                set_code=str(resolved["set_code"]).upper(),
                collector_number=str(resolved["collector_number"]).strip(),
                finish=int(resolved.get("finish") or 0),
                owned_qty=owned_qty,
            )
        sort_order += 1
        added += 1

    conn.commit()
    bump_cache_epoch()
    return {
        "deckId": str(deck_key),
        "deckName": deck_row[1],
        "added": added,
        "replaceMain": replace_main,
    }


def preview_deck_csv_import(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    csv: str,
    mode: str = "merge",
    section: str = "main",
) -> dict:
    from util.deck_csv_import import build_csv_import_plan
    from util.deck_tables import ensure_deck_tables

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    plan = build_csv_import_plan(
        conn,
        deck_id=deck_key,
        csv=csv,
        mode=mode,
        section=section,
    )
    return {
        "deckId": str(deck_key),
        "deckName": deck_row[1],
        **plan,
    }


def apply_deck_csv_import(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    csv: str,
    mode: str = "merge",
    section: str = "main",
) -> dict:
    from api.cache import bump_cache_epoch
    from util.deck_csv_import import build_csv_import_plan
    from util.deck_tables import ensure_deck_tables

    preview = preview_deck_csv_import(
        conn,
        deck_id=deck_id,
        csv=csv,
        mode=mode,
        section=section,
    )
    if preview.get("errors"):
        raise DeckError("Fix CSV errors before applying", status_code=400)
    if not preview.get("changes"):
        raise DeckError("No deck changes to apply", status_code=400)

    ensure_deck_tables(conn)
    deck_key = int(deck_id)

    applied = {"add": 0, "update": 0, "remove": 0}

    for change in preview["changes"]:
        action = change["action"]
        set_code = change["setCode"]
        collector_number = change["collectorNumber"]
        finish = change["finish"]
        section_name = change["section"]
        current_qty = int(change["currentQty"])
        new_qty = int(change["newQty"])

        if action == "add":
            add_card_to_deck(
                conn,
                deck_id=deck_id,
                set_code=set_code,
                collector_number=collector_number,
                finish=finish,
                section=section_name,
                qty=new_qty,
            )
            applied["add"] += 1
            continue

        if action == "remove":
            remove_card_from_deck(
                conn,
                deck_id=deck_id,
                set_code=set_code,
                collector_number=collector_number,
                finish=finish,
                section=section_name,
                qty=current_qty,
            )
            applied["remove"] += 1
            continue

        delta = new_qty - current_qty
        if delta > 0:
            add_card_to_deck(
                conn,
                deck_id=deck_id,
                set_code=set_code,
                collector_number=collector_number,
                finish=finish,
                section=section_name,
                qty=delta,
            )
        elif delta < 0:
            remove_card_from_deck(
                conn,
                deck_id=deck_id,
                set_code=set_code,
                collector_number=collector_number,
                finish=finish,
                section=section_name,
                qty=-delta,
            )
        applied["update"] += 1

    bump_cache_epoch()
    log.info(
        "Applied CSV import to deck %s (%r): add=%s update=%s remove=%s mode=%s",
        deck_key,
        preview["deckName"],
        applied["add"],
        applied["update"],
        applied["remove"],
        preview["mode"],
    )
    return {
        "deckId": str(deck_key),
        "deckName": preview["deckName"],
        "mode": preview["mode"],
        "section": preview["section"],
        "applied": applied,
        "summary": preview["summary"],
    }


def refresh_deck_unpriced_metadata(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
) -> dict:
    from api.cache import bump_cache_epoch
    from lib.config import normalize_set_code
    from report.deck_queries import deck_scope
    from util.deck_tables import ensure_deck_tables
    from util.scryfall_catalog_sync import import_set_catalog_from_scryfall

    ensure_deck_tables(conn)
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id, name FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    _, deck_df = _load_strategy_deck_df(conn)
    scoped = deck_scope(deck_df, deck_key)
    unknown = scoped[scoped["current_value"].isna()] if not scoped.empty else scoped
    set_codes = sorted(
        {
            normalized
            for normalized in (
                normalize_set_code(str(code))
                for code in unknown["set_code"].dropna()
                if str(code).strip()
            )
            if normalized
        }
    )

    synced: list[dict] = []
    errors: list[dict] = []
    for set_code in set_codes:
        try:
            catalog_count = import_set_catalog_from_scryfall(conn, set_code)
            synced.append({"setCode": set_code, "catalogCount": catalog_count})
        except ValueError as exc:
            errors.append({"setCode": set_code, "message": str(exc)})
        except Exception as exc:
            errors.append({"setCode": set_code, "message": str(exc)})

    from util.deck_helpers import sync_deck_cards_in_catalog

    catalog_flags_updated = sync_deck_cards_in_catalog(
        conn,
        deck_id=deck_key,
        set_codes=set_codes or None,
    )

    conn.commit()
    bump_cache_epoch()

    if not set_codes:
        message = "No unpriced cards with set codes to refresh."
    elif synced and not errors:
        message = (
            f"Refreshed metadata for {len(synced)} set"
            f"{'' if len(synced) == 1 else 's'}."
        )
    elif synced:
        message = (
            f"Refreshed {len(synced)} set{'s' if len(synced) != 1 else ''}; "
            f"{len(errors)} failed."
        )
    else:
        message = f"Could not refresh metadata for {len(errors)} set{'s' if len(errors) != 1 else ''}."

    return {
        "deckId": str(deck_key),
        "deckName": deck_row[1],
        "setCodes": set_codes,
        "synced": synced,
        "errors": errors,
        "message": message,
    }


def load_deck_power(conn: sqlite3.Connection, deck_id: str) -> dict:
    from api.services.deck_power_service import assess_deck_power_by_id

    try:
        return assess_deck_power_by_id(conn, deck_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "Deck not found" else 500
        raise DeckError(message, status_code=status_code) from exc


def _deck_cards_for_builder(conn: sqlite3.Connection, deck_id: str) -> tuple[list[dict], list[dict]]:
    """Return (commanders, main_cards) for builder improve/rebuild."""
    from report.deck_queries import enrich_deck_cards_df, load_deck_cards_df

    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise DeckError("Deck not found", status_code=404) from exc

    deck_row = conn.execute(
        "SELECT deck_id FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    cards_df = enrich_deck_cards_df(load_deck_cards_df(conn, deck_id=deck_key), conn)
    commanders: list[dict] = []
    main_cards: list[dict] = []
    if cards_df is None or cards_df.empty:
        return commanders, main_cards

    for _, row in cards_df.iterrows():
        section = str(row.get("section") or "main").lower()
        payload = {
            "name": row.get("card_name") or row.get("name") or "",
            "cardName": row.get("card_name") or row.get("name") or "",
            "setCode": str(row.get("set_code") or "").upper(),
            "collectorNumber": str(row.get("collector_number") or ""),
            "finish": int(row.get("finish") or 0),
            "qty": int(row.get("qty") or 1),
            "owned": int(row.get("owned_qty") or 0) > 0,
            "section": section,
            "typeLine": row.get("type_line") or "",
            "oracleText": row.get("oracle_text") or "",
            "cardType": row.get("card_type") or "",
            "cmc": row.get("cmc"),
            "manaCost": row.get("mana_cost") or "",
            "rarity": (str(row.get("rarity") or "").strip().lower() or None),
            "isBasicLand": bool(row.get("is_basic_land")),
            "colorIdentity": row.get("color_identity"),
        }
        if section == "commander":
            commanders.append(payload)
        elif section == "main":
            main_cards.append(payload)
    return commanders, main_cards


def improve_existing_deck(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    location_slugs: list[str],
    include_deck_storage: bool = False,
    land_count: int = 38,
    budget_cap: float | None = None,
    exclude_categories: list[str] | None = None,
    slot_counts: dict[str, int] | None = None,
    preset: str | None = None,
    rebuild: bool = False,
) -> dict:
    from api.services.deck_generation_service import improve_deck_proposal

    commanders, main_cards = _deck_cards_for_builder(conn, deck_id)
    if not commanders:
        raise DeckError("Deck has no commander", status_code=400)

    proposal = improve_deck_proposal(
        conn,
        commanders=[
            {
                "setCode": card["setCode"],
                "collectorNumber": card["collectorNumber"],
                "finish": card["finish"],
            }
            for card in commanders
        ],
        existing_cards=main_cards,
        location_slugs=location_slugs,
        include_deck_storage=include_deck_storage,
        land_count=land_count,
        budget_cap=budget_cap,
        exclude_categories=exclude_categories,
        slot_counts=slot_counts,
        preset=preset,
        rebuild=rebuild,
    )
    proposal["deckId"] = str(deck_id)
    return proposal


def apply_deck_proposal(
    conn: sqlite3.Connection,
    *,
    deck_id: str,
    cards: list[dict],
    mode: str = "improve",
) -> dict:
    """Apply a builder proposal to an existing deck.

    rebuild → replace main
    improve → replace main with proposal list (keeps commander section)
    """
    main_cards = [
        {
            **card,
            "section": "main",
            "owned": bool(card.get("owned")) and not card.get("suggested"),
        }
        for card in cards
        if str(card.get("section") or "main").lower() == "main"
        and not card.get("infiniteBasic")
    ]
    # Infinite basics: keep as named cards without set when possible
    for card in cards:
        if card.get("infiniteBasic"):
            main_cards.append(
                {
                    "cardName": card.get("name"),
                    "name": card.get("name"),
                    "setCode": "",
                    "collectorNumber": "",
                    "finish": 0,
                    "qty": int(card.get("qty") or 1),
                    "section": "main",
                    "owned": False,
                }
            )
    result = bulk_add_cards_to_deck(
        conn,
        deck_id=deck_id,
        cards=main_cards,
        replace_main=True,
    )
    result["mode"] = mode
    return result

