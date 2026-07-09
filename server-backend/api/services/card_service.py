import sqlite3

from report.card_detail_data import collector_sort_key
from report.report_data import format_set_option_label, get_set_display_names
from report.serialize_helpers import deck_card_display_name
from api.services import settings_service
from api.services import manager_service
from api.services.pricing_service import (
    all_guide_prices_for_card,
    list_price_strategies,
    price_from_strategy,
)
from util.cardmarket_urls import cardmarket_url_for_finish
from util.price_history import (
    card_price_key,
    load_snapshot_prices,
)
from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    GUIDE_PRICE_GROUPS,
    finish_available,
    finish_has_pricing,
)
from util.card_metadata import card_metadata_api
from util.db_migrate import ensure_card_columns
from util.set_catalog import load_sets_catalog
from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql, is_alchemy_collector_number

CARD_QUERY = f"""
SELECT
    set_code,
    collector_number,
    name,
    art_style,
    image_uri,
    cardmarket_url,
    cardmarket_url_foil,
    market_value,
    market_value_foil,
    market_value_etched,
    has_nonfoil,
    has_foil,
    has_etched,
    colors,
    type_line,
    card_type
FROM cards
WHERE set_code = ? AND collector_number = ? AND {exclude_alchemy_sql()} AND {exclude_alchemy_art_style_sql()}
"""


class CardError(Exception):
    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def load_card_detail(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    *,
    finish: int | None = None,
) -> dict:
    normalized_set = set_code.strip().upper()
    normalized_number = str(collector_number).strip()
    if is_alchemy_collector_number(normalized_number):
        raise CardError("Card not found")
    ensure_card_columns(conn)
    row = conn.execute(CARD_QUERY, (normalized_set, normalized_number)).fetchone()
    if row is None:
        raise CardError("Card not found")

    settings = settings_service.get_settings(conn)
    strategy = settings["priceStrategy"]
    selected_compare = settings_service.resolve_compare_date(conn)
    previous_snapshot = _snapshot_map(conn, selected_compare)

    purchases = _load_print_purchases(conn, normalized_set, normalized_number)
    locations = _load_print_locations(conn, normalized_set, normalized_number)
    guide_prices = all_guide_prices_for_card(
        row["cardmarket_url"],
        row["cardmarket_url_foil"],
    )

    finishes: dict[str, dict] = {}
    requested_finish = finish
    for finish_id in (FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED):
        purchase_value = purchases.get(finish_id)
        finish_locations = locations.get(finish_id, [])
        is_owned = purchase_value is not None or bool(finish_locations)
        if not is_owned and not finish_available(row, finish_id, guide_prices=guide_prices):
            continue
        finish_key = card_price_key(normalized_set, normalized_number, finish_id)
        current_value = price_from_strategy(
            row["cardmarket_url"],
            finish_id,
            strategy,
            cardmarket_url_foil=row["cardmarket_url_foil"],
            market_value=_float_or_none(row["market_value"]),
            market_value_foil=_float_or_none(row["market_value_foil"]),
            market_value_etched=_float_or_none(row["market_value_etched"]),
        )
        previous_value = previous_snapshot.get(finish_key)
        price_change = None
        if current_value is not None and previous_value is not None:
            price_change = current_value - previous_value
        profit_loss = None
        if purchase_value is not None and current_value is not None:
            profit_loss = current_value - purchase_value
        finishes[str(finish_id)] = {
            "finish": finish_id,
            "foil": finish_id,
            "owned": purchase_value is not None or bool(finish_locations),
            "purchaseValue": purchase_value,
            "currentValue": current_value,
            "profitLoss": profit_loss,
            "previousValue": previous_value,
            "priceChange": price_change,
            "locations": finish_locations,
            "guidePrices": guide_prices.get(GUIDE_PRICE_GROUPS[finish_id], {}),
        }

    if not finishes:
        raise CardError("Card has no tracked finishes")

    selected_finish = requested_finish if requested_finish is not None else _default_finish(finishes)
    if str(selected_finish) not in finishes:
        selected_finish = int(next(iter(finishes)))

    set_names = get_set_display_names()
    sets_catalog = load_sets_catalog(conn)
    set_info = sets_catalog.get(normalized_set, {})
    ownership_payload = manager_service.load_owned_instances_for_print(
        conn,
        normalized_set,
        normalized_number,
        strategy=strategy,
    )

    return {
        "setCode": normalized_set,
        "collectorNumber": normalized_number,
        "name": deck_card_display_name({
            "catalog_name": row["name"],
            "card_name": row["name"],
            "set_code": normalized_set,
            "collector_number": normalized_number,
        }),
        "artStyle": row["art_style"] or "",
        "imageUri": row["image_uri"] or "",
        "hasNonfoil": bool(row["has_nonfoil"]),
        "hasFoil": bool(row["has_foil"]),
        "hasEtched": bool(row["has_etched"]),
        "cardmarketUrl": cardmarket_url_for_finish(row, selected_finish) or "",
        **card_metadata_api(row),
        "setLabel": format_set_option_label(normalized_set, set_names),
        "setReleasedAt": set_info.get("released_at"),
        "priceStrategy": strategy,
        "compareDate": selected_compare,
        "selectedFinish": selected_finish,
        "finishes": finishes,
        "guidePriceMatrix": _guide_price_matrix(
            guide_prices,
            stored_etched=_float_or_none(row["market_value_etched"])
            if finish_has_pricing(row, FINISH_ETCHED, guide_prices)
            else None,
            price_strategy=strategy,
        ),
        "variantGallery": _load_variant_gallery(
            conn,
            row["name"],
            normalized_set,
            normalized_number,
            strategy=strategy,
            set_names=set_names,
        ),
        "setGallery": _load_set_gallery(
            conn,
            normalized_set,
            normalized_number,
            strategy=strategy,
            set_names=set_names,
        ),
        **ownership_payload,
    }


