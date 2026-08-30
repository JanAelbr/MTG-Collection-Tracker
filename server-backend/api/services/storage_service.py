import json
import sqlite3
import uuid
from datetime import datetime, timezone

from api.cache import bump_cache_epoch
from api.services.pricing_service import (
    price_from_strategy,
    value_from_strategy_map,
    values_by_strategy_for_finish,
)
from report.card_detail_data import collector_sort_key
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.card_metadata import card_image_fields, card_metadata_api
from util.db_migrate import ensure_card_columns
from util.set_catalog import load_set_display_names

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
    c.color_identity,
    c.type_line,
    c.card_type,
    c.oracle_text,
    c.mana_cost,
    c.cmc,
    c.rarity,
    c.power,
    c.toughness
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
    from api.services.sale_listings_service import listed_listings_by_instance_id
    from util.card_name_roles import load_card_name_roles_map

    listed_by_instance = listed_listings_by_instance_id(conn)
    roles_by_name = load_card_name_roles_map(conn)
    from util.set_families import load_family_roots

    family_roots = load_family_roots(conn)
    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = (row["set_code"], str(row["collector_number"]), int(row["finish"]))
        card = grouped.get(key)
        if card is None:
            finish = int(row["finish"])
            set_code = str(row["set_code"] or "").strip().upper()
            name = deck_card_display_name({
                "catalog_name": row["name"],
                "card_name": row["name"],
                "set_code": row["set_code"],
                "collector_number": row["collector_number"],
            })
            catalog_name = str_or_empty(row["name"])
            roles = (
                roles_by_name.get(catalog_name)
                or roles_by_name.get(catalog_name.casefold())
                or []
            )
            values_by_strategy, current_value = _finish_prices(
                row, finish, price_strategy
            )
            card = {
                "setCode": row["set_code"],
                "familyRoot": family_roots.get(set_code) or set_code,
                "collectorNumber": str(row["collector_number"]),
                "finish": finish,
                "foil": finish,
                "copyCount": 0,
                "instanceIds": [],
                "purchaseValue": _float_or_none(row["purchase_value"]),
                "name": name,
                "artStyle": str_or_empty(row["art_style"]),
                **card_image_fields(row),
                **card_metadata_api(row),
                "roles": list(roles),
                "valuesByStrategy": values_by_strategy,
                "currentValue": current_value,
            }
            grouped[key] = card
        card["copyCount"] += 1
        instance_id = int(row["instance_id"])
        card["instanceIds"].append(instance_id)
        listing = listed_by_instance.get(instance_id)
        if listing is not None:
            current_ask = card.get("listingPrice")
            if current_ask is None or listing["listingPrice"] < current_ask:
                card["listingPrice"] = listing["listingPrice"]
                card["listingId"] = listing["listingId"]
                card["listedInstanceId"] = instance_id
            card["forSale"] = True

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
    try:
        from api.services.sale_listings_service import clear_listing_instance_link

        clear_listing_instance_link(conn, instance_id)
    except Exception:
        pass
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
    by_art_style: dict[str, dict] = {}
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

        art_style = str_or_empty(row["art_style"])
        if art_style:
            art_bucket = by_art_style.setdefault(
                art_style,
                {
                    "artStyle": art_style,
                    "copies": 0,
                    "current": 0.0,
                },
            )
            art_bucket["copies"] += 1
            if unit_current is not None:
                art_bucket["current"] += unit_current

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

    art_style_rows = []
    for bucket in by_art_style.values():
        if not bucket["copies"]:
            continue
        art_style_rows.append({
            "id": bucket["artStyle"],
            "artStyle": bucket["artStyle"],
            "label": bucket["artStyle"],
            "count": bucket["copies"],
            "copies": bucket["copies"],
            "current": round(bucket["current"], 2) if bucket["current"] else 0.0,
            "share": (bucket["copies"] / total_copies) if total_copies else 0.0,
            "valueShare": (bucket["current"] / total_current) if total_current else 0.0,
        })
    art_style_rows.sort(key=lambda row: (-row["current"], -row["copies"], row["artStyle"]))

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
        "byArtStyle": art_style_rows,
        "topCards": top_card_rows,
    }


