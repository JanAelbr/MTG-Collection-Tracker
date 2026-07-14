import sqlite3



from report.deck_queries import enrich_deck_cards_df, load_deck_cards_df, load_deck_list

from report.deck_stats_data import compute_deck_stats_page

from api.services import settings_service

from api.services.pricing_helpers import apply_strategy_to_deck_df

from util.price_history import load_price_snapshot_cache





class DeckError(Exception):

    def __init__(self, message: str, status_code: int = 404):

        super().__init__(message)

        self.message = message

        self.status_code = status_code





def list_decks(conn: sqlite3.Connection) -> dict:

    return {"decks": load_deck_list(conn)}


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





def _load_strategy_deck_df(conn: sqlite3.Connection) -> tuple[str, object]:

    settings = settings_service.get_settings(conn)

    strategy = settings["priceStrategy"]

    deck_df = apply_strategy_to_deck_df(

        enrich_deck_cards_df(load_deck_cards_df(conn), conn),

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



    strategy, deck_df = _load_strategy_deck_df(conn)

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


def _release_owned_copies_to_storage(
    conn: sqlite3.Connection,
    *,
    deck_slug: str,
    set_code: str,
    collector_number: str,
    finish: int,
    count: int,
) -> dict:
    from api.services.manager_service import _insert_copy_instance, _instance_count
    from api.services.storage_service import StorageError, get_location
    from util.app_tables import ensure_app_tables

    if count <= 0:
        return {"movedToStorage": 0, "storageLocation": ""}

    ensure_app_tables(conn)
    destination = settings_service.get_default_storage_location(conn)
    try:
        get_location(conn, destination)
    except StorageError as exc:
        raise DeckError(exc.message, status_code=exc.status_code) from exc

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
    current_owned = int(existing[2])
    storage_result = {"movedToStorage": 0, "storageLocation": ""}
    claimed = 0

    if owned:
        new_owned = current_qty
        if new_owned > current_owned:
            claimed = _ensure_owned_copies_at_deck(
                conn,
                deck_slug=deck_row[2],
                set_code=normalized_set,
                collector_number=normalized_number,
                finish=finish_id,
                target_count=new_owned,
            )
    else:
        new_owned = 0
        if current_owned > 0:
            storage_result = _release_owned_copies_to_storage(
                conn,
                deck_slug=deck_row[2],
                set_code=normalized_set,
                collector_number=normalized_number,
                finish=finish_id,
                count=current_owned,
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
        "claimedToDeck": claimed,
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
    return {"deletedDeckId": str(deck_key)}


def _serialize_deck_stats(stats: dict, conn: sqlite3.Connection | None = None) -> dict:
    from util.deck_helpers import cheapest_owned_printing_by_name

    serialized_cards = []
    for card in stats.get("cards") or []:
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
            "colors": card.get("colors") or [],
            "typeLine": card.get("type_line") or "",
            "cardType": card.get("card_type") or "",
            "cardTypes": card.get("card_types") or [],
            "manaCost": card.get("mana_cost") or "",
            "cmc": card.get("cmc"),
            "cardmarketUrl": card.get("cardmarket_url"),
            "inCatalog": card.get("in_catalog"),
        }
        if conn is not None and owned_qty < qty:
            alternative = cheapest_owned_printing_by_name(conn, card.get("card_name"))
            if alternative:
                entry["cheapestOwnedAlternative"] = {
                    "setCode": alternative["set_code"],
                    "collectorNumber": alternative["collector_number"],
                    "finish": alternative["finish"],
                    "currentValue": alternative["current_value"],
                }
        serialized_cards.append(entry)

    return {
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
        "cards": serialized_cards,
    }


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
        "SELECT deck_id, name FROM decks WHERE deck_id = ?",
        (deck_key,),
    ).fetchone()
    if deck_row is None:
        raise DeckError("Deck not found", status_code=404)

    if replace_main:
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

