import sqlite3
import uuid

from api.cache import bump_cache_epoch
from api.services.pricing_service import price_from_strategy
from report.card_detail_data import collector_sort_key
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.card_metadata import card_metadata_api
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
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.cardmarket_url,
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
) -> dict:
    cleaned_label = label.strip()
    if not cleaned_label:
        raise StorageError("Label is required")

    slug = f"custom:{uuid.uuid4().hex[:12]}"
    sort_order = _next_custom_sort_order(conn)
    conn.execute(
        """
        INSERT INTO storage_locations (
            location_slug, label, location_type, sort_order,
            set_code, description, deck_id, is_system
        ) VALUES (?, ?, 'storage', ?, NULL, ?, NULL, 0)
        """,
        (slug, cleaned_label, sort_order, (description or "").strip() or None),
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
                "imageUri": str_or_empty(row["image_uri"]),
                **card_metadata_api(row),
                "currentValue": price_from_strategy(
                    row["cardmarket_url"],
                    finish,
                    price_strategy,
                    market_value=_float_or_none(row["market_value"]),
                    market_value_foil=_float_or_none(row["market_value_foil"]),
                    market_value_etched=_float_or_none(row["market_value_etched"]),
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
    conn.execute(
        "DELETE FROM card_instances WHERE instance_id = ?",
        (instance_id,),
    )
    bump_cache_epoch()
    return get_location(conn, location_slug)


def _next_custom_sort_order(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(sort_order), 1999)
        FROM storage_locations
        WHERE location_slug LIKE 'custom:%'
        """
    ).fetchone()
    return int(row[0]) + 1


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
        "isCustom": slug.startswith("custom:"),
    }


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)
