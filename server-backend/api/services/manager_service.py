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
from lib.run_log import get_logger
from report.manager_data import (
    attach_locations_to_manager_cards,
    count_manager_cards_for_set,
    count_manager_price_issues_for_set,
    load_locations_for_set,
    load_manager_cards_for_set,
    query_manager_cards_for_set,
)
from util.card_metadata import card_metadata_api
from api.services import settings_service
from api.services.pricing_service import price_from_strategy, values_by_strategy_for_finish
from report.report_data import (
    build_art_style_options_for_set,
    build_sorted_set_options,
    format_set_option_label,
    get_set_display_names,
    load_owned_count_by_set,
    scryfall_set_icon_uri,
)
from api.services.storage_service import StorageError, assert_location_assignable, get_location
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
from util.set_catalog import fetch_all_scryfall_sets
from util.set_families import (
    relations_from_scryfall_sets,
    scryfall_family_members,
    scryfall_family_root,
)
from util.tracked_sets import (
    add_tracked_set,
    is_set_tracked,
    list_tracked_set_codes,
    remove_tracked_set,
)

MANAGER_CARDS_PAGE_SIZE = 100
MAX_OWNED_COPIES = 99
_MANAGER_SET_CACHE_TTL = 300
log = get_logger(__name__)


class ManagerError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def list_sets(conn: sqlite3.Connection) -> list[dict]:
    from util.set_family_sync import ensure_tracked_family_children_once

    ensure_tracked_family_children_once(conn)
    favorite_sets = settings_service.get_favorite_sets(conn)
    settings = settings_service.get_settings(conn)
    return build_sorted_set_options(
        conn,
        favorite_sets=favorite_sets,
        sort_mode=settings["setSortMode"],
        include_all=False,
    )


def list_available_sets(conn: sqlite3.Connection) -> list[dict]:
    tracked = {
        normalize_set_code(code)
        for code in list_tracked_set_codes(conn)
        if normalize_set_code(code)
    }
    scryfall_sets = fetch_all_scryfall_sets()
    relations = relations_from_scryfall_sets(scryfall_sets)
    by_code = {}
    for item in scryfall_sets:
        code = normalize_set_code(item.get("code"))
        if not code or code in EXCLUDED_SET_CODES or not code.isalnum():
            continue
        by_code[code] = item

    roots_seen: set[str] = set()
    available: list[dict] = []
    for code in sorted(by_code.keys()):
        root = scryfall_family_root(code, relations)
        if root in roots_seen:
            continue
        roots_seen.add(root)
        members = scryfall_family_members(root, relations=relations)
        members = [m for m in members if m in by_code]
        if not members:
            continue
        if any(member in tracked for member in members):
            continue
        root_item = by_code.get(root) or by_code[members[0]]
        root_code = normalize_set_code(root_item.get("code")) or members[0]
        from util.set_family_sync import AUTO_LOAD_CHILD_TYPES

        child_codes = [
            m for m in members
            if m != root_code
            and ((relations.get(m) or {}).get("set_type") in AUTO_LOAD_CHILD_TYPES)
        ]
        display_members = [root_code, *child_codes]
        name = root_item.get("name") or root_code
        if child_codes:
            name = f"{name} (+{', '.join(child_codes)})"
        available.append(
            {
                "setCode": root_code,
                "name": name,
                "releasedAt": str(root_item.get("released_at") or ""),
                "iconUri": root_item.get("icon_svg_uri") or scryfall_set_icon_uri(root_code),
                "setType": (str(root_item.get("set_type") or "").strip().lower() or None),
                "parentSetCode": None,
                "familyMembers": display_members,
            }
        )
    available.sort(key=lambda row: row["releasedAt"], reverse=True)
    return available


def _scryfall_family_for_code(set_code: str) -> list[str]:
    from util.set_families import relations_from_scryfall_sets, scryfall_family_members
    from util.set_family_sync import AUTO_LOAD_CHILD_TYPES

    normalized = normalize_set_code(set_code)
    if not normalized:
        return []
    scryfall_sets = fetch_all_scryfall_sets()
    relations = relations_from_scryfall_sets(scryfall_sets)
    members = scryfall_family_members(normalized, relations=relations)
    filtered: list[str] = []
    for code in members:
        if not code or code in EXCLUDED_SET_CODES or not code.isalnum():
            continue
        if code == members[0]:
            filtered.append(code)
            continue
        set_type = (relations.get(code) or {}).get("set_type") or ""
        if set_type in AUTO_LOAD_CHILD_TYPES:
            filtered.append(code)
    return filtered or [normalized]


