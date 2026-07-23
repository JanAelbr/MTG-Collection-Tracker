import sqlite3
import uuid

from api.cache import bump_cache_epoch
from api.services.pricing_service import price_from_strategy
from report.card_detail_data import collector_sort_key
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.card_metadata import card_image_fields, card_metadata_api
from util.db_migrate import ensure_card_columns

LOCATIONS_QUERY = """
SELECT
    sl.location_slug,
    sl.label,
    sl.location_type,
    sl.description,
    sl.sort_order,
    sl.is_system,
    COUNT(ci.instance_id) AS card_count,
    COUNT(DISTINCT ci.set_code || '|' || ci.collector_number || '|' || ci.finish) AS unique_prints
FROM storage_locations sl
LEFT JOIN card_instances ci ON ci.location_slug = sl.location_slug
GROUP BY sl.location_slug
ORDER BY sl.sort_order, sl.label
"""

LOCATION_CARDS_QUERY = """
SELECT
    ci.instance_id,
    ci.set_code,
    ci.collector_number,
    ci.finish,
    ci.purchase_value,
    c.name,
    c.art_style,
    c.image_uri,
    c.image_uri_back,
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.cardmarket_url,
    c.cardmarket_url_foil,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched,
    c.colors,
    c.type_line,
    c.card_type
FROM card_instances ci
LEFT JOIN cards c
    ON c.set_code = ci.set_code
    AND c.collector_number = ci.collector_number
WHERE ci.location_slug = ?
ORDER BY ci.set_code, ci.collector_number, ci.finish, ci.instance_id
"""


class StorageError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


DECK_STORAGE_MANUAL_MESSAGE = "Deck storage is set from deck ownership"


def assert_location_assignable(conn: sqlite3.Connection, slug: str) -> dict:
    """Return location if users may assign copies there; reject deck locations."""
    location = get_location(conn, slug)
    location_type = str(location.get("locationType") or "").lower()
    normalized_slug = str(slug or "").strip().lower()
    if location_type == "deck" or normalized_slug.startswith("deck:"):
        raise StorageError(DECK_STORAGE_MANUAL_MESSAGE, status_code=400)
    return location


def list_locations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(LOCATIONS_QUERY).fetchall()
    return [_serialize_location(row) for row in rows]


def get_location(conn: sqlite3.Connection, slug: str) -> dict:
    row = conn.execute(
        """
        SELECT
            sl.location_slug,
            sl.label,
            sl.location_type,
            sl.description,
            sl.sort_order,
            sl.is_system,
            COUNT(ci.instance_id) AS card_count,
            COUNT(DISTINCT ci.set_code || '|' || ci.collector_number || '|' || ci.finish) AS unique_prints
        FROM storage_locations sl
        LEFT JOIN card_instances ci ON ci.location_slug = sl.location_slug
        WHERE sl.location_slug = ?
        GROUP BY sl.location_slug
        """,
        (slug,),
    ).fetchone()
    if row is None:
        raise StorageError("Storage location not found", status_code=404)
    return _serialize_location(row)


def create_location(
    conn: sqlite3.Connection,
    *,
    label: str,
    description: str | None = None,
    location_type: str = "storage",
) -> dict:
    cleaned_label = label.strip()
    if not cleaned_label:
        raise StorageError("Label is required")
    if location_type not in {"storage", "binder"}:
        raise StorageError("locationType must be storage or binder")

    if location_type == "binder":
        slug = f"binder:custom:{uuid.uuid4().hex[:12]}"
        sort_order = _next_binder_sort_order(conn)
    else:
        slug = f"custom:{uuid.uuid4().hex[:12]}"
        sort_order = _next_custom_sort_order(conn)

    conn.execute(
        """
        INSERT INTO storage_locations (
            location_slug, label, location_type, sort_order,
            set_code, description, deck_id, is_system
        ) VALUES (?, ?, ?, ?, NULL, ?, NULL, 0)
        """,
        (slug, cleaned_label, location_type, sort_order, (description or "").strip() or None),
    )
    bump_cache_epoch()
    return get_location(conn, slug)


def update_location(
    conn: sqlite3.Connection,
    slug: str,
    *,
    label: str | None = None,
    description: str | None = None,
) -> dict:
    location = get_location(conn, slug)
    next_label = label.strip() if label is not None else location["label"]
    if not next_label:
        raise StorageError("Label is required")

    next_description = location["description"]
    if description is not None:
        next_description = description.strip()

    conn.execute(
        """
        UPDATE storage_locations
        SET label = ?, description = ?
        WHERE location_slug = ?
        """,
        (next_label, next_description or None, slug),
    )
    bump_cache_epoch()
    return get_location(conn, slug)


def delete_location(conn: sqlite3.Connection, slug: str) -> None:
    location = get_location(conn, slug)
    if location["isSystem"]:
        raise StorageError("System storage locations cannot be deleted")
    if location["cardCount"] > 0:
        raise StorageError("Only empty storage locations can be deleted")
    conn.execute(
        "DELETE FROM storage_locations WHERE location_slug = ?",
        (slug,),
    )
    bump_cache_epoch()


