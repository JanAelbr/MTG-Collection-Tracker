import sqlite3

from api.cache import bump_cache_epoch, get_cache_epoch, memory_cache
from lib.art_styles import (
    load_art_style_rules,
    refresh_art_styles_for_set,
    save_art_style_rules,
    validate_art_style_rules,
)
from lib.config import EXCLUDED_SET_CODES, normalize_set_code
from lib.deck_purchase import lookup_unit_market, upsert_purchase_value
from lib.card_locations import sync_card_instances
from report.manager_data import (
    count_manager_cards_for_set,
    load_manager_cards_for_set,
    query_manager_cards_for_set,
)
from util.card_metadata import card_metadata_api
from api.services import settings_service
from api.services.pricing_service import price_from_strategy
from report.report_data import (
    build_art_style_options_for_set,
    build_sorted_set_options,
    format_set_option_label,
    get_set_display_names,
    load_owned_count_by_set,
)
from api.services.storage_service import StorageError, get_location
from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    finish_label,
    has_finish_flag,
    normalize_finish,
)
from util.db_migrate import ensure_card_columns
from util.app_tables import ensure_app_tables
from util.deck_tables import list_deck_sync_set_codes
from util.scryfall_catalog_sync import import_set_catalog_from_scryfall
from util.tracked_sets import (
    add_tracked_set,
    is_set_tracked,
    list_tracked_set_codes,
    remove_tracked_set,
)

MANAGER_CARDS_PAGE_SIZE = 100
MAX_OWNED_COPIES = 99
_MANAGER_SET_CACHE_TTL = 300


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


def get_art_style_rules(set_code: str) -> list[dict]:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)
    return load_art_style_rules(normalized.lower())


def save_art_style_rules_for_set(
    conn: sqlite3.Connection,
    set_code: str,
    rules: list[dict],
) -> dict:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)

    errors = validate_art_style_rules(rules)
    if errors:
        raise ManagerError(errors[0], status_code=400)

    try:
        saved_rules = save_art_style_rules(normalized, rules)
    except ValueError as exc:
        raise ManagerError(str(exc), status_code=400) from exc

    updated_cards = refresh_art_styles_for_set(conn, normalized)
    bump_cache_epoch()
    art_styles = build_art_style_options_for_set(conn, normalized)
    return {
        "setCode": normalized,
        "rules": saved_rules,
        "artStyles": art_styles,
        "updatedCards": updated_cards,
    }


def _cached_manager_cards_for_set(
    conn: sqlite3.Connection,
    set_code: str,
) -> list[dict]:
    normalized = set_code.upper()
    epoch = get_cache_epoch()
    cache_key = memory_cache.make_key(
        "manager.set_cards.full",
        {"setCode": normalized},
        epoch,
    )
    cached = memory_cache.get(cache_key)
    if cached is not None:
        return cached
    cards = load_manager_cards_for_set(conn, normalized)
    memory_cache.set(cache_key, cards, _MANAGER_SET_CACHE_TTL)
    return cards


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
    normalized = set_code.upper()
    art_styles = build_art_style_options_for_set(conn, normalized)

    total = count_manager_cards_for_set(
        conn,
        normalized,
        art_style=art_style,
        search=search,
        finish_filter=finish_filter,
    )
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 500))
    start = (safe_page - 1) * safe_page_size
    page_cards = query_manager_cards_for_set(
        conn,
        normalized,
        art_style=art_style,
        search=search,
        finish_filter=finish_filter,
        offset=start,
        limit=safe_page_size,
    )

    return {
        "setCode": normalized,
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
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )
    was_owned = (
        get_owned_copy_count(conn, normalized_set, normalized_number, normalized_finish) > 0
    )
    _apply_ownership(
        conn,
        set_code=set_code,
        collector_number=collector_number,
        finish=finish,
        owned=owned,
        purchase_value=purchase_value,
    )
    price_only_update = owned and was_owned and purchase_value is not None
    if resync and not price_only_update:
        sync_card_instances(conn)
    bump_cache_epoch()
    return get_card_ownership(conn, set_code.upper(), collector_number)


