import sqlite3

import pandas as pd

from lib.config import DB_PATH
from util.alchemy_cards import exclude_alchemy_sql
from util.price_history import PriceSnapshotCache, card_price_key, load_price_snapshot_cache


DECK_CARDS_QUERY = f"""
SELECT
    dc.deck_id,
    d.name AS deck_name,
    d.slug AS deck_slug,
    d.purchase_price AS deck_purchase_price,
    dc.card_name,
    dc.set_code,
    dc.collector_number,
    dc.finish,
    dc.qty,
    dc.owned_qty,
    dc.section,
    dc.in_catalog,
    dc.sort_order,
    c.name AS catalog_name,
    c.art_style,
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.image_uri,
    c.cardmarket_url,
    c.cardmarket_url_foil,
    c.colors,
    c.type_line,
    c.card_type,
    c.color_identity,
    c.cmc,
    c.mana_cost,
    c.is_basic_land,
    p.purchase_value
FROM deck_cards dc
JOIN decks d ON d.deck_id = dc.deck_id
LEFT JOIN cards c
    ON c.set_code = dc.set_code
    AND c.collector_number = dc.collector_number
LEFT JOIN purchases p
    ON p.set_code = dc.set_code
    AND p.collector_number = dc.collector_number
    AND p.finish = dc.finish
WHERE dc.collector_number IS NULL
   OR {exclude_alchemy_sql("dc.collector_number")}
ORDER BY dc.deck_id, dc.sort_order
"""

DECK_LIST_QUERY = """
SELECT
    d.deck_id,
    d.name,
    d.slug,
    d.purchase_price,
    d.format,
    CAST(strftime('%Y', MAX(s.released_at)) AS INTEGER) AS release_year
FROM decks d
LEFT JOIN deck_cards dc
    ON dc.deck_id = d.deck_id
    AND dc.in_catalog = 1
LEFT JOIN sets s
    ON s.set_code = dc.set_code
GROUP BY d.deck_id
ORDER BY release_year, d.name
"""


def _float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


