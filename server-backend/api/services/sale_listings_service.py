"""For-sale listings and sold archive backed by sale_listings."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from api.cache import bump_cache_epoch
from api.services import settings_service
from api.services.pricing_service import list_price_strategies, price_from_strategy, values_by_strategy_for_finish
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.app_tables import ensure_app_tables
from util.card_finishes import finish_label
from util.card_metadata import card_image_fields, card_metadata_api
from util.db_migrate import ensure_card_columns
from util.sale_listings import ensure_sale_listings_table
from util.set_catalog import load_set_display_names


class SaleListingsError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_non_negative_price(value, *, field_name: str) -> float:
    if value is None:
        raise SaleListingsError(f"{field_name} is required")
    try:
        price = float(value)
    except (TypeError, ValueError) as exc:
        raise SaleListingsError(f"{field_name} must be a number") from exc
    if price < 0:
        raise SaleListingsError(f"{field_name} must be zero or greater")
    return price


def _location_labels(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT location_slug, label FROM storage_locations"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _catalog_row(conn: sqlite3.Connection, set_code: str, collector_number: str):
    ensure_card_columns(conn)
    return conn.execute(
        """
        SELECT *
        FROM cards
        WHERE set_code = ? AND collector_number = ?
        LIMIT 1
        """,
        (set_code, str(collector_number).strip()),
    ).fetchone()


def _current_value(card_row, finish: int, strategy: str) -> float | None:
    if card_row is None:
        return None
    return price_from_strategy(
        card_row["cardmarket_url"] if "cardmarket_url" in card_row.keys() else None,
        finish,
        strategy,
        cardmarket_url_foil=card_row["cardmarket_url_foil"] if "cardmarket_url_foil" in card_row.keys() else None,
        market_value=_float_or_none(card_row["market_value"]) if "market_value" in card_row.keys() else None,
        market_value_foil=_float_or_none(card_row["market_value_foil"]) if "market_value_foil" in card_row.keys() else None,
        market_value_etched=_float_or_none(card_row["market_value_etched"]) if "market_value_etched" in card_row.keys() else None,
        has_nonfoil=card_row["has_nonfoil"] if "has_nonfoil" in card_row.keys() else None,
        has_foil=card_row["has_foil"] if "has_foil" in card_row.keys() else None,
        has_etched=card_row["has_etched"] if "has_etched" in card_row.keys() else None,
    )


def _values_by_strategy(card_row, finish: int) -> dict[str, float | None]:
    if card_row is None:
        return {strategy["id"]: None for strategy in list_price_strategies()}
    return values_by_strategy_for_finish(
        {
            "cardmarket_url": card_row["cardmarket_url"] if "cardmarket_url" in card_row.keys() else None,
            "cardmarket_url_foil": (
                card_row["cardmarket_url_foil"] if "cardmarket_url_foil" in card_row.keys() else None
            ),
            "market_value": _float_or_none(card_row["market_value"]) if "market_value" in card_row.keys() else None,
            "market_value_foil": (
                _float_or_none(card_row["market_value_foil"]) if "market_value_foil" in card_row.keys() else None
            ),
            "market_value_etched": (
                _float_or_none(card_row["market_value_etched"])
                if "market_value_etched" in card_row.keys()
                else None
            ),
            "has_nonfoil": card_row["has_nonfoil"] if "has_nonfoil" in card_row.keys() else None,
            "has_foil": card_row["has_foil"] if "has_foil" in card_row.keys() else None,
            "has_etched": card_row["has_etched"] if "has_etched" in card_row.keys() else None,
        },
        finish,
    )


def _serialize_listing(
    row: sqlite3.Row,
    *,
    strategy: str,
    location_labels: dict[str, str],
    set_names: dict[str, str] | None = None,
    catalog_row=None,
) -> dict:
    set_code = row["set_code"]
    collector_number = str(row["collector_number"])
    finish = int(row["finish"])
    if catalog_row is None:
        catalog_row = None  # caller may pass None intentionally
    purchase_value = _float_or_none(row["purchase_value"])
    listing_price = float(row["listing_price"])
    sale_price = _float_or_none(row["sale_price"])
    current_value = _current_value(catalog_row, finish, strategy) if catalog_row is not None else None
    values_by_strategy = _values_by_strategy(catalog_row, finish)
    location_slug = row["location_slug"] or ""
    code_key = str(set_code or "").strip().upper()
    set_label = (set_names or {}).get(code_key) or code_key or set_code
    payload = {
        "listingId": int(row["listing_id"]),
        "status": row["status"],
        "setCode": set_code,
        "setLabel": set_label,
        "collectorNumber": collector_number,
        "finish": finish,
        "foil": finish,
        "finishLabel": finish_label(finish),
        "listingPrice": listing_price,
        "salePrice": sale_price,
        "purchaseValue": purchase_value,
        "locationSlug": location_slug or None,
        "locationLabel": location_labels.get(location_slug) if location_slug else None,
        "instanceId": int(row["instance_id"]) if row["instance_id"] is not None else None,
        "notes": row["notes"] or "",
        "listedAt": row["listed_at"],
        "soldAt": row["sold_at"],
        "sortOrder": int(row["sort_order"] or 0),
        "currentValue": current_value,
        "valuesByStrategy": values_by_strategy,
        "name": deck_card_display_name({
            "catalog_name": catalog_row["name"] if catalog_row is not None else None,
            "card_name": catalog_row["name"] if catalog_row is not None else None,
            "set_code": set_code,
            "collector_number": collector_number,
        }) if catalog_row is not None else f"{set_code} #{collector_number}",
        "artStyle": str_or_empty(catalog_row["art_style"]) if catalog_row is not None and "art_style" in catalog_row.keys() else "",
        "rarity": (
            str_or_empty(catalog_row["rarity"]).lower() or None
            if catalog_row is not None and "rarity" in catalog_row.keys()
            else None
        ),
    }
    if catalog_row is not None:
        payload.update(card_image_fields(catalog_row))
        payload.update(card_metadata_api(catalog_row))
    else:
        payload["imageUri"] = ""
        payload["imageUriBack"] = ""

    if row["status"] == "sold" and sale_price is not None and purchase_value is not None:
        payload["profitLoss"] = round(sale_price - purchase_value, 2)
    elif row["status"] == "listed" and current_value is not None:
        payload["vsMarket"] = round(listing_price - current_value, 2)
    else:
        payload["profitLoss"] = None
        payload["vsMarket"] = None
    return payload


def _load_listing_row(conn: sqlite3.Connection, listing_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM sale_listings WHERE listing_id = ?",
        (listing_id,),
    ).fetchone()
    if row is None:
        raise SaleListingsError("Listing not found", status_code=404)
    return row


def _hydrate_rows(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict]:
    strategy = settings_service.get_settings(conn)["priceStrategy"]
    labels = _location_labels(conn)
    set_names = load_set_display_names(conn)
    catalog_cache: dict[tuple[str, str], object] = {}
    items: list[dict] = []
    for row in rows:
        key = (row["set_code"], str(row["collector_number"]))
        if key not in catalog_cache:
            catalog_cache[key] = _catalog_row(conn, key[0], key[1])
        items.append(
            _serialize_listing(
                row,
                strategy=strategy,
                location_labels=labels,
                set_names=set_names,
                catalog_row=catalog_cache[key],
            )
        )
    return items


def list_listed(conn: sqlite3.Connection) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    rows = conn.execute(
        """
        SELECT *
        FROM sale_listings
        WHERE status = 'listed'
        ORDER BY sort_order ASC, listing_id DESC
        """
    ).fetchall()
    cards = _hydrate_rows(conn, rows)
    total_asking = sum(float(card["listingPrice"]) for card in cards)
    return {
        "status": "listed",
        "cards": cards,
        "totalListings": len(cards),
        "totalAsking": round(total_asking, 2),
        "priceStrategy": settings_service.get_settings(conn)["priceStrategy"],
    }


def listed_asking_by_print_key(conn: sqlite3.Connection) -> dict[str, float]:
    """Map print key -> asking price for currently listed copies (min if several)."""
    from util.card_finishes import card_price_key

    ensure_sale_listings_table(conn)
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sale_listings'"
    ).fetchone()
    if not table:
        return {}

    asking: dict[str, float] = {}
    for set_code, collector_number, finish, listing_price in conn.execute(
        """
        SELECT set_code, collector_number, finish, listing_price
        FROM sale_listings
        WHERE status = 'listed'
        """
    ):
        key = card_price_key(set_code, collector_number, finish)
        price = float(listing_price)
        current = asking.get(key)
        if current is None or price < current:
            asking[key] = price
    return asking


def listed_asking_by_instance_id(conn: sqlite3.Connection) -> dict[int, float]:
    """Map instance_id -> asking price for currently listed copies."""
    return {
        instance_id: payload["listingPrice"]
        for instance_id, payload in listed_listings_by_instance_id(conn).items()
    }


def listed_listings_by_instance_id(conn: sqlite3.Connection) -> dict[int, dict]:
    """Map instance_id -> {listingId, listingPrice} for currently listed copies."""
    ensure_sale_listings_table(conn)
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sale_listings'"
    ).fetchone()
    if not table:
        return {}

    return {
        int(instance_id): {
            "listingId": int(listing_id),
            "listingPrice": float(listing_price),
        }
        for listing_id, instance_id, listing_price in conn.execute(
            """
            SELECT listing_id, instance_id, listing_price
            FROM sale_listings
            WHERE status = 'listed' AND instance_id IS NOT NULL
            """
        )
        if instance_id is not None
    }


def list_sold(conn: sqlite3.Connection) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    rows = conn.execute(
        """
        SELECT *
        FROM sale_listings
        WHERE status = 'sold'
        ORDER BY sold_at DESC, listing_id DESC
        """
    ).fetchall()
    cards = _hydrate_rows(conn, rows)
    total_sales = sum(float(card["salePrice"] or 0) for card in cards)
    total_profit = sum(float(card["profitLoss"] or 0) for card in cards if card.get("profitLoss") is not None)
    return {
        "status": "sold",
        "cards": cards,
        "totalListings": len(cards),
        "totalSales": round(total_sales, 2),
        "totalProfitLoss": round(total_profit, 2),
        "priceStrategy": settings_service.get_settings(conn)["priceStrategy"],
    }


def create_listing(
    conn: sqlite3.Connection,
    *,
    instance_id: int,
    listing_price,
    notes: str = "",
) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    price = _parse_non_negative_price(listing_price, field_name="listingPrice")
    instance = conn.execute(
        """
        SELECT instance_id, set_code, collector_number, finish, purchase_value, location_slug
        FROM card_instances
        WHERE instance_id = ?
        """,
        (int(instance_id),),
    ).fetchone()
    if instance is None:
        raise SaleListingsError("Copy not found", status_code=404)

    existing = conn.execute(
        """
        SELECT listing_id
        FROM sale_listings
        WHERE status = 'listed' AND instance_id = ?
        """,
        (int(instance_id),),
    ).fetchone()
    if existing:
        raise SaleListingsError("This copy is already listed for sale")

    max_sort = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM sale_listings WHERE status = 'listed'"
    ).fetchone()[0]
    cursor = conn.execute(
        """
        INSERT INTO sale_listings (
            status, set_code, collector_number, finish,
            listing_price, sale_price, purchase_value, location_slug,
            instance_id, notes, listed_at, sold_at, sort_order
        ) VALUES (
            'listed', ?, ?, ?,
            ?, NULL, ?, ?,
            ?, ?, ?, NULL, ?
        )
        """,
        (
            instance["set_code"],
            str(instance["collector_number"]),
            int(instance["finish"]),
            price,
            _float_or_none(instance["purchase_value"]),
            instance["location_slug"],
            int(instance["instance_id"]),
            (notes or "").strip(),
            _utc_now(),
            int(max_sort) + 1,
        ),
    )
    bump_cache_epoch()
    listing_id = int(cursor.lastrowid)
    return _hydrate_rows(conn, [_load_listing_row(conn, listing_id)])[0]


def update_listed(
    conn: sqlite3.Connection,
    listing_id: int,
    *,
    listing_price=None,
    notes: str | None = None,
    sort_order: int | None = None,
) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    row = _load_listing_row(conn, listing_id)
    if row["status"] != "listed":
        raise SaleListingsError("Listing is not active", status_code=400)

    next_price = float(row["listing_price"])
    if listing_price is not None:
        next_price = _parse_non_negative_price(listing_price, field_name="listingPrice")
    next_notes = row["notes"] or ""
    if notes is not None:
        next_notes = notes.strip()
    next_sort = int(row["sort_order"] or 0)
    if sort_order is not None:
        next_sort = int(sort_order)

    conn.execute(
        """
        UPDATE sale_listings
        SET listing_price = ?, notes = ?, sort_order = ?
        WHERE listing_id = ?
        """,
        (next_price, next_notes, next_sort, listing_id),
    )
    bump_cache_epoch()
    return _hydrate_rows(conn, [_load_listing_row(conn, listing_id)])[0]


def update_sold(
    conn: sqlite3.Connection,
    listing_id: int,
    *,
    sale_price=None,
    notes: str | None = None,
) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    row = _load_listing_row(conn, listing_id)
    if row["status"] != "sold":
        raise SaleListingsError("Listing is not in the sold archive", status_code=400)

    next_sale = _float_or_none(row["sale_price"])
    if sale_price is not None:
        next_sale = _parse_non_negative_price(sale_price, field_name="salePrice")
    if next_sale is None:
        raise SaleListingsError("salePrice is required")
    next_notes = row["notes"] or ""
    if notes is not None:
        next_notes = notes.strip()

    conn.execute(
        """
        UPDATE sale_listings
        SET sale_price = ?, notes = ?
        WHERE listing_id = ?
        """,
        (next_sale, next_notes, listing_id),
    )
    bump_cache_epoch()
    return _hydrate_rows(conn, [_load_listing_row(conn, listing_id)])[0]


def unlist(conn: sqlite3.Connection, listing_id: int) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    row = _load_listing_row(conn, listing_id)
    if row["status"] != "listed":
        raise SaleListingsError("Only active listings can be unlisted", status_code=400)
    conn.execute("DELETE FROM sale_listings WHERE listing_id = ?", (listing_id,))
    bump_cache_epoch()
    return {"ok": True, "listingId": listing_id}


def delete_sold(conn: sqlite3.Connection, listing_id: int) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    row = _load_listing_row(conn, listing_id)
    if row["status"] != "sold":
        raise SaleListingsError("Only sold archive rows can be deleted this way", status_code=400)
    conn.execute("DELETE FROM sale_listings WHERE listing_id = ?", (listing_id,))
    bump_cache_epoch()
    return {"ok": True, "listingId": listing_id}


def mark_sold(
    conn: sqlite3.Connection,
    listing_id: int,
    *,
    sale_price,
) -> dict:
    ensure_app_tables(conn)
    ensure_sale_listings_table(conn)
    row = _load_listing_row(conn, listing_id)
    if row["status"] != "listed":
        raise SaleListingsError("Only active listings can be marked sold", status_code=400)

    price = _parse_non_negative_price(sale_price, field_name="salePrice")
    instance_id = row["instance_id"]
    set_code = row["set_code"]
    collector_number = str(row["collector_number"])
    finish = int(row["finish"])

    # Prefer the linked instance; otherwise claim any matching owned copy.
    if instance_id is not None:
        instance = conn.execute(
            "SELECT instance_id FROM card_instances WHERE instance_id = ?",
            (int(instance_id),),
        ).fetchone()
        if instance is None:
            instance_id = None

    if instance_id is None:
        rematch = conn.execute(
            """
            SELECT instance_id
            FROM card_instances
            WHERE set_code = ? AND collector_number = ? AND finish = ?
            ORDER BY
              CASE WHEN location_slug = ? THEN 0 ELSE 1 END,
              instance_id
            LIMIT 1
            """,
            (set_code, collector_number, finish, row["location_slug"] or ""),
        ).fetchone()
        if rematch is None:
            raise SaleListingsError(
                "Owned copy for this listing is missing; unlist or restore the copy first",
                status_code=409,
            )
        instance_id = int(rematch["instance_id"])

    purchase_value = _float_or_none(row["purchase_value"])
    instance_row = conn.execute(
        """
        SELECT purchase_value, location_slug
        FROM card_instances
        WHERE instance_id = ?
        """,
        (instance_id,),
    ).fetchone()
    if instance_row is not None:
        if purchase_value is None:
            purchase_value = _float_or_none(instance_row["purchase_value"])
        location_slug = instance_row["location_slug"]
    else:
        location_slug = row["location_slug"]

    conn.execute("DELETE FROM card_instances WHERE instance_id = ?", (instance_id,))

    from api.services.manager_service import _sync_finish_purchase_aggregate

    _sync_finish_purchase_aggregate(conn, set_code, collector_number, finish)

    conn.execute(
        """
        UPDATE sale_listings
        SET status = 'sold',
            sale_price = ?,
            purchase_value = ?,
            location_slug = ?,
            instance_id = NULL,
            sold_at = ?
        WHERE listing_id = ?
        """,
        (price, purchase_value, location_slug, _utc_now(), listing_id),
    )
    bump_cache_epoch()
    return _hydrate_rows(conn, [_load_listing_row(conn, listing_id)])[0]


def rematch_listed_instances(conn: sqlite3.Connection) -> dict:
    """Re-link open listings to card_instances after a full instance sync wipe."""
    ensure_sale_listings_table(conn)
    listed = conn.execute(
        """
        SELECT listing_id, set_code, collector_number, finish, location_slug, instance_id
        FROM sale_listings
        WHERE status = 'listed'
        ORDER BY listing_id
        """
    ).fetchall()
    if not listed:
        return {"rematched": 0, "cleared": 0, "removed": 0}

    claimed: set[int] = set()
    rematched = 0
    cleared = 0
    removed = 0

    for row in listed:
        listing_id = int(row["listing_id"])
        current_id = int(row["instance_id"]) if row["instance_id"] is not None else None
        if current_id is not None and current_id not in claimed:
            still = conn.execute(
                "SELECT 1 FROM card_instances WHERE instance_id = ?",
                (current_id,),
            ).fetchone()
            if still:
                claimed.add(current_id)
                continue

        candidates = conn.execute(
            """
            SELECT instance_id, location_slug
            FROM card_instances
            WHERE set_code = ? AND collector_number = ? AND finish = ?
            ORDER BY instance_id
            """,
            (row["set_code"], str(row["collector_number"]), int(row["finish"])),
        ).fetchall()
        preferred = row["location_slug"] or ""
        match_id = None
        for candidate in candidates:
            cid = int(candidate["instance_id"])
            if cid in claimed:
                continue
            if preferred and candidate["location_slug"] == preferred:
                match_id = cid
                break
        if match_id is None:
            for candidate in candidates:
                cid = int(candidate["instance_id"])
                if cid not in claimed:
                    match_id = cid
                    break

        if match_id is None:
            conn.execute("DELETE FROM sale_listings WHERE listing_id = ?", (listing_id,))
            removed += 1
            continue

        claimed.add(match_id)
        if current_id != match_id:
            conn.execute(
                "UPDATE sale_listings SET instance_id = ? WHERE listing_id = ?",
                (match_id, listing_id),
            )
            rematched += 1
            if current_id is not None:
                cleared += 1

    return {"rematched": rematched, "cleared": cleared, "removed": removed}


def clear_listing_instance_link(conn: sqlite3.Connection, instance_id: int) -> None:
    """When a copy is deleted outside the sell flow, drop the soft link."""
    ensure_sale_listings_table(conn)
    conn.execute(
        """
        UPDATE sale_listings
        SET instance_id = NULL
        WHERE status = 'listed' AND instance_id = ?
        """,
        (int(instance_id),),
    )