def change_ownership_finish(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    from_finish: int,
    to_finish: int,
) -> dict:
    _validate_set_code(set_code)
    normalized_set, normalized_number, source_finish = _normalized_print(
        set_code,
        collector_number,
        from_finish,
    )
    _, _, target_finish = _normalized_print(
        set_code,
        collector_number,
        to_finish,
    )

    if source_finish == target_finish:
        raise ManagerError("Choose a different finish")

    if get_owned_copy_count(conn, normalized_set, normalized_number, source_finish) <= 0:
        raise ManagerError("Card is not owned in that finish")

    if get_owned_copy_count(conn, normalized_set, normalized_number, target_finish) > 0:
        raise ManagerError("Already owned in that finish")

    card_row = conn.execute(
        """
        SELECT has_nonfoil, has_foil, has_etched
        FROM cards
        WHERE set_code = ? AND collector_number = ?
        """,
        (normalized_set, normalized_number),
    ).fetchone()
    if card_row is None:
        raise ManagerError("Card not found", status_code=404)
    if not has_finish_flag(card_row, target_finish):
        raise ManagerError(f"Card is not available as {finish_label(target_finish)}")

    purchase_row = conn.execute(
        """
        SELECT purchase_value
        FROM purchases
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (normalized_set, normalized_number, source_finish),
    ).fetchone()
    purchase_value = float(purchase_row[0]) if purchase_row else None

    conn.execute(
        """
        UPDATE card_instances
        SET finish = ?
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (target_finish, normalized_set, normalized_number, source_finish),
    )

    conn.execute(
        """
        DELETE FROM purchases
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (normalized_set, normalized_number, source_finish),
    )

    cursor = conn.cursor()
    if purchase_value is None:
        purchase_value = lookup_unit_market(
            cursor,
            normalized_set,
            normalized_number,
            target_finish,
        )
    if purchase_value is None:
        purchase_value = 0.0
    upsert_purchase_value(
        cursor,
        normalized_set,
        normalized_number,
        target_finish,
        float(purchase_value),
        overwrite_zero_only=False,
    )

    bump_cache_epoch()
    return {
        "setCode": normalized_set,
        "collectorNumber": normalized_number,
        "fromFinish": source_finish,
        "toFinish": target_finish,
        **get_copy_state(conn, normalized_set, normalized_number, target_finish),
    }


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
        SELECT ci.instance_id, ci.location_slug, sl.label, ci.purchase_value
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
            "purchaseValue": _float_or_none(purchase_value),
            "finish": normalized_finish,
        }
        for instance_id, slug, label, purchase_value in rows
    ]


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _owned_finishes_for_print(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
) -> set[int]:
    normalized_set, normalized_number, _ = _normalized_print(set_code, collector_number, 0)
    finishes: set[int] = set()
    for row in conn.execute(
        """
        SELECT DISTINCT finish
        FROM purchases
        WHERE set_code = ? AND collector_number = ?
        """,
        (normalized_set, normalized_number),
    ):
        finishes.add(int(row[0]))
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
    ).fetchone()
    if table:
        for row in conn.execute(
            """
            SELECT DISTINCT finish
            FROM card_instances
            WHERE set_code = ? AND collector_number = ?
            """,
            (normalized_set, normalized_number),
        ):
            finishes.add(int(row[0]))
    return finishes


def _load_card_pricing_row(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
):
    ensure_card_columns(conn)
    return conn.execute(
        """
        SELECT
            cardmarket_url,
            cardmarket_url_foil,
            market_value,
            market_value_foil,
            market_value_etched
        FROM cards
        WHERE set_code = ? AND collector_number = ?
        """,
        (set_code.upper(), str(collector_number).strip()),
    ).fetchone()


def _current_value_for_finish(card_row, finish: int, strategy: str) -> float | None:
    if card_row is None:
        return None
    return price_from_strategy(
        card_row["cardmarket_url"],
        finish,
        strategy,
        cardmarket_url_foil=card_row["cardmarket_url_foil"],
        market_value=_float_or_none(card_row["market_value"]),
        market_value_foil=_float_or_none(card_row["market_value_foil"]),
        market_value_etched=_float_or_none(card_row["market_value_etched"]),
    )


def _sync_finish_purchase_aggregate(
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
    count = _instance_count(conn, normalized_set, normalized_number, normalized_finish)
    if count <= 0:
        _apply_ownership(
            conn,
            set_code=normalized_set,
            collector_number=normalized_number,
            finish=normalized_finish,
            owned=False,
        )
        return

    rows = conn.execute(
        """
        SELECT purchase_value
        FROM card_instances
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (normalized_set, normalized_number, normalized_finish),
    ).fetchall()
    positive = [
        float(row[0])
        for row in rows
        if row[0] is not None and float(row[0]) > 0
    ]
    cursor = conn.cursor()
    if positive:
        avg_value = sum(positive) / len(positive)
        upsert_purchase_value(
            cursor,
            normalized_set,
            normalized_number,
            normalized_finish,
            avg_value,
            overwrite_zero_only=False,
        )
        return

    upsert_purchase_value(
        cursor,
        normalized_set,
        normalized_number,
        normalized_finish,
        0.0,
        overwrite_zero_only=False,
    )