# Load deck catalog rows joined to cards and purchases.
def load_deck_cards_df(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    if conn is None:
        with sqlite3.connect(DB_PATH) as connection:
            return pd.read_sql_query(DECK_CARDS_QUERY, connection)
    return pd.read_sql_query(DECK_CARDS_QUERY, conn)


# Format one deck name for selectors and tables.
def format_deck_label(name: str, release_year: int | None) -> str:
    if release_year:
        return f"{release_year} - {name}"
    return name


# Load deck metadata for selectors and navigation.
def load_deck_list(conn: sqlite3.Connection | None = None) -> list[dict]:
    if conn is None:
        with sqlite3.connect(DB_PATH) as connection:
            rows = connection.execute(DECK_LIST_QUERY).fetchall()
    else:
        rows = conn.execute(DECK_LIST_QUERY).fetchall()
    return [
        {
            "id": deck_id,
            "name": name,
            "label": format_deck_label(name, release_year),
            "slug": slug,
            "format": deck_format or "commander",
            "releaseYear": int(release_year) if release_year is not None else None,
            "purchasePrice": float(purchase_price) if purchase_price is not None else None,
        }
        for deck_id, name, slug, purchase_price, deck_format, release_year in rows
    ]


# Load owned copy counts per print from card_instances and purchases.
def load_owned_count_by_print(conn: sqlite3.Connection) -> dict[tuple[str, str, int], int]:
    counts: dict[tuple[str, str, int], int] = {}
    instance_rows = conn.execute(
        """
        SELECT set_code, collector_number, finish, COUNT(*) AS owned_count
        FROM card_instances
        GROUP BY set_code, collector_number, finish
        """
    ).fetchall()
    for set_code, collector_number, finish, owned_count in instance_rows:
        key = (str(set_code).upper(), str(collector_number).strip(), int(finish))
        counts[key] = int(owned_count)

    purchase_rows = conn.execute(
        "SELECT set_code, collector_number, finish FROM purchases"
    ).fetchall()
    for set_code, collector_number, finish in purchase_rows:
        key = (str(set_code).upper(), str(collector_number).strip(), int(finish))
        counts.setdefault(key, 1)
    return counts


# Add derived pricing columns used by deck statistics.
def enrich_deck_cards_df(
    deck_df: pd.DataFrame,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    if deck_df.empty:
        return deck_df.copy()

    enriched = deck_df.copy()
    enriched["set_code"] = enriched["set_code"].where(enriched["set_code"].notna(), None)
    collector_numbers = enriched["collector_number"].where(
        enriched["collector_number"].notna(),
        None,
    )
    enriched["collector_number"] = collector_numbers.map(
        lambda value: str(value) if value is not None and not pd.isna(value) else None
    )

    catalog_matched = enriched["catalog_name"].notna()
    flagged_in_catalog = enriched["in_catalog"].fillna(0).astype(int) == 1
    in_catalog = flagged_in_catalog | catalog_matched
    enriched["in_catalog"] = in_catalog.astype(int)
    finish = enriched["finish"].fillna(0).astype(int)
    unit_value = pd.Series(pd.NA, index=enriched.index, dtype="Float64")
    unit_value.loc[in_catalog & (finish == 0)] = pd.to_numeric(
        enriched.loc[in_catalog & (finish == 0), "market_value"],
        errors="coerce",
    )
    unit_value.loc[in_catalog & (finish == 1)] = pd.to_numeric(
        enriched.loc[in_catalog & (finish == 1), "market_value_foil"],
        errors="coerce",
    )
    unit_value.loc[in_catalog & (finish == 2)] = pd.to_numeric(
        enriched.loc[in_catalog & (finish == 2), "market_value_etched"],
        errors="coerce",
    )
    enriched["unit_value"] = unit_value.astype(object).where(unit_value.notna(), None)

    purchase_value = pd.to_numeric(enriched["purchase_value"], errors="coerce")
    owned_qty = pd.to_numeric(enriched["owned_qty"], errors="coerce").fillna(0).astype(int)
    owned_qty = owned_qty.clip(lower=0)
    owned_qty = pd.concat([owned_qty, enriched["qty"].astype(int)], axis=1).min(axis=1)
    enriched["owned_qty"] = owned_qty.astype(int)

    owned_mask = enriched["owned_qty"] > 0
    current_value = unit_value.astype("float64") * enriched["qty"].astype("float64")
    enriched["current_value"] = current_value.where(unit_value.notna(), None)
    invested = purchase_value * enriched["owned_qty"].astype("float64")
    enriched["invested"] = invested.where(purchase_value.notna(), None)
    profit_loss = current_value - invested
    enriched["profit_loss"] = profit_loss.where(
        unit_value.notna() & owned_mask & purchase_value.notna(),
        None,
    )

    has_print = enriched["set_code"].notna() & enriched["collector_number"].notna()
    finish_key = pd.Series([None] * len(enriched), index=enriched.index, dtype=object)
    if has_print.any():
        finish_key.loc[has_print] = (
            enriched.loc[has_print, "set_code"].astype(str).str.upper()
            + "|"
            + enriched.loc[has_print, "collector_number"].astype(str)
            + "|"
            + enriched.loc[has_print, "finish"].fillna(0).astype(int).astype(str)
        )
    enriched["finish_key"] = finish_key
    return enriched


# Filter deck rows to one deck or keep all decks combined.
def deck_scope(deck_df: pd.DataFrame, deck_id: str | int | None) -> pd.DataFrame:
    if deck_id in (None, "", "All", "all"):
        return deck_df.copy()
    scoped = deck_df[deck_df["deck_id"] == int(deck_id)].copy()
    return scoped


# Build finish keys per deck for client-side filtering.
def build_deck_filter_payload(
    deck_df: pd.DataFrame,
    decks: list[dict],
) -> dict:
    deck_cards: dict[str, list[str]] = {"All": []}
    all_keys: set[str] = set()

    for deck in decks:
        deck_id = str(deck["id"])
        keys = []
        scoped = deck_df[deck_df["deck_id"] == deck["id"]]
        for finish_key in scoped["finish_key"].dropna().unique():
            key = str(finish_key)
            keys.append(key)
            all_keys.add(key)
        deck_cards[deck_id] = sorted(keys)

    deck_cards["All"] = sorted(all_keys)
    return {"deckCards": deck_cards}


# Load deck filter payload from the database.
def load_deck_filter_payload(conn: sqlite3.Connection) -> dict:
    deck_df = enrich_deck_cards_df(load_deck_cards_df(conn), conn)
    decks = load_deck_list(conn)
    return {
        "decks": decks,
        **build_deck_filter_payload(deck_df, decks),
    }


# Compute deck value history using market prices and deck quantities.
def compute_deck_portfolio_history(
    conn: sqlite3.Connection,
    deck_df: pd.DataFrame,
    *,
    snapshot_cache: PriceSnapshotCache | None = None,
) -> list[dict]:
    tracked = deck_df[
        deck_df["finish_key"].notna() & deck_df["unit_value"].notna()
    ].copy()
    if tracked.empty:
        return []

    cache = snapshot_cache or load_price_snapshot_cache(conn)
    dates = cache.dates
    if not dates:
        return []

    cards = []
    for _, row in tracked.iterrows():
        cards.append({
            "key": row["finish_key"],
            "qty": int(row["qty"]),
            "current_value": row["current_value"],
        })

    history: list[dict] = []
    for price_date in sorted(dates):
        price_map = cache.snapshots.get(price_date, {})

        total = 0.0
        has_value = False
        for card in cards:
            if price_date == dates[0]:
                value = card["current_value"]
            else:
                unit = price_map.get(card["key"])
                value = unit * card["qty"] if unit is not None else None
            if value is None:
                continue
            total += value
            has_value = True

        if has_value:
            history.append({"date": price_date, "value": total})

    if history and cards:
        latest_value = sum(
            card["current_value"] for card in cards if card["current_value"] is not None
        )
        if history[-1]["date"] != dates[0]:
            history.append({"date": dates[0], "value": latest_value})
    return history
