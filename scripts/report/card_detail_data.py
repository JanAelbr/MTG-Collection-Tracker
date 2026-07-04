import json
import sqlite3
from datetime import date

import pandas as pd

from lib.config import APP_CACHE_DIR, DB_PATH
from util.price_history import card_price_key, load_card_detail_compare_context
from util.set_catalog import load_sets_catalog
from util.storage_tables import ensure_storage_tables
from util.card_metadata import card_metadata_snake
from util.db_migrate import ensure_card_columns


def _float_or_none(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value)


def print_key(set_code: str, collector_number: str) -> str:
    return f"{set_code.upper()}|{collector_number}"


# Sort collector numbers numerically, keeping suffixes such as 378z in order.
def collector_sort_key(collector_number: str) -> tuple:
    collector_str = str(collector_number)
    digits = "".join(char for char in collector_str if char.isdigit())
    suffix = collector_str[len(digits):].lower() if digits else collector_str.lower()
    number = int(digits) if digits else 0
    return (number, suffix)


# Load all purchase rows keyed by set|number|finish.
def _load_purchases(conn: sqlite3.Connection) -> dict[str, float]:
    rows = conn.execute(
        "SELECT set_code, collector_number, finish, purchase_value FROM purchases"
    ).fetchall()
    return {
        card_price_key(set_code, collector_number, finish): float(purchase_value)
        for set_code, collector_number, finish, purchase_value in rows
    }