def _build_ownership_summary(
    instances: list[dict],
    *,
    card_row,
    strategy: str,
) -> list[dict]:
    grouped: dict[int, list[dict]] = {}
    for instance in instances:
        grouped.setdefault(int(instance["finish"]), []).append(instance)

    summary: list[dict] = []
    for finish_id in sorted(grouped):
        copies = grouped[finish_id]
        paid_values = [
            float(item["purchaseValue"])
            for item in copies
            if item.get("purchaseValue") is not None and float(item["purchaseValue"]) > 0
        ]
        if not paid_values:
            continue
        avg_purchase = sum(paid_values) / len(paid_values)
        current_value = _current_value_for_finish(card_row, finish_id, strategy)
        gain_loss = None
        if current_value is not None:
            gain_loss = (current_value - avg_purchase) * len(copies)
        summary.append({
            "finish": finish_id,
            "label": finish_label(finish_id),
            "count": len(copies),
            "avgPurchase": avg_purchase,
            "currentValue": current_value,
            "gainLoss": gain_loss,
        })
    return summary


def load_owned_instances_for_print(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    *,
    strategy: str | None = None,
) -> dict:
    _validate_set_code(set_code)
    ensure_app_tables(conn)
    normalized_set, normalized_number, _ = _normalized_print(set_code, collector_number, 0)
    if strategy is None:
        strategy = settings_service.get_settings(conn)["priceStrategy"]

    for finish_id in _owned_finishes_for_print(conn, normalized_set, normalized_number):
        _ensure_materialized_copies(conn, normalized_set, normalized_number, finish_id)

    card_row = _load_card_pricing_row(conn, normalized_set, normalized_number)
    rows = conn.execute(
        """
        SELECT
            ci.instance_id,
            ci.finish,
            ci.location_slug,
            sl.label,
            ci.purchase_value
        FROM card_instances ci
        JOIN storage_locations sl ON sl.location_slug = ci.location_slug
        WHERE ci.set_code = ? AND ci.collector_number = ?
        ORDER BY ci.finish, ci.instance_id
        """,
        (normalized_set, normalized_number),
    ).fetchall()

    finish_counts: dict[int, int] = {}
    instances: list[dict] = []
    for instance_id, finish, slug, label, purchase_value in rows:
        finish_id = int(finish)
        finish_counts[finish_id] = finish_counts.get(finish_id, 0) + 1
        index_within_finish = finish_counts[finish_id]
        purchase = _float_or_none(purchase_value)
        current_value = _current_value_for_finish(card_row, finish_id, strategy)
        profit_loss = None
        if purchase is not None and current_value is not None:
            profit_loss = current_value - purchase
        instances.append({
            "instanceId": int(instance_id),
            "finish": finish_id,
            "finishLabel": finish_label(finish_id),
            "finishIndex": index_within_finish,
            "locationSlug": slug,
            "locationLabel": label,
            "purchaseValue": purchase,
            "currentValue": current_value,
            "profitLoss": profit_loss,
        })

    return {
        "ownedInstances": instances,
        "ownershipSummary": _build_ownership_summary(
            instances,
            card_row=card_row,
            strategy=strategy,
        ),
    }