def _import_tracked_set(conn: sqlite3.Connection, set_code: str) -> int:
    add_tracked_set(conn, set_code)
    try:
        return import_set_catalog_from_scryfall(conn, set_code)
    except ValueError:
        remove_tracked_set(conn, set_code)
        raise


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


def get_art_style_rules(conn: sqlite3.Connection, set_code: str) -> list[dict]:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)
    return load_art_style_rules(conn, normalized.lower())


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
        saved_rules = save_art_style_rules(conn, normalized, rules)
    except ValueError as exc:
        raise ManagerError(str(exc), status_code=400) from exc

    updated_cards = refresh_art_styles_for_set(conn, normalized)
    bump_cache_epoch()
    art_styles = build_art_style_options_for_set(conn, normalized)
    log.info(
        "Saved art style rules for %s (%s rule(s), %s card(s) updated)",
        normalized,
        len(saved_rules),
        updated_cards,
    )
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
    price_issues_only: bool = False,
    page: int = 1,
    page_size: int = MANAGER_CARDS_PAGE_SIZE,
) -> dict:
    _validate_set_code(set_code)
    normalized = set_code.upper()
    art_styles = build_art_style_options_for_set(conn, normalized)

    if price_issues_only:
        total = count_manager_price_issues_for_set(
            conn,
            normalized,
            art_style=art_style,
            search=search,
            finish_filter=finish_filter,
        )
    else:
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
        price_issues_only=price_issues_only,
        offset=start,
        limit=safe_page_size,
    )
    locations_by_print = load_locations_for_set(conn, normalized)
    attach_locations_to_manager_cards(page_cards, locations_by_print)

    return {
        "setCode": normalized,
        "artStyles": art_styles,
        "cards": [_serialize_manager_card(card) for card in page_cards],
        "page": safe_page,
        "pageSize": safe_page_size,
        "total": total,
        "totalPages": max(1, (total + safe_page_size - 1) // safe_page_size) if total else 1,
        "priceIssueCount": count_manager_price_issues_for_set(
            conn,
            normalized,
            art_style=art_style,
            search=search,
            finish_filter=finish_filter,
        ),
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
            market_value_etched,
            has_nonfoil,
            has_foil,
            has_etched
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
        has_nonfoil=card_row["has_nonfoil"],
        has_foil=card_row["has_foil"],
        has_etched=card_row["has_etched"],
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
            sl.location_type,
            sl.deck_id,
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
    for instance_id, finish, slug, label, location_type, deck_id, purchase_value in rows:
        finish_id = int(finish)
        finish_counts[finish_id] = finish_counts.get(finish_id, 0) + 1
        index_within_finish = finish_counts[finish_id]
        purchase = _float_or_none(purchase_value)
        current_value = _current_value_for_finish(card_row, finish_id, strategy)
        profit_loss = None
        if purchase is not None and current_value is not None:
            profit_loss = current_value - purchase
        location_type_value = str(location_type or "storage").lower()
        entry = {
            "instanceId": int(instance_id),
            "finish": finish_id,
            "finishLabel": finish_label(finish_id),
            "finishIndex": index_within_finish,
            "locationSlug": slug,
            "locationLabel": label,
            "locationType": location_type_value,
            "purchaseValue": purchase,
            "currentValue": current_value,
            "profitLoss": profit_loss,
        }
        if deck_id is not None:
            entry["deckId"] = int(deck_id)
        if location_type_value == "deck" or str(slug).lower().startswith("deck:"):
            entry["deckSlug"] = str(slug).split(":", 1)[-1] if ":" in str(slug) else str(slug)
        instances.append(entry)

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
        try:
            assert_location_assignable(conn, location_slug)
        except StorageError as exc:
            raise ManagerError(exc.message, status_code=exc.status_code) from exc
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
            assert_location_assignable(conn, destination)
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
            assert_location_assignable(conn, slug)
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
    try:
        assert_location_assignable(conn, location_slug)
    except StorageError as exc:
        raise ManagerError(exc.message, status_code=exc.status_code) from exc
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
    try:
        assert_location_assignable(conn, location_slug)
    except StorageError as exc:
        raise ManagerError(exc.message, status_code=exc.status_code) from exc
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

    family_codes = _scryfall_family_for_code(normalized)
    root = family_codes[0] if family_codes else normalized
    already = [code for code in family_codes if is_set_tracked(conn, code)]
    if already and len(already) == len(family_codes):
        raise ManagerError(f"Set {root} family already exists")

    added: list[str] = []
    catalog_total = 0
    try:
        for code in family_codes:
            if is_set_tracked(conn, code):
                continue
            catalog_total += _import_tracked_set(conn, code)
            added.append(code)
    except ValueError as exc:
        for code in reversed(added):
            remove_tracked_set(conn, code)
        raise ManagerError(str(exc), status_code=404) from exc

    if not added:
        raise ManagerError(f"Set {root} family already exists")

    conn.commit()
    bump_cache_epoch()
    set_names = get_set_display_names(refresh=True)
    log.info(
        "Added tracked family %s members=%s (%s catalog card(s))",
        root,
        ",".join(added),
        catalog_total,
    )
    return {
        "setCode": root,
        "label": format_set_option_label(root, set_names),
        "tracked": True,
        "catalogCount": catalog_total,
        "familyMembers": family_codes,
        "addedSetCodes": added,
    }


def reload_set_catalog(conn: sqlite3.Connection, set_code: str) -> dict:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)

    family_codes = _scryfall_family_for_code(normalized)
    tracked = {normalize_set_code(code) for code in list_tracked_set_codes(conn)}
    deck_codes = {code.upper() for code in list_deck_sync_set_codes(conn)}
    reload_codes = [
        code
        for code in family_codes
        if code in tracked
        or code in deck_codes
        or conn.execute(
            "SELECT COUNT(*) FROM cards WHERE set_code = ?",
            (code,),
        ).fetchone()[0]
    ]
    if not reload_codes:
        raise ManagerError(f"Set {normalized} is not tracked", status_code=404)

    catalog_total = 0
    try:
        for code in reload_codes:
            if not is_set_tracked(conn, code) and code in family_codes:
                add_tracked_set(conn, code)
            catalog_total += import_set_catalog_from_scryfall(conn, code)
        # Also import any Scryfall siblings not yet tracked when reloading a family root.
        for code in family_codes:
            if code in reload_codes:
                continue
            if not is_set_tracked(conn, code):
                catalog_total += _import_tracked_set(conn, code)
                reload_codes.append(code)
    except ValueError as exc:
        raise ManagerError(str(exc), status_code=404) from exc

    bump_cache_epoch()
    set_names = get_set_display_names(refresh=True)
    root = family_codes[0] if family_codes else normalized
    log.info(
        "Reloaded catalog for family %s members=%s (%s card(s))",
        root,
        ",".join(reload_codes),
        catalog_total,
    )
    return {
        "setCode": root,
        "label": format_set_option_label(root, set_names),
        "catalogCount": catalog_total,
        "familyMembers": reload_codes,
    }


def _delete_catalog_for_set(conn: sqlite3.Connection, set_code: str) -> bool:
    """Delete catalog rows for a set. Returns True if anything was removed."""
    code = normalize_set_code(set_code)
    if not code:
        return False
    deleted = False
    if conn.execute("DELETE FROM cards WHERE set_code = ?", (code,)).rowcount:
        deleted = True
    has_prices = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_prices'"
    ).fetchone()
    if has_prices and conn.execute(
        "DELETE FROM card_prices WHERE set_code = ?",
        (code,),
    ).rowcount:
        deleted = True
    if conn.execute("DELETE FROM sets WHERE set_code = ?", (code,)).rowcount:
        deleted = True
    return deleted