# Load card_prices grouped by card finish, one price per date (Cardmarket preferred).
def _load_price_histories(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    rows = conn.execute(
        """
        SELECT set_code, collector_number, finish, price_date, price, source
        FROM card_prices
        ORDER BY set_code, collector_number, finish, price_date,
                 CASE source WHEN 'cardmarket' THEN 0 WHEN 'scryfall' THEN 1 ELSE 99 END,
                 price_id
        """
    ).fetchall()
    if not rows:
        return {}

    histories: dict[str, list[dict]] = {}
    seen: set[tuple[str, str, int, str]] = set()
    for set_code, collector_number, finish, price_date, price, source in rows:
        dedupe_key = (set_code, str(collector_number), int(finish), price_date)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        key = card_price_key(set_code, collector_number, finish)
        histories.setdefault(key, []).append({
            "date": price_date,
            "price": float(price),
            "source": source,
        })
    return histories


# Load physical storage locations grouped by card finish.
def _load_card_locations(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
    ).fetchone()
    if not table:
        return {}

    rows = conn.execute(
        """
        SELECT
            ci.set_code,
            ci.collector_number,
            ci.finish,
            ci.location_slug,
            sl.label,
            sl.location_type,
            COUNT(*) AS copy_count
        FROM card_instances ci
        JOIN storage_locations sl ON sl.location_slug = ci.location_slug
        GROUP BY ci.set_code, ci.collector_number, ci.finish, ci.location_slug
        ORDER BY sl.sort_order, sl.label
        """
    ).fetchall()
    locations: dict[str, list[dict]] = {}
    for set_code, collector_number, finish, slug, label, location_type, copy_count in rows:
        key = card_price_key(set_code, collector_number, finish)
        locations.setdefault(key, []).append({
            "slug": slug,
            "label": label,
            "locationType": location_type,
            "count": int(copy_count),
        })
    return locations


# Build chart points from purchase price through history to today's value.
def _build_chart_points(
    history: list[dict],
    purchase_value: float | None,
    current_value: float | None,
) -> list[dict]:
    points: list[dict] = []

    if purchase_value is not None:
        points.append({"date": "Purchase", "price": purchase_value})

    for entry in history:
        if points and points[-1]["date"] == entry["date"] and points[-1]["price"] == entry["price"]:
            continue
        points.append({"date": entry["date"], "price": entry["price"]})

    if current_value is not None:
        if not points or points[-1]["price"] != current_value:
            label = "Today" if points else date.today().isoformat()
            if points and points[-1]["date"] not in ("Purchase", "Today"):
                label = "Today"
            points.append({"date": label, "price": current_value})

    return points


# Serialize one finish for the card index payload.
def _serialize_finish(
    purchase_value: float | None,
    current_value: float | None,
    *,
    has_history: bool = False,
    previous_value: float | None = None,
) -> dict | None:
    if purchase_value is None and current_value is None and not has_history:
        return None

    profit_loss = None
    if purchase_value is not None and current_value is not None:
        profit_loss = current_value - purchase_value

    price_change = None
    if previous_value is not None and current_value is not None:
        price_change = current_value - previous_value

    return {
        "purchase_value": purchase_value,
        "current_value": current_value,
        "profit_loss": profit_loss,
        "owned": purchase_value is not None,
        "previous_value": previous_value,
        "price_change": price_change,
    }


# Build card index entries and per-set history payloads in one pass.
def _build_card_index_and_histories(
    cards_df: pd.DataFrame,
    purchases: dict[str, float],
    histories: dict[str, list[dict]],
    default_snapshot: dict[str, float],
    card_locations: dict[str, list[dict]] | None = None,
) -> tuple[dict[str, dict], dict[str, dict[str, dict]], dict[str, list[str]]]:
    card_locations = card_locations or {}
    cards: dict[str, dict] = {}
    names: dict[str, list[str]] = {}
    set_histories: dict[str, dict[str, dict]] = {}

    for row in cards_df.itertuples(index=False):
        set_code = row.set_code
        collector_number = str(row.collector_number)
        key = print_key(set_code, collector_number)
        finishes: dict[str, dict] = {}
        set_bucket = set_histories.setdefault(set_code, {})

        for finish, market_value in (
            (0, row.market_value),
            (1, row.market_value_foil),
            (2, row.market_value_etched),
        ):
            finish_key = card_price_key(set_code, collector_number, finish)
            history = histories.get(finish_key)
            purchase_value = purchases.get(finish_key)
            current_value = _float_or_none(market_value)
            finish_data = _serialize_finish(
                purchase_value,
                current_value,
                has_history=bool(history),
                previous_value=default_snapshot.get(finish_key),
            )
            if finish_data is None:
                continue

            locations = card_locations.get(finish_key)
            if locations:
                finish_data["locations"] = locations

            finishes[str(finish)] = finish_data
            if history or purchase_value is not None or current_value is not None:
                chart = _build_chart_points(history or [], purchase_value, current_value)
                if history or chart:
                    set_bucket[f"{collector_number}|{finish}"] = {
                        "history": history or [],
                        "chart": chart,
                    }

        if not finishes:
            continue

        cards[key] = {
            "set_code": set_code,
            "collector_number": collector_number,
            "name": row.name,
            "art_style": row.art_style or "",
            "image_uri": row.image_uri or "",
            "cardmarket_url": row.cardmarket_url or "",
            **card_metadata_snake(row),
            "finishes": finishes,
        }
        names.setdefault(row.name, []).append(key)

    return cards, set_histories, names


# Build the lightweight card index and per-set history payloads.
def load_card_detail_assets() -> tuple[dict, dict[str, dict[str, dict]]]:
    with sqlite3.connect(DB_PATH) as conn:
        ensure_storage_tables(conn)
        ensure_card_columns(conn)
        cards_df = pd.read_sql_query(
            """
            SELECT
                set_code,
                collector_number,
                name,
                art_style,
                image_uri,
                cardmarket_url,
                colors,
                colors,
                type_line,
                card_type,
                market_value,
                market_value_foil
                ,market_value_etched
            FROM cards
            ORDER BY name, set_code, CAST(collector_number AS INTEGER), collector_number
            """,
            conn,
        )
        purchases = _load_purchases(conn)
        histories = _load_price_histories(conn)
        card_locations = _load_card_locations(conn)
        compare_payload, default_snapshot = load_card_detail_compare_context(conn)
        sets_catalog = load_sets_catalog(conn)

    cards, set_histories, names = _build_card_index_and_histories(
        cards_df,
        purchases,
        histories,
        default_snapshot,
        card_locations,
    )

    for card_name, keys in names.items():
        unique_keys = sorted(set(keys), key=lambda key: (
            cards[key]["set_code"],
            cards[key]["collector_number"],
        ))
        names[card_name] = unique_keys
        for key in unique_keys:
            cards[key]["variant_keys"] = unique_keys

    set_orders: dict[str, list[str]] = {}
    keys_by_set: dict[str, list[str]] = {}
    for key, card in cards.items():
        keys_by_set.setdefault(card["set_code"], []).append(key)
    for set_code, keys in keys_by_set.items():
        set_orders[set_code] = sorted(
            keys,
            key=lambda key: collector_sort_key(cards[key]["collector_number"]),
        )

    payload = {
        "cards": cards,
        "set_orders": set_orders,
        "sets": sets_catalog,
        "compareDates": compare_payload.get("compareDates", []),
        "currentDate": compare_payload.get("currentDate"),
        "defaultCompareDate": compare_payload.get("defaultCompareDate"),
    }
    return payload, set_histories


# Backwards-compatible alias for callers that only need the index payload.
def load_card_detail_payload() -> dict:
    payload, _history = load_card_detail_assets()
    return payload


# Build per-set history payloads for lazy loading on card detail pages.
def load_card_history_payloads() -> dict[str, dict[str, dict]]:
    _payload, history_payloads = load_card_detail_assets()
    return history_payloads


# Write one JS file per set containing price history and chart data.
def write_card_history_scripts(set_histories: dict[str, dict[str, dict]] | None = None) -> int:
    if set_histories is None:
        set_histories = load_card_history_payloads()

    out_dir = APP_CACHE_DIR / "card_histories"
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for set_code, payload in sorted(set_histories.items()):
        if not payload:
            continue
        path = out_dir / f"{set_code.upper()}.js"
        content = f"window.CARD_SET_HISTORY = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};"
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
        written += 1
    return written