def update_copy_instance(
    conn: sqlite3.Connection,
    *,
    instance_id: int,
    purchase_value: float | None = None,
    finish: int | None = None,
    location_slug: str | None = None,
) -> dict:
    ensure_app_tables(conn)
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

    set_code = row["set_code"]
    collector_number = row["collector_number"]
    old_finish = int(row["finish"])
    new_finish = normalize_finish(finish) if finish is not None else old_finish

    if location_slug is not None:
        get_location(conn, location_slug)
        conn.execute(
            "UPDATE card_instances SET location_slug = ? WHERE instance_id = ?",
            (location_slug, instance_id),
        )

    if finish is not None and new_finish != old_finish:
        card_row = conn.execute(
            """
            SELECT has_nonfoil, has_foil, has_etched
            FROM cards
            WHERE set_code = ? AND collector_number = ?
            """,
            (set_code, collector_number),
        ).fetchone()
        if card_row is None:
            raise ManagerError("Card not found", status_code=404)
        if not has_finish_flag(card_row, new_finish):
            raise ManagerError(f"Card is not available as {finish_label(new_finish)}")
        conn.execute(
            "UPDATE card_instances SET finish = ? WHERE instance_id = ?",
            (new_finish, instance_id),
        )

    if purchase_value is not None:
        if purchase_value < 0:
            raise ManagerError("Purchase value must be zero or greater")
        conn.execute(
            "UPDATE card_instances SET purchase_value = ? WHERE instance_id = ?",
            (float(purchase_value), instance_id),
        )

    _sync_finish_purchase_aggregate(conn, set_code, collector_number, old_finish)
    if new_finish != old_finish:
        _sync_finish_purchase_aggregate(conn, set_code, collector_number, new_finish)

    bump_cache_epoch()
    strategy = settings_service.get_settings(conn)["priceStrategy"]
    return load_owned_instances_for_print(
        conn,
        set_code,
        collector_number,
        strategy=strategy,
    )


def delete_copy_instance(
    conn: sqlite3.Connection,
    *,
    instance_id: int,
) -> dict:
    ensure_app_tables(conn)
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

    set_code = row["set_code"]
    collector_number = row["collector_number"]
    finish = int(row["finish"])

    conn.execute("DELETE FROM card_instances WHERE instance_id = ?", (instance_id,))
    _sync_finish_purchase_aggregate(conn, set_code, collector_number, finish)
    bump_cache_epoch()
    strategy = settings_service.get_settings(conn)["priceStrategy"]
    return load_owned_instances_for_print(
        conn,
        set_code,
        collector_number,
        strategy=strategy,
    )


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
    ensure_app_tables(conn)
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
    _sync_finish_purchase_aggregate(
        conn,
        normalized_set,
        normalized_number,
        normalized_finish,
    )
    return get_copy_state(conn, normalized_set, normalized_number, normalized_finish)


