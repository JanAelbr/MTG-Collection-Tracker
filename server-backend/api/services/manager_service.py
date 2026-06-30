import sqlite3

from api.cache import bump_cache_epoch
from lib.config import EXCLUDED_SET_CODES, list_set_csv_files, purchase_csv_path
from lib.deck_csv import list_deck_sync_set_codes
from lib.deck_purchase import lookup_unit_market, upsert_purchase_value
from lib.card_locations import sync_card_instances
from report.manager_data import load_manager_cards_for_set
from util.card_metadata import card_metadata_api
from api.services import settings_service
from report.report_data import (
    build_art_style_options_for_set,
    build_sorted_set_options,
    format_set_option_label,
    get_set_display_names,
    load_owned_count_by_set,
)
from api.services.storage_service import StorageError, get_location
from util.card_finishes import normalize_finish
from util.scryfall_catalog_sync import import_set_catalog_from_scryfall

MANAGER_CARDS_PAGE_SIZE = 100
MAX_OWNED_COPIES = 3


class ManagerError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def list_sets(conn: sqlite3.Connection) -> list[dict]:
    favorite_sets = settings_service.get_favorite_sets(conn)
    settings = settings_service.get_settings(conn)
    return build_sorted_set_options(
        conn,
        favorite_sets=favorite_sets,
        sort_mode=settings["setSortMode"],
        include_all=False,
    )


def toggle_favorite_set(conn: sqlite3.Connection, set_code: str) -> dict:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)
    favorites = settings_service.get_favorite_sets(conn)
    if normalized in {code.upper() for code in favorites}:
        next_favorites = [code for code in favorites if code.upper() != normalized]
    else:
        next_favorites = [*favorites, normalized]
    saved = settings_service.save_favorite_sets(conn, next_favorites)
    sets = list_sets(conn)
    return {
        "setCode": normalized,
        "favorite": normalized in {code.upper() for code in saved},
        "favoriteSets": saved,
        "sets": sets,
        "defaultSet": sets[0]["setCode"] if sets else "",
    }


def list_art_styles(conn: sqlite3.Connection, set_code: str) -> list[dict]:
    _validate_set_code(set_code)
    return build_art_style_options_for_set(conn, set_code)