def _guide_price_matrix(
    guide_prices: dict,
    *,
    stored_etched: float | None = None,
    price_strategy: str = "trend",
) -> dict:
    rows = []
    for strategy in list_price_strategies():
        strategy_id = strategy["id"]
        etched = stored_etched if stored_etched is not None and strategy_id == price_strategy else None
        rows.append({
            "strategyId": strategy_id,
            "label": strategy["label"],
            "nonfoil": guide_prices.get("nonfoil", {}).get(strategy_id),
            "foil": guide_prices.get("foil", {}).get(strategy_id),
            "etched": etched,
        })
    return {
        "strategies": list_price_strategies(),
        "rows": rows,
    }


def _default_finish(finishes: dict[str, dict]) -> int:
    if "0" in finishes:
        return 0
    return int(next(iter(finishes)))


def _load_print_purchases(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
) -> dict[int, float]:
    rows = conn.execute(
        """
        SELECT finish, purchase_value
        FROM purchases
        WHERE set_code = ? AND collector_number = ?
        """,
        (set_code, collector_number),
    ).fetchall()
    return {int(finish): float(purchase_value) for finish, purchase_value in rows}


def _load_print_locations(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
) -> dict[int, list[dict]]:
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
    ).fetchone()
    if not table:
        return {}

    rows = conn.execute(
        """
        SELECT
            ci.finish,
            ci.location_slug,
            sl.label,
            sl.location_type,
            COUNT(*) AS copy_count
        FROM card_instances ci
        JOIN storage_locations sl ON sl.location_slug = ci.location_slug
        WHERE ci.set_code = ? AND ci.collector_number = ?
        GROUP BY ci.finish, ci.location_slug
        ORDER BY sl.sort_order, sl.label
        """,
        (set_code, collector_number),
    ).fetchall()

    locations: dict[int, list[dict]] = {}
    for finish, slug, label, location_type, copy_count in rows:
        locations.setdefault(int(finish), []).append({
            "slug": slug,
            "label": label,
            "locationType": location_type,
            "count": int(copy_count),
        })
    return locations


def _snapshot_map(conn: sqlite3.Connection, compare_date: str | None) -> dict[str, float]:
    if not compare_date:
        return {}
    price_df = load_snapshot_prices(conn, compare_date)
    if price_df.empty:
        return {}
    return {
        card_price_key(row.set_code, row.collector_number, row.finish): float(row.previous_value)
        for row in price_df.itertuples(index=False)
    }