def set_copy_allocations(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    allocations: list[dict],
) -> dict:
    ensure_app_tables(conn)
    _validate_set_code(set_code)
    normalized_set, normalized_number, normalized_finish = _normalized_print(
        set_code,
        collector_number,
        finish,
    )

    validated: list[tuple[str, int]] = []
    seen_slugs: set[str] = set()
    total = 0
    for item in allocations:
        slug = str(item.get("locationSlug") or "").strip()
        count = int(item.get("count") or 0)
        if count < 0:
            raise ManagerError("Count must be zero or greater", status_code=400)
        if count == 0:
            continue
        if not slug:
            raise ManagerError("Storage location is required", status_code=400)
        if slug in seen_slugs:
            raise ManagerError("Each storage location can only appear once", status_code=400)
        try:
            get_location(conn, slug)
        except StorageError as exc:
            raise ManagerError(exc.message, exc.status_code) from exc
        seen_slugs.add(slug)
        validated.append((slug, count))
        total += count

    if total > MAX_OWNED_COPIES:
        raise ManagerError(f"At most {MAX_OWNED_COPIES} copies are allowed", status_code=400)

    purchase_row = conn.execute(
        """
        SELECT purchase_value
        FROM purchases
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (normalized_set, normalized_number, normalized_finish),
    ).fetchone()

    conn.execute(
        """
        DELETE FROM card_instances
        WHERE set_code = ? AND collector_number = ? AND finish = ?
        """,
        (normalized_set, normalized_number, normalized_finish),
    )

    if total > 0:
        purchase_value = float(purchase_row[0]) if purchase_row else None
        _apply_ownership(
            conn,
            set_code=normalized_set,
            collector_number=normalized_number,
            finish=normalized_finish,
            owned=True,
            purchase_value=purchase_value,
        )
        for slug, count in validated:
            for _ in range(count):
                _insert_copy_instance(
                    conn,
                    set_code=normalized_set,
                    collector_number=normalized_number,
                    finish=normalized_finish,
                    location_slug=slug,
                )
    else:
        _apply_ownership(
            conn,
            set_code=normalized_set,
            collector_number=normalized_number,
            finish=normalized_finish,
            owned=False,
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
    normalized = normalize_set_code(set_code)
    if not normalized:
        raise ManagerError("Set code is required")
    if normalized in EXCLUDED_SET_CODES:
        raise ManagerError(f"Set code {normalized} is not allowed")
    if not normalized.isalnum():
        raise ManagerError("Set code must be alphanumeric")

    if is_set_tracked(conn, normalized):
        raise ManagerError(f"Set {normalized} already exists")

    add_tracked_set(conn, normalized)
    try:
        catalog_count = import_set_catalog_from_scryfall(conn, normalized)
    except ValueError as exc:
        remove_tracked_set(conn, normalized)
        raise ManagerError(str(exc), status_code=404) from exc

    conn.commit()
    bump_cache_epoch()
    set_names = get_set_display_names(refresh=True)
    return {
        "setCode": normalized,
        "label": format_set_option_label(normalized, set_names),
        "tracked": True,
        "catalogCount": catalog_count,
    }


def reload_set_catalog(conn: sqlite3.Connection, set_code: str) -> dict:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)

    tracked = is_set_tracked(conn, normalized)
    deck_codes = {code.upper() for code in list_deck_sync_set_codes(conn)}
    card_count = conn.execute(
        "SELECT COUNT(*) FROM cards WHERE set_code = ?",
        (normalized,),
    ).fetchone()[0]
    if not tracked and normalized not in deck_codes and card_count == 0:
        raise ManagerError(f"Set {normalized} is not tracked", status_code=404)

    try:
        catalog_count = import_set_catalog_from_scryfall(conn, normalized)
    except ValueError as exc:
        raise ManagerError(str(exc), status_code=404) from exc

    bump_cache_epoch()
    set_names = get_set_display_names(refresh=True)
    return {
        "setCode": normalized,
        "label": format_set_option_label(normalized, set_names),
        "catalogCount": catalog_count,
    }


def remove_set(conn: sqlite3.Connection, set_code: str) -> dict:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)

    deck_codes = {code.upper() for code in list_deck_sync_set_codes(conn)}
    if normalized in deck_codes:
        raise ManagerError("Cannot remove a set that is referenced by a deck")

    owned_counts = load_owned_count_by_set(conn)
    if owned_counts.get(normalized, 0) > 0:
        raise ManagerError("Cannot remove a set that has owned cards")

    if not remove_tracked_set(conn, normalized):
        raise ManagerError(f"Set {normalized} does not exist", status_code=404)

    conn.commit()

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
    tracked = {normalize_set_code(code) for code in list_tracked_set_codes(conn)}
    tracked |= {code.upper() for code in list_deck_sync_set_codes(conn)}

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
    cards = _cached_manager_cards_for_set(conn, set_code)
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
    normalized = normalize_set_code(set_code)
    if not normalized or normalized in EXCLUDED_SET_CODES:
        raise ManagerError("Invalid set code")