def list_location_cards(
    conn: sqlite3.Connection,
    slug: str,
    *,
    price_strategy: str,
) -> dict:
    ensure_card_columns(conn)
    get_location(conn, slug)
    rows = conn.execute(LOCATION_CARDS_QUERY, (slug,)).fetchall()
    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = (row["set_code"], str(row["collector_number"]), int(row["finish"]))
        card = grouped.get(key)
        if card is None:
            finish = int(row["finish"])
            card = {
                "setCode": row["set_code"],
                "collectorNumber": str(row["collector_number"]),
                "finish": finish,
                "foil": finish,
                "copyCount": 0,
                "instanceIds": [],
                "purchaseValue": _float_or_none(row["purchase_value"]),
                "name": deck_card_display_name({
                    "catalog_name": row["name"],
                    "card_name": row["name"],
                    "set_code": row["set_code"],
                    "collector_number": row["collector_number"],
                }),
                "artStyle": str_or_empty(row["art_style"]),
                **card_image_fields(row),
                "currentValue": price_from_strategy(
                    row["cardmarket_url"],
                    finish,
                    price_strategy,
                    cardmarket_url_foil=row["cardmarket_url_foil"],
                    market_value=_float_or_none(row["market_value"]),
                    market_value_foil=_float_or_none(row["market_value_foil"]),
                    market_value_etched=_float_or_none(row["market_value_etched"]),
                    has_nonfoil=row["has_nonfoil"],
                    has_foil=row["has_foil"],
                    has_etched=row["has_etched"],
                ),
            }
            grouped[key] = card
        card["copyCount"] += 1
        card["instanceIds"].append(int(row["instance_id"]))

    cards = sorted(
        grouped.values(),
        key=lambda card: (
            card["setCode"],
            collector_sort_key(card["collectorNumber"]),
            card["finish"],
        ),
    )
    return {
        "location": get_location(conn, slug),
        "cards": cards,
        "totalCopies": sum(card["copyCount"] for card in cards),
        "uniquePrints": len(cards),
    }


def delete_instance(conn: sqlite3.Connection, instance_id: int) -> dict:
    row = conn.execute(
        """
        SELECT instance_id, location_slug
        FROM card_instances
        WHERE instance_id = ?
        """,
        (instance_id,),
    ).fetchone()
    if row is None:
        raise StorageError("Card instance not found", status_code=404)

    location_slug = row["location_slug"]
    if str(location_slug).lower().startswith("deck:"):
        raise StorageError(DECK_STORAGE_MANUAL_MESSAGE, status_code=400)

    conn.execute(
        "DELETE FROM card_instances WHERE instance_id = ?",
        (instance_id,),
    )
    bump_cache_epoch()
    return get_location(conn, location_slug)


BREAKDOWN_INSTANCES_QUERY = """
SELECT
    ci.instance_id,
    ci.set_code,
    ci.collector_number,
    ci.finish,
    ci.purchase_value,
    ci.location_slug,
    sl.label AS location_label,
    sl.location_type,
    sl.sort_order,
    c.name,
    c.art_style,
    c.image_uri,
    c.image_uri_back,
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.cardmarket_url,
    c.cardmarket_url_foil,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched
FROM card_instances ci
JOIN storage_locations sl ON sl.location_slug = ci.location_slug
LEFT JOIN cards c
    ON c.set_code = ci.set_code
    AND c.collector_number = ci.collector_number
WHERE ci.location_slug = ?
"""

FINISH_LABELS = {
    0: "Nonfoil",
    1: "Foil",
    2: "Etched",
}