def _load_set_gallery(
    conn: sqlite3.Connection,
    set_code: str,
    collector_number: str,
    *,
    strategy: str,
    set_names: dict[str, str],
) -> dict:
    rows = conn.execute(
        f"""
        SELECT
            set_code,
            collector_number,
            name,
            art_style,
            image_uri,
            cardmarket_url,
            cardmarket_url_foil,
            market_value,
            market_value_foil,
            market_value_etched,
            colors,
            type_line,
            card_type
        FROM cards
        WHERE set_code = ?
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        """,
        (set_code,),
    ).fetchall()
    ordered = sorted(rows, key=lambda row: collector_sort_key(str(row["collector_number"])))
    cards = []
    current_index = 0
    for index, row in enumerate(ordered):
        is_current = str(row["collector_number"]) == str(collector_number)
        if is_current:
            current_index = index
        cards.append(_serialize_gallery_card(row, strategy=strategy, set_names=set_names, is_current=is_current))
    return {"cards": cards, "currentIndex": current_index}


def _load_variant_gallery(
    conn: sqlite3.Connection,
    name: str,
    set_code: str,
    collector_number: str,
    *,
    strategy: str,
    set_names: dict[str, str],
) -> dict:
    rows = conn.execute(
        f"""
        SELECT
            set_code,
            collector_number,
            name,
            art_style,
            image_uri,
            cardmarket_url,
            cardmarket_url_foil,
            market_value,
            market_value_foil,
            market_value_etched,
            colors,
            type_line,
            card_type
        FROM cards
        WHERE name = ?
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        ORDER BY set_code, collector_number
        """,
        (name,),
    ).fetchall()
    if len(rows) <= 1:
        return {"cards": [], "currentIndex": -1}

    cards = []
    current_index = -1
    for index, row in enumerate(rows):
        is_current = row["set_code"] == set_code and str(row["collector_number"]) == str(collector_number)
        if is_current:
            current_index = index
        cards.append(_serialize_gallery_card(row, strategy=strategy, set_names=set_names, is_current=is_current))
    return {"cards": cards, "currentIndex": current_index}


def _serialize_gallery_card(
    row: sqlite3.Row,
    *,
    strategy: str,
    set_names: dict[str, str],
    is_current: bool,
) -> dict:
    nonfoil_value = price_from_strategy(
        row["cardmarket_url"],
        0,
        strategy,
        cardmarket_url_foil=row["cardmarket_url_foil"],
        market_value=_float_or_none(row["market_value"]),
        market_value_foil=_float_or_none(row["market_value_foil"]),
        market_value_etched=_float_or_none(row["market_value_etched"]),
    )
    foil_value = price_from_strategy(
        row["cardmarket_url"],
        1,
        strategy,
        cardmarket_url_foil=row["cardmarket_url_foil"],
        market_value=_float_or_none(row["market_value"]),
        market_value_foil=_float_or_none(row["market_value_foil"]),
        market_value_etched=_float_or_none(row["market_value_etched"]),
    )
    etched_value = price_from_strategy(
        row["cardmarket_url"],
        2,
        strategy,
        cardmarket_url_foil=row["cardmarket_url_foil"],
        market_value=_float_or_none(row["market_value"]),
        market_value_foil=_float_or_none(row["market_value_foil"]),
        market_value_etched=_float_or_none(row["market_value_etched"]),
    )
    return {
        "setCode": row["set_code"],
        "collectorNumber": str(row["collector_number"]),
        "name": deck_card_display_name({
            "catalog_name": row["name"],
            "card_name": row["name"],
            "set_code": row["set_code"],
            "collector_number": row["collector_number"],
        }),
        "artStyle": row["art_style"] or "",
        "imageUri": row["image_uri"] or "",
        **card_metadata_api(row),
        "setLabel": format_set_option_label(row["set_code"], set_names),
        "currentValueNonfoil": nonfoil_value,
        "currentValueFoil": foil_value,
        "currentValueEtched": etched_value,
        "isCurrent": is_current,
    }


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)