SNAPSHOT_LOCATION_TYPES = frozenset({"storage", "binder"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot_locations(conn: sqlite3.Connection) -> list[dict]:
    return [
        loc for loc in list_locations(conn)
        if loc["locationType"] in SNAPSHOT_LOCATION_TYPES
    ]


def _combined_snapshot_totals(locations: list[dict]) -> dict:
    copies = 0
    unique_prints = 0
    current = 0.0
    invested = 0.0
    priced = 0
    invested_copies = 0
    unpriced = 0
    has_current = False
    has_invested = False
    for loc in locations:
        totals = loc.get("totals") or {}
        copies += int(totals.get("copies") or 0)
        unique_prints += int(totals.get("uniquePrints") or 0)
        unpriced += int(totals.get("unpricedCopies") or 0)
        priced += int(totals.get("pricedCopies") or 0)
        if totals.get("current") is not None:
            current += float(totals["current"])
            has_current = True
        if totals.get("invested") is not None:
            invested += float(totals["invested"])
            has_invested = True
            invested_copies += 1
    profit = None
    if has_current and has_invested and priced:
        profit = round(current - invested, 2)
    return {
        "copies": copies,
        "uniquePrints": unique_prints,
        "current": round(current, 2) if has_current else None,
        "invested": round(invested, 2) if has_invested else None,
        "profit": profit,
        "pricedCopies": priced,
        "unpricedCopies": unpriced,
        "locationCount": len(locations),
    }


def _serialize_snapshot_row(row: sqlite3.Row, *, include_payload: bool = False) -> dict:
    payload = json.loads(row["payload_json"])
    locations = payload.get("locations") or []
    item = {
        "id": int(row["snapshot_id"]),
        "snapshotDate": row["snapshot_date"],
        "createdAt": row["created_at"],
        "note": row["note"] or "",
        "priceStrategy": row["price_strategy"] or "",
        "totals": _combined_snapshot_totals(locations),
    }
    if include_payload:
        item["locations"] = locations
        item["payload"] = payload
    return item


def save_daily_breakdown(
    conn: sqlite3.Connection,
    *,
    price_strategy: str,
    note: str = "",
) -> dict:
    from util.storage_tables import ensure_storage_tables

    ensure_storage_tables(conn)
    now = _utc_now()
    snapshot_date = now.date().isoformat()
    created_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    locations = []
    for loc in _snapshot_locations(conn):
        breakdown = get_storage_breakdown(
            conn,
            loc["slug"],
            price_strategy=price_strategy,
            top_sets=10_000,
        )
        locations.append({
            "slug": loc["slug"],
            "label": loc["label"],
            "locationType": loc["locationType"],
            "totals": breakdown["totals"],
            "byFinish": breakdown["byFinish"],
            "bySet": breakdown["bySet"],
            "byArtStyle": breakdown["byArtStyle"],
            "topCards": breakdown["topCards"],
        })
    payload = {
        "snapshotDate": snapshot_date,
        "priceStrategy": price_strategy,
        "locations": locations,
    }
    cleaned_note = (note or "").strip()
    conn.execute(
        """
        INSERT INTO storage_breakdown_snapshots (
            snapshot_date, created_at, note, price_strategy, payload_json
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date) DO UPDATE SET
            created_at = excluded.created_at,
            note = excluded.note,
            price_strategy = excluded.price_strategy,
            payload_json = excluded.payload_json
        """,
        (
            snapshot_date,
            created_at,
            cleaned_note or None,
            price_strategy,
            json.dumps(payload),
        ),
    )
    bump_cache_epoch()
    row = conn.execute(
        """
        SELECT snapshot_id, snapshot_date, created_at, note, price_strategy, payload_json
        FROM storage_breakdown_snapshots
        WHERE snapshot_date = ?
        """,
        (snapshot_date,),
    ).fetchone()
    return _serialize_snapshot_row(row)


def _history_mix_rows(rows: list | None, id_field: str) -> list[dict]:
    compact: list[dict] = []
    for row in rows or []:
        ident = str(row.get(id_field) or row.get("id") or "").strip()
        if not ident:
            continue
        compact.append({
            "id": ident,
            "label": str(row.get("label") or ident),
            "copies": int(row.get("copies") or row.get("count") or 0),
            "current": float(row.get("current") or 0),
        })
    return compact


def _merge_history_mix(target: dict[str, dict], rows: list[dict]) -> None:
    for row in rows:
        bucket = target.get(row["id"])
        if bucket is None:
            target[row["id"]] = {
                "id": row["id"],
                "label": row["label"],
                "copies": row["copies"],
                "current": row["current"],
            }
            continue
        bucket["copies"] += row["copies"]
        bucket["current"] += row["current"]
        if row["label"]:
            bucket["label"] = row["label"]


def _rounded_mix(values: dict[str, dict]) -> list[dict]:
    rows = []
    for bucket in values.values():
        rows.append({
            "id": bucket["id"],
            "label": bucket["label"],
            "copies": int(bucket["copies"] or 0),
            "current": round(float(bucket["current"] or 0), 2),
        })
    rows.sort(key=lambda row: (-row["current"], -row["copies"], row["label"]))
    return rows


def _set_display_label(set_code: str, set_names: dict[str, str] | None) -> str:
    code = str(set_code or "").strip().upper()
    if not code:
        return ""
    name = (set_names or {}).get(code)
    return name or code


def compact_breakdown_history(
    snapshots: list[dict],
    set_names: dict[str, str] | None = None,
) -> dict:
    ordered = sorted(
        snapshots,
        key=lambda item: (str(item.get("snapshotDate") or ""), int(item.get("id") or 0)),
    )
    points = []
    has_art_styles = False
    for item in ordered:
        locations = item.get("locations") or []
        location_rows = []
        sets: dict[str, dict] = {}
        art_styles: dict[str, dict] = {}
        for loc in locations:
            totals = loc.get("totals") or {}
            slug = str(loc.get("slug") or "").strip()
            if slug:
                location_rows.append({
                    "id": slug,
                    "label": str(loc.get("label") or slug),
                    "copies": int(totals.get("copies") or 0),
                    "current": float(totals.get("current") or 0),
                })
            _merge_history_mix(sets, _history_mix_rows(loc.get("bySet"), "setCode"))
            art_rows = _history_mix_rows(loc.get("byArtStyle"), "artStyle")
            if art_rows:
                has_art_styles = True
            _merge_history_mix(art_styles, art_rows)
        combined = _combined_snapshot_totals(locations)
        points.append({
            "id": int(item.get("id") or 0),
            "date": item.get("snapshotDate") or "",
            "copies": int(combined.get("copies") or 0),
            "current": combined.get("current"),
            "locations": location_rows,
            "sets": [
                {**row, "label": _set_display_label(row["id"], set_names)}
                for row in _rounded_mix(sets)
            ],
            "artStyles": _rounded_mix(art_styles),
        })
    return {
        "points": points,
        "hasArtStyles": has_art_styles,
    }


def list_breakdown_history(conn: sqlite3.Connection) -> dict:
    from util.storage_tables import ensure_storage_tables

    ensure_storage_tables(conn)
    rows = conn.execute(
        """
        SELECT snapshot_id, snapshot_date, created_at, note, price_strategy, payload_json
        FROM storage_breakdown_snapshots
        ORDER BY snapshot_date ASC, snapshot_id ASC
        """
    ).fetchall()
    snapshots = [_serialize_snapshot_row(row, include_payload=True) for row in rows]
    return compact_breakdown_history(snapshots, set_names=load_set_display_names(conn))


def list_breakdown_snapshots(conn: sqlite3.Connection) -> list[dict]:
    from util.storage_tables import ensure_storage_tables

    ensure_storage_tables(conn)
    rows = conn.execute(
        """
        SELECT snapshot_id, snapshot_date, created_at, note, price_strategy, payload_json
        FROM storage_breakdown_snapshots
        ORDER BY snapshot_date DESC, snapshot_id DESC
        """
    ).fetchall()
    return [_serialize_snapshot_row(row) for row in rows]


def get_breakdown_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> dict:
    from util.storage_tables import ensure_storage_tables

    ensure_storage_tables(conn)
    row = conn.execute(
        """
        SELECT snapshot_id, snapshot_date, created_at, note, price_strategy, payload_json
        FROM storage_breakdown_snapshots
        WHERE snapshot_id = ?
        """,
        (int(snapshot_id),),
    ).fetchone()
    if row is None:
        raise StorageError("Breakdown snapshot not found", status_code=404)
    return _serialize_snapshot_row(row, include_payload=True)


def delete_breakdown_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> None:
    from util.storage_tables import ensure_storage_tables

    ensure_storage_tables(conn)
    cursor = conn.execute(
        "DELETE FROM storage_breakdown_snapshots WHERE snapshot_id = ?",
        (int(snapshot_id),),
    )
    if cursor.rowcount == 0:
        raise StorageError("Breakdown snapshot not found", status_code=404)
    bump_cache_epoch()


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


def _guide_fields_from_row(row) -> dict:
    return {
        "cardmarket_url": row["cardmarket_url"],
        "cardmarket_url_foil": row["cardmarket_url_foil"],
        "market_value": _float_or_none(row["market_value"]),
        "market_value_foil": _float_or_none(row["market_value_foil"]),
        "market_value_etched": _float_or_none(row["market_value_etched"]),
        "has_nonfoil": row["has_nonfoil"],
        "has_foil": row["has_foil"],
        "has_etched": row["has_etched"],
    }


def _finish_prices(row, finish: int, price_strategy: str) -> tuple[dict, float | None]:
    fields = _guide_fields_from_row(row)
    values = values_by_strategy_for_finish(fields, finish)
    current = value_from_strategy_map(
        values,
        price_strategy,
        finish=finish,
        market_value=fields["market_value"],
        market_value_foil=fields["market_value_foil"],
        market_value_etched=fields["market_value_etched"],
    )
    return values, current