def get_storage_breakdown(
    conn: sqlite3.Connection,
    location_slug: str,
    *,
    price_strategy: str,
    top_cards: int = 8,
    top_sets: int = 8,
) -> dict:
    """Aggregate copies, value, and mix for one storage location."""
    ensure_card_columns(conn)
    location = get_location(conn, location_slug)
    rows = conn.execute(BREAKDOWN_INSTANCES_QUERY, (location["slug"],)).fetchall()

    by_finish: dict[int, dict] = {}
    by_set: dict[str, dict] = {}
    by_print: dict[tuple, dict] = {}

    total_copies = 0
    total_current = 0.0
    total_invested = 0.0
    priced_copies = 0
    invested_copies = 0

    for row in rows:
        finish = int(row["finish"] or 0)
        set_code = str(row["set_code"] or "").upper()
        collector = str(row["collector_number"] or "")
        unit_current = price_from_strategy(
            row["cardmarket_url"],
            finish,
            price_strategy,
            cardmarket_url_foil=row["cardmarket_url_foil"],
            market_value=_float_or_none(row["market_value"]),
            market_value_foil=_float_or_none(row["market_value_foil"]),
            market_value_etched=_float_or_none(row["market_value_etched"]),
            has_nonfoil=row["has_nonfoil"],
            has_foil=row["has_foil"],
            has_etched=row["has_etched"],
        )
        unit_invested = _float_or_none(row["purchase_value"])

        total_copies += 1
        if unit_current is not None:
            total_current += unit_current
            priced_copies += 1
        if unit_invested is not None:
            total_invested += unit_invested
            invested_copies += 1

        finish_bucket = by_finish.setdefault(
            finish,
            {
                "id": finish,
                "label": FINISH_LABELS.get(finish, f"Finish {finish}"),
                "copies": 0,
                "current": 0.0,
            },
        )
        finish_bucket["copies"] += 1
        if unit_current is not None:
            finish_bucket["current"] += unit_current

        if set_code:
            set_bucket = by_set.setdefault(
                set_code,
                {
                    "setCode": set_code,
                    "copies": 0,
                    "uniquePrints": set(),
                    "current": 0.0,
                },
            )
            set_bucket["copies"] += 1
            set_bucket["uniquePrints"].add((collector, finish))
            if unit_current is not None:
                set_bucket["current"] += unit_current

        print_key = (set_code, collector, finish)
        print_bucket = by_print.setdefault(
            print_key,
            {
                "setCode": set_code,
                "collectorNumber": collector,
                "finish": finish,
                "name": deck_card_display_name({
                    "catalog_name": row["name"],
                    "card_name": row["name"],
                    "set_code": set_code,
                    "collector_number": collector,
                }),
                "artStyle": str_or_empty(row["art_style"]),
                **card_image_fields(row),
                "copyCount": 0,
                "unitValue": unit_current,
                "current": 0.0,
            },
        )
        print_bucket["copyCount"] += 1
        if unit_current is not None:
            print_bucket["current"] += unit_current
            if print_bucket["unitValue"] is None:
                print_bucket["unitValue"] = unit_current

    finish_rows = []
    for finish in (0, 1, 2):
        bucket = by_finish.get(finish)
        if not bucket or not bucket["copies"]:
            continue
        finish_rows.append({
            "id": bucket["id"],
            "label": bucket["label"],
            "count": bucket["copies"],
            "copies": bucket["copies"],
            "current": round(bucket["current"], 2) if bucket["current"] else 0.0,
            "share": (bucket["copies"] / total_copies) if total_copies else 0.0,
        })

    set_rows = []
    for bucket in by_set.values():
        if not bucket["copies"]:
            continue
        set_rows.append({
            "id": bucket["setCode"],
            "setCode": bucket["setCode"],
            "label": bucket["setCode"],
            "count": bucket["copies"],
            "copies": bucket["copies"],
            "uniquePrints": len(bucket["uniquePrints"]),
            "current": round(bucket["current"], 2) if bucket["current"] else 0.0,
            "share": (bucket["copies"] / total_copies) if total_copies else 0.0,
            "valueShare": (bucket["current"] / total_current) if total_current else 0.0,
        })
    set_rows.sort(key=lambda row: (-row["current"], -row["copies"], row["setCode"]))
    set_rows = set_rows[:top_sets]

    top_card_rows = []
    for bucket in by_print.values():
        top_card_rows.append({
            "setCode": bucket["setCode"],
            "collectorNumber": bucket["collectorNumber"],
            "finish": bucket["finish"],
            "name": bucket["name"],
            "artStyle": bucket["artStyle"],
            "imageUri": bucket.get("imageUri") or "",
            "imageUriBack": bucket.get("imageUriBack") or "",
            "copyCount": bucket["copyCount"],
            "unitValue": bucket["unitValue"],
            "current": round(bucket["current"], 2) if bucket["current"] else 0.0,
        })
    top_card_rows.sort(key=lambda row: (-row["current"], -row["copyCount"], row["name"]))
    top_card_rows = top_card_rows[:top_cards]

    profit = None
    if priced_copies and invested_copies:
        profit = round(total_current - total_invested, 2)

    return {
        "location": location,
        "totals": {
            "copies": total_copies,
            "uniquePrints": len(by_print),
            "current": round(total_current, 2) if priced_copies else None,
            "invested": round(total_invested, 2) if invested_copies else None,
            "profit": profit,
            "pricedCopies": priced_copies,
            "unpricedCopies": max(0, total_copies - priced_copies),
        },
        "byFinish": finish_rows,
        "bySet": set_rows,
        "topCards": top_card_rows,
    }


def _next_custom_sort_order(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(sort_order), 1999)
        FROM storage_locations
        WHERE location_slug LIKE 'custom:%'
        """
    ).fetchone()
    return int(row[0]) + 1


def _next_binder_sort_order(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(sort_order), 0)
        FROM storage_locations
        WHERE location_type = 'binder'
        """
    ).fetchone()
    return int(row[0]) + 10


def _serialize_location(row: sqlite3.Row) -> dict:
    slug = row["location_slug"]
    card_count = int(row["card_count"])
    is_system = bool(row["is_system"])
    return {
        "slug": slug,
        "label": row["label"],
        "locationType": row["location_type"],
        "description": row["description"] or "",
        "sortOrder": int(row["sort_order"]),
        "isSystem": is_system,
        "cardCount": card_count,
        "uniquePrints": int(row["unique_prints"]),
        "canDelete": not is_system and card_count == 0,
        "isCustom": slug.startswith("custom:") or slug.startswith("binder:custom:"),
    }


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)
