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
    from lib.deck_loader import resolve_deck_row
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
        owned_row = conn.execute(
            """
            SELECT 1 FROM purchases
            WHERE set_code = ? AND collector_number = ? AND finish = ?
            """,
            (resolved["set_code"], resolved["collector_number"], resolved["finish"]),
        ).fetchone()
        owned_default = 1 if owned_row else 0
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
                owned_default,
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

        "stats": _serialize_deck_stats(stats),

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

            )

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

        "stats": _serialize_deck_stats(stats),

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
    from lib.deck_loader import resolve_deck_row
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

    owned_row = conn.execute(
        """
        SELECT 1 FROM purchases
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (resolved["set_code"], resolved["collector_number"], resolved["finish"]),
    ).fetchone()
    owned_default = min(add_qty, 1) if owned_row else 0

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


def _serialize_deck_stats(stats: dict) -> dict:

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

        "cards": [

            {

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

                "cardmarketUrl": card.get("cardmarket_url"),

                "inCatalog": card.get("in_catalog"),

            }

            for card in (stats.get("cards") or [])

        ],

    }