def remove_set(conn: sqlite3.Connection, set_code: str) -> dict:
    normalized = set_code.strip().upper()
    _validate_set_code(normalized)

    from util.set_families import resolve_set_codes_for_scope

    family_codes = resolve_set_codes_for_scope(conn, set_code=normalized, family=True)
    if not family_codes:
        family_codes = [normalized]

    deck_codes = {code.upper() for code in list_deck_sync_set_codes(conn)}
    blocked_deck = [code for code in family_codes if code in deck_codes]
    if blocked_deck:
        raise ManagerError(
            f"Cannot remove a set that is referenced by a deck ({', '.join(blocked_deck)})"
        )

    owned_counts = load_owned_count_by_set(conn)
    blocked_owned = [code for code in family_codes if owned_counts.get(code, 0) > 0]
    if blocked_owned:
        raise ManagerError(
            f"Cannot remove a set that has owned cards ({', '.join(blocked_owned)})"
        )

    removed: list[str] = []
    for code in family_codes:
        untracked = remove_tracked_set(conn, code)
        catalog_cleared = _delete_catalog_for_set(conn, code)
        if untracked or catalog_cleared:
            removed.append(code)
    if not removed:
        raise ManagerError(f"Set {normalized} does not exist", status_code=404)

    conn.commit()

    favorites = settings_service.get_favorite_sets(conn)
    removed_upper = {code.upper() for code in removed}
    if any(code.upper() in removed_upper for code in favorites):
        settings_service.save_favorite_sets(
            conn,
            [code for code in favorites if code.upper() not in removed_upper],
        )

    bump_cache_epoch()
    get_set_display_names(refresh=True)
    root = family_codes[0]
    log.info("Removed set family %s members=%s", root, ",".join(removed))
    return {"setCode": root, "removed": True, "removedSetCodes": removed}


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
        before_cards = conn.execute(
            "SELECT COUNT(*) FROM cards WHERE set_code = ?",
            (code,),
        ).fetchone()[0]
        before_prices = 0
        if has_prices:
            before_prices = conn.execute(
                "SELECT COUNT(*) FROM card_prices WHERE set_code = ?",
                (code,),
            ).fetchone()[0]
        _delete_catalog_for_set(conn, code)
        deleted_cards += before_cards
        deleted_prices += before_prices

    if orphan_codes:
        bump_cache_epoch()
        get_set_display_names(refresh=True)
        log.info(
            "Pruned %s orphan catalog set(s): deleted %s card(s), %s price row(s)",
            len(orphan_codes),
            deleted_cards,
            deleted_prices,
        )
    else:
        log.info("Prune orphan catalogs: nothing to remove")

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
        "imageUriBack": card.get("image_uri_back") or "",
        **card_metadata_api(card),
        "marketValue": card.get("market_value"),
        "marketValueFoil": card.get("market_value_foil"),
        "marketValueEtched": card.get("market_value_etched"),
        "valuesByFinish": {
            str(FINISH_NONFOIL): values_by_strategy_for_finish(card, FINISH_NONFOIL),
            str(FINISH_FOIL): values_by_strategy_for_finish(card, FINISH_FOIL),
            str(FINISH_ETCHED): values_by_strategy_for_finish(card, FINISH_ETCHED),
        },
        "hasNonfoil": bool(card.get("has_nonfoil")),
        "hasFoil": bool(card.get("has_foil")),
        "hasEtched": bool(card.get("has_etched")),
        "ownedNonfoil": bool(card.get("owned_nonfoil")),
        "ownedFoil": bool(card.get("owned_foil")),
        "ownedEtched": bool(card.get("owned_etched")),
        "ownedCountNonfoil": int(card.get("owned_count_nonfoil") or 0),
        "ownedCountFoil": int(card.get("owned_count_foil") or 0),
        "ownedCountEtched": int(card.get("owned_count_etched") or 0),
        "locationsNonfoil": card.get("locations_nonfoil") or [],
        "locationsFoil": card.get("locations_foil") or [],
        "locationsEtched": card.get("locations_etched") or [],
        "purchaseValueNonfoil": card.get("purchase_value_nonfoil"),
        "purchaseValueFoil": card.get("purchase_value_foil"),
        "purchaseValueEtched": card.get("purchase_value_etched"),
        "priceIssues": card.get("price_issues") or [],
    }


def _validate_set_code(set_code: str) -> None:
    normalized = normalize_set_code(set_code)
    if not normalized or normalized in EXCLUDED_SET_CODES:
        raise ManagerError("Invalid set code")