def list_set_cards(
    conn: sqlite3.Connection,
    set_code: str,
    *,
    art_style: str = "",
    search: str = "",
    finish_filter: str = "all",
    page: int = 1,
    page_size: int = MANAGER_CARDS_PAGE_SIZE,
) -> dict:
    _validate_set_code(set_code)
    cards = load_manager_cards_for_set(conn, set_code.upper())
    art_styles = build_art_style_options_for_set(conn, set_code)

    filtered = cards
    if finish_filter == "foil":
        filtered = [card for card in filtered if card.get("has_foil")]
    elif finish_filter == "nonfoil":
        filtered = [card for card in filtered if card.get("has_nonfoil")]
    elif finish_filter == "etched":
        filtered = [card for card in filtered if card.get("has_etched")]

    if art_style:
        filtered = [card for card in filtered if card["art_style"] == art_style]

    term = search.strip().lower()
    if term:
        filtered = [
            card
            for card in filtered
            if term in str(card["collector_number"]).lower()
            or term in str(card["name"]).lower()
            or term in str(card.get("art_style", "")).lower()
        ]

    total = len(filtered)
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 500))
    start = (safe_page - 1) * safe_page_size
    page_cards = filtered[start : start + safe_page_size]

    return {
        "setCode": set_code.upper(),
        "artStyles": art_styles,
        "cards": [_serialize_manager_card(card) for card in page_cards],
        "page": safe_page,
        "pageSize": safe_page_size,
        "total": total,
        "totalPages": max(1, (total + safe_page_size - 1) // safe_page_size) if total else 1,
    }


def set_ownership(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    owned: bool,
    purchase_value: float | None = None,
    resync: bool = True,
) -> dict:
    _validate_set_code(set_code)
    _apply_ownership(
        conn,
        set_code=set_code,
        collector_number=collector_number,
        finish=finish,
        owned=owned,
        purchase_value=purchase_value,
    )
    if resync:
        sync_card_instances(conn)
    bump_cache_epoch()
    return get_card_ownership(conn, set_code.upper(), collector_number)


def bulk_set_ownership(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    items: list[dict],
) -> dict:
    _validate_set_code(set_code)
    for item in items:
        _apply_ownership(
            conn,
            set_code=set_code,
            collector_number=item["collectorNumber"],
            finish=item.get("finish", item.get("foil", 0)),
            owned=bool(item["owned"]),
            purchase_value=item.get("purchaseValue"),
        )
    sync_card_instances(conn)
    bump_cache_epoch()
    return {"updated": len(items)}


def _normalized_print(
    set_code: str,
    collector_number: str,
    finish: int,
) -> tuple[str, str, int]:
    return set_code.upper(), str(collector_number).strip(), normalize_finish(finish)


def _instance_count(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
) -> int:
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    row = conn.execute(
        """
        SELECT COUNT(*) FROM card_instances
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (normalized_set, normalized_number, normalized_finish),
    ).fetchone()
    return int(row[0]) if row else 0


def _purchase_exists(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
) -> bool:
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    row = conn.execute(
        """
        SELECT 1 FROM purchases
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (normalized_set, normalized_number, normalized_finish),
    ).fetchone()
    return row is not None


def _insert_copy_instance(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    location_slug: str,
) -> None:
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    cursor = conn.cursor()
    purchase_value = lookup_unit_market(
        cursor,
        normalized_set,
        normalized_number,
        normalized_finish,
    )
    conn.execute(
        """
        INSERT INTO card_instances (
            set_code, collector_number, finish, location_slug, purchase_value
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            normalized_set,
            normalized_number,
            normalized_finish,
            location_slug,
            purchase_value,
        ),
    )


def _aggregate_locations(copies: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for copy in copies:
        slug = copy["locationSlug"]
        if slug not in grouped:
            grouped[slug] = {
                "slug": slug,
                "label": copy.get("label") or slug,
                "count": 0,
            }
        grouped[slug]["count"] += 1
    return sorted(grouped.values(), key=lambda item: item["label"])


def _load_copy_instances(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
) -> list[dict]:
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    rows = conn.execute(
        """
        SELECT ci.instance_id, ci.location_slug, sl.label
        FROM card_instances ci
        JOIN storage_locations sl ON sl.location_slug = ci.location_slug
        WHERE ci.set_code = ? AND ci.collector_number = ? AND ci.finish = ?
        ORDER BY ci.instance_id
        """,
        (normalized_set, normalized_number, normalized_finish),
    ).fetchall()
    return [
        {
            "instanceId": int(instance_id),
            "locationSlug": slug,
            "label": label,
        }
        for instance_id, slug, label in rows
    ]


def _ensure_materialized_copies(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
) -> None:
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    owned_count = get_owned_copy_count(conn, normalized_set, normalized_number, normalized_finish)
    if owned_count <= 0:
        return
    destination = settings_service.get_default_storage_location(conn)
    try:
        get_location(conn, destination)
    except StorageError as exc:
        raise ManagerError(exc.message, exc.status_code) from exc
    while _instance_count(conn, normalized_set, normalized_number, normalized_finish) < owned_count:
        _insert_copy_instance(
            conn,
            set_code=normalized_set,
            collector_number=normalized_number,
            finish=normalized_finish,
            location_slug=destination,
        )


def get_owned_copy_count(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
) -> int:
    instance_count = _instance_count(conn, set_code, collector_number, finish)
    if instance_count > 0:
        return instance_count
    if _purchase_exists(conn, set_code, collector_number, finish):
        return 1
    return 0


def get_copy_state(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    finish: int,
) -> dict:
    _validate_set_code(set_code)
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    _ensure_materialized_copies(conn, normalized_set, normalized_number, normalized_finish)
    copies = _load_copy_instances(conn, normalized_set, normalized_number, normalized_finish)
    locations = _aggregate_locations(copies)
    owned_count = len(copies)
    if owned_count == 0:
        owned_count = get_owned_copy_count(conn, normalized_set, normalized_number, normalized_finish)
    location_slug = copies[0]["locationSlug"] if len(copies) == 1 else None
    return {
        "setCode": normalized_set,
        "collectorNumber": normalized_number,
        "finish": normalized_finish,
        "ownedCount": owned_count,
        "maxCopies": MAX_OWNED_COPIES,
        "copies": copies,
        "locations": locations,
        "locationSlug": location_slug,
    }


def adjust_copy_count(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    delta: int,
    location_slug: str | None = None,
) -> dict:
    if delta not in (-1, 1):
        raise ManagerError("Copy adjustment must be -1 or 1")
    _validate_set_code(set_code)
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    current = get_owned_copy_count(conn, normalized_set, normalized_number, normalized_finish)

    if delta < 0:
        if current <= 0:
            raise ManagerError("No owned copies to remove")
        target = current - 1
        while _instance_count(conn, normalized_set, normalized_number, normalized_finish) > target:
            row = conn.execute(
                """
                SELECT instance_id
                FROM card_instances
                WHERE set_code = ? AND collector_number = ? AND finish = ?
                ORDER BY instance_id DESC
                LIMIT 1
                """,
                (normalized_set, normalized_number, normalized_finish),
            ).fetchone()
            if not row:
                break
            conn.execute("DELETE FROM card_instances WHERE instance_id = ?", (row[0],))
        if target == 0:
            _apply_ownership(
                conn,
                set_code=normalized_set,
                collector_number=normalized_number,
                finish=normalized_finish,
                owned=False,
            )
    else:
        if current >= MAX_OWNED_COPIES:
            raise ManagerError(f"At most {MAX_OWNED_COPIES} copies are allowed")
        destination = location_slug or settings_service.get_default_storage_location(conn)
        try:
            get_location(conn, destination)
        except StorageError as exc:
            raise ManagerError(exc.message, exc.status_code) from exc
        target = current + 1
        if current == 0:
            _apply_ownership(
                conn,
                set_code=normalized_set,
                collector_number=normalized_number,
                finish=normalized_finish,
                owned=True,
            )
        while _instance_count(conn, normalized_set, normalized_number, normalized_finish) < target:
            _insert_copy_instance(
                conn,
                set_code=normalized_set,
                collector_number=normalized_number,
                finish=normalized_finish,
                location_slug=destination,
            )

    bump_cache_epoch()
    return get_copy_state(conn, normalized_set, normalized_number, normalized_finish)


def update_copy_storage(
    conn: sqlite3.Connection,
    *,
    instance_id: int,
    location_slug: str,
) -> dict:
    get_location(conn, location_slug)
    row = conn.execute(
        """
        SELECT set_code, collector_number, finish
        FROM card_instances
        WHERE instance_id = ?
        """,
        (instance_id,),
    ).fetchone()
    if row is None:
        raise ManagerError("Copy not found", status_code=404)
    conn.execute(
        "UPDATE card_instances SET location_slug = ? WHERE instance_id = ?",
        (location_slug, instance_id),
    )
    bump_cache_epoch()
    return get_copy_state(conn, row["set_code"], row["collector_number"], row["finish"])


def _apply_ownership(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    owned: bool,
    purchase_value: float | None = None,
) -> None:
    normalized_set = set_code.upper()
    normalized_number = str(collector_number).strip()
    finish = normalize_finish(finish)
    cursor = conn.cursor()

    if owned:
        value = purchase_value
        if value is None:
            value = lookup_unit_market(cursor, normalized_set, normalized_number, finish)
        if value is None:
            value = 0.0
        upsert_purchase_value(
            cursor,
            normalized_set,
            normalized_number,
            finish,
            float(value),
            overwrite_zero_only=False,
        )
    else:
        conn.execute(
            """
            DELETE FROM purchases
            WHERE set_code = ?
              AND collector_number = ?
              AND finish = ?
            """,
            (normalized_set, normalized_number, finish),
        )


def bulk_assign_storage(
    conn: sqlite3.Connection,
    *,
    location_slug: str,
    items: list[dict],
) -> dict:
    get_location(conn, location_slug)
    moved = 0
    for item in items:
        cursor = conn.execute(
            """
            UPDATE card_instances
            SET location_slug = ?
            WHERE set_code = ?
              AND collector_number = ?
              AND finish = ?
            """,
            (
                location_slug,
                item["setCode"].upper(),
                str(item["collectorNumber"]).strip(),
                normalize_finish(item.get("finish", item.get("foil", 0))),
            ),
        )
        moved += cursor.rowcount
    bump_cache_epoch()
    return {"moved": moved, "locationSlug": location_slug}


def add_set(conn: sqlite3.Connection, set_code: str) -> dict:
    normalized = set_code.strip().upper()
    if not normalized:
        raise ManagerError("Set code is required")
    if normalized in EXCLUDED_SET_CODES:
        raise ManagerError(f"Set code {normalized} is not allowed")
    if not normalized.isalnum():
        raise ManagerError("Set code must be alphanumeric")

    csv_path = purchase_csv_path(normalized)
    if csv_path.exists():
        raise ManagerError(f"Set {normalized} already exists")

    csv_path.write_text("card_number,purchase_value,finish\n", encoding="utf-8")
    try:
        catalog_count = import_set_catalog_from_scryfall(conn, normalized)
    except ValueError as exc:
        csv_path.unlink(missing_ok=True)
        raise ManagerError(str(exc), status_code=404) from exc

    bump_cache_epoch()
    set_names = get_set_display_names(refresh=True)
    return {
        "setCode": normalized,
        "label": format_set_option_label(normalized, set_names),
        "csvPath": str(csv_path),
        "catalogCount": catalog_count,
    }


def remove_set(conn: sqlite3.Connection, set_code: str) -> dict:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)

    deck_codes = {code.upper() for code in list_deck_sync_set_codes()}
    if normalized in deck_codes:
        raise ManagerError("Cannot remove a set that is referenced by a deck")

    owned_counts = load_owned_count_by_set(conn)
    if owned_counts.get(normalized, 0) > 0:
        raise ManagerError("Cannot remove a set that has owned cards")

    csv_path = purchase_csv_path(normalized)
    if not csv_path.exists():
        raise ManagerError(f"Set {normalized} does not exist", status_code=404)

    csv_path.unlink()

    favorites = settings_service.get_favorite_sets(conn)
    if normalized in {code.upper() for code in favorites}:
        settings_service.save_favorite_sets(
            conn,
            [code for code in favorites if code.upper() != normalized],
        )

    bump_cache_epoch()
    get_set_display_names(refresh=True)
    return {"setCode": normalized, "removed": True}


def prune_orphan_catalogs(conn: sqlite3.Connection) -> dict:
    tracked = {path.stem.upper() for path in list_set_csv_files()}
    tracked |= {code.upper() for code in list_deck_sync_set_codes()}

    rows = conn.execute("SELECT DISTINCT set_code FROM cards").fetchall()
    orphan_codes = sorted(
        {
            str(row[0]).upper()
            for row in rows
            if row[0] and str(row[0]).upper() not in tracked
        }
    )

    deleted_cards = 0
    deleted_prices = 0
    has_prices = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_prices'"
    ).fetchone()
    for code in orphan_codes:
        deleted_cards += conn.execute(
            "DELETE FROM cards WHERE set_code = ?",
            (code,),
        ).rowcount
        if has_prices:
            deleted_prices += conn.execute(
                "DELETE FROM card_prices WHERE set_code = ?",
                (code,),
            ).rowcount
        conn.execute("DELETE FROM sets WHERE set_code = ?", (code,))

    if orphan_codes:
        bump_cache_epoch()
        get_set_display_names(refresh=True)

    return {
        "removedSets": orphan_codes,
        "deletedCards": deleted_cards,
        "deletedPrices": deleted_prices,
    }


def get_card_ownership(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
) -> dict:
    cards = load_manager_cards_for_set(conn, set_code)
    card = next(
        (item for item in cards if str(item["collector_number"]) == str(collector_number)),
        None,
    )
    if card is None:
        raise ManagerError("Card not found", status_code=404)
    return _serialize_manager_card(card)


def _serialize_manager_card(card: dict) -> dict:
    return {
        "setCode": card["set_code"],
        "collectorNumber": str(card["collector_number"]),
        "name": card["name"],
        "artStyle": card.get("art_style") or "",
        "imageUri": card.get("image_uri") or "",
        **card_metadata_api(card),
        "marketValue": card.get("market_value"),
        "marketValueFoil": card.get("market_value_foil"),
        "marketValueEtched": card.get("market_value_etched"),
        "hasNonfoil": bool(card.get("has_nonfoil")),
        "hasFoil": bool(card.get("has_foil")),
        "hasEtched": bool(card.get("has_etched")),
        "ownedNonfoil": bool(card.get("owned_nonfoil")),
        "ownedFoil": bool(card.get("owned_foil")),
        "ownedEtched": bool(card.get("owned_etched")),
        "purchaseValueNonfoil": card.get("purchase_value_nonfoil"),
        "purchaseValueFoil": card.get("purchase_value_foil"),
        "purchaseValueEtched": card.get("purchase_value_etched"),
    }


def _validate_set_code(set_code: str) -> None:
    normalized = set_code.strip().upper()
    if not normalized or normalized in EXCLUDED_SET_CODES:
        raise ManagerError("Invalid set code")
