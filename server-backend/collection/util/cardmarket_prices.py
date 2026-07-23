import json
import logging
import math
import pickle
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from lib.config import DATA_DIR, DB_PATH, HTTP_USER_AGENT
from lib.run_log import get_logger
from util.card_prices import (
    record_card_price,
    snapshot_owned_cardmarket_prices,
)
from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    MARKET_VALUE_COLUMNS,
    guide_uses_foil_keys,
    normalize_finish,
)
from util.db_migrate import ensure_card_columns
from util.http_client import http_get

log = get_logger(__name__)

_GUIDE_INDEX_MEMORY: dict[int, dict] | None = None
_PRICE_GUIDE_CACHE_LOGGED = False


def invalidate_price_guide_memory_cache() -> None:
    global _GUIDE_INDEX_MEMORY, _PRICE_GUIDE_CACHE_LOGGED
    _GUIDE_INDEX_MEMORY = None
    _PRICE_GUIDE_CACHE_LOGGED = False

PRICE_GUIDE_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json"
PRICE_GUIDE_CACHE = DATA_DIR / "cardmarket_price_guide.json"
PRICE_GUIDE_INDEX_CACHE = DATA_DIR / "cardmarket_price_guide.pkl"
PRICE_GUIDE_MAX_AGE = timedelta(hours=24)
_PRODUCT_ID_PATTERN = re.compile(r"idProduct=(\d+)", re.IGNORECASE)
REQUEST_HEADERS = {
    "User-Agent": HTTP_USER_AGENT,
}

PRIMARY_NONFOIL_KEYS = ("trend", "avg", "avg7", "avg30", "avg1")
PRIMARY_FOIL_KEYS = ("trend-foil", "avg-foil", "avg7-foil", "avg30-foil", "avg1-foil")
NONFOIL_PRICE_KEYS = PRIMARY_NONFOIL_KEYS + ("low",)
FOIL_PRICE_KEYS = PRIMARY_FOIL_KEYS + ("low-foil",)

UNOWNED_PRICE_MIN_CARDS = 25
UNOWNED_PRICE_SET_FRACTION = 0.25

OWNED_FINISH_SUBQUERY = """
    SELECT set_code, collector_number, finish FROM purchases
    UNION
    SELECT set_code, collector_number, finish
    FROM deck_cards
    WHERE owned_qty > 0
      AND set_code IS NOT NULL
      AND collector_number IS NOT NULL
"""

OWNED_PRINT_EXISTS_CLAUSE = """
    EXISTS (
        SELECT 1
        FROM purchases p
        WHERE p.set_code = cards.set_code
          AND p.collector_number = cards.collector_number
    )
    OR EXISTS (
        SELECT 1
        FROM deck_cards dc
        WHERE dc.set_code = cards.set_code
          AND dc.collector_number = cards.collector_number
          AND dc.owned_qty > 0
    )
"""


def _deck_cards_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'deck_cards'"
    ).fetchone()
    return row is not None


def _load_owned_finishes(conn: sqlite3.Connection) -> frozenset[tuple[str, str, int]]:
    if _deck_cards_table_exists(conn):
        rows = conn.execute(
            f"SELECT set_code, collector_number, finish FROM ({OWNED_FINISH_SUBQUERY})"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT set_code, collector_number, finish FROM purchases"
        ).fetchall()
    return frozenset(
        (set_code.upper(), str(collector_number), int(finish))
        for set_code, collector_number, finish in rows
    )


def _load_set_owned_counts(conn: sqlite3.Connection) -> dict[str, int]:
    if _deck_cards_table_exists(conn):
        query = f"""
            SELECT set_code, COUNT(*) AS owned_count
            FROM ({OWNED_FINISH_SUBQUERY})
            GROUP BY set_code
        """
    else:
        query = """
            SELECT set_code, COUNT(*) AS owned_count
            FROM purchases
            GROUP BY set_code
        """
    rows = conn.execute(query).fetchall()
    return {
        set_code.upper(): int(owned_count)
        for set_code, owned_count in rows
    }


def _owned_finish_exists_clause(finish: int, *, include_deck: bool) -> str:
    purchase_clause = f"""
        EXISTS (
            SELECT 1
            FROM purchases p
            WHERE p.set_code = cards.set_code
              AND p.collector_number = cards.collector_number
              AND p.finish = {int(finish)}
        )
    """
    if not include_deck:
        return purchase_clause
    return f"""
        {purchase_clause}
        OR EXISTS (
            SELECT 1
            FROM deck_cards dc
            WHERE dc.set_code = cards.set_code
              AND dc.collector_number = cards.collector_number
              AND dc.finish = {int(finish)}
              AND dc.owned_qty > 0
        )
    """


def _owned_print_exists_clause(*, include_deck: bool) -> str:
    if not include_deck:
        return """
            EXISTS (
                SELECT 1
                FROM purchases p
                WHERE p.set_code = cards.set_code
                  AND p.collector_number = cards.collector_number
            )
        """
    return OWNED_PRINT_EXISTS_CLAUSE


@dataclass(frozen=True)
class PriceSyncContext:
    owned_finishes: frozenset[tuple[str, str, int]]
    qualifying_sets: frozenset[str]
    set_owned_counts: dict[str, int]
    set_catalog_sizes: dict[str, int]


# Return the minimum owned-card count required before unowned prices are synced.
def unowned_price_threshold(set_size: int) -> int:
    if set_size <= 0:
        return UNOWNED_PRICE_MIN_CARDS
    return min(
        UNOWNED_PRICE_MIN_CARDS,
        math.ceil(set_size * UNOWNED_PRICE_SET_FRACTION),
    )


# Load ownership stats and the sets that qualify for unowned price sync.
def load_price_sync_context(
    conn: sqlite3.Connection,
    set_codes: set[str] | None = None,
) -> PriceSyncContext:
    owned_finishes = _load_owned_finishes(conn)

    catalog_rows = conn.execute(
        """
        SELECT set_code, COUNT(*) AS catalog_size
        FROM cards
        GROUP BY set_code
        """
    ).fetchall()
    set_catalog_sizes = {
        set_code.upper(): int(catalog_size)
        for set_code, catalog_size in catalog_rows
    }

    set_owned_counts = _load_set_owned_counts(conn)

    candidate_sets = set_codes or set(set_catalog_sizes)
    qualifying_sets: set[str] = set()
    for set_code in candidate_sets:
        code = set_code.upper()
        catalog_size = set_catalog_sizes.get(code, 0)
        owned_count = set_owned_counts.get(code, 0)
        if owned_count >= unowned_price_threshold(catalog_size):
            qualifying_sets.add(code)

    return PriceSyncContext(
        owned_finishes=owned_finishes,
        qualifying_sets=frozenset(qualifying_sets),
        set_owned_counts=set_owned_counts,
        set_catalog_sizes=set_catalog_sizes,
    )


# Return True when one finish should receive Cardmarket price updates.
def should_sync_finish(
    set_code: str,
    collector_number: str,
    finish: int,
    context: PriceSyncContext,
) -> bool:
    finish_id = normalize_finish(finish)
    finish_key = (set_code.upper(), str(collector_number), finish_id)
    if finish_key in context.owned_finishes:
        return True
    return set_code.upper() in context.qualifying_sets


# Clear stored prices for unowned finishes in sets below the unowned threshold.
def clear_unowned_prices_for_non_qualifying_sets(
    conn: sqlite3.Connection,
    context: PriceSyncContext,
    set_codes: set[str] | None = None,
) -> int:
    candidate_sets = set_codes or set(context.set_catalog_sizes)
    non_qualifying = {
        set_code.upper()
        for set_code in candidate_sets
        if set_code.upper() not in context.qualifying_sets
    }
    if not non_qualifying:
        return 0

    include_deck = _deck_cards_table_exists(conn)
    placeholders = ",".join("?" for _ in non_qualifying)
    params = tuple(sorted(non_qualifying))
    cleared = 0
    cleared += conn.execute(
        f"""
        UPDATE cards
        SET market_value = NULL
        WHERE set_code IN ({placeholders})
          AND market_value IS NOT NULL
          AND NOT ({_owned_finish_exists_clause(0, include_deck=include_deck)})
        """,
        params,
    ).rowcount
    cleared += conn.execute(
        f"""
        UPDATE cards
        SET market_value_foil = NULL
        WHERE set_code IN ({placeholders})
          AND market_value_foil IS NOT NULL
          AND NOT ({_owned_finish_exists_clause(1, include_deck=include_deck)})
        """,
        params,
    ).rowcount
    cleared += conn.execute(
        f"""
        UPDATE cards
        SET market_value_etched = NULL
        WHERE set_code IN ({placeholders})
          AND market_value_etched IS NOT NULL
          AND NOT ({_owned_finish_exists_clause(FINISH_ETCHED, include_deck=include_deck)})
        """,
        params,
    ).rowcount
    return cleared


# Parse a Cardmarket product id from a purchase or product URL.
def parse_id_product(url: str) -> int | None:
    if not url:
        return None
    match = _PRODUCT_ID_PATTERN.search(url)
    if match:
        return int(match.group(1))
    query = parse_qs(urlparse(url).query)
    if "idProduct" in query:
        return int(query["idProduct"][0])
    return None


def _load_guide_index_cache() -> dict[int, dict] | None:
    if not PRICE_GUIDE_INDEX_CACHE.is_file() or not PRICE_GUIDE_CACHE.is_file():
        return None
    if PRICE_GUIDE_INDEX_CACHE.stat().st_mtime < PRICE_GUIDE_CACHE.stat().st_mtime:
        return None
    with PRICE_GUIDE_INDEX_CACHE.open("rb") as handle:
        return pickle.load(handle)


def _save_guide_index_cache(guide: dict[int, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with PRICE_GUIDE_INDEX_CACHE.open("wb") as handle:
        pickle.dump(guide, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _invalidate_guide_index_cache() -> None:
    if PRICE_GUIDE_INDEX_CACHE.is_file():
        PRICE_GUIDE_INDEX_CACHE.unlink()
    invalidate_price_guide_memory_cache()


# Return True when a non-foil low price is not just a foil listing floor.
def _nonfoil_low_is_reliable(entry: dict, low: float) -> bool:
    if any(entry.get(key) not in (None, 0) and entry.get(key) > 0 for key in PRIMARY_NONFOIL_KEYS):
        return True
    trend_foil = entry.get("trend-foil") or 0
    if trend_foil > 0 and low >= trend_foil * 0.5:
        return False
    return True


# Return the Cardmarket trend for a finish, or None when that exact field is missing.
# Never cascades to avg/low or across finish key groups — missing trend means unknown.
def price_from_guide_entry(entry: dict, finish: int | bool) -> float | None:
    finish_id = normalize_finish(finish)
    if finish_id == FINISH_ETCHED:
        # No dedicated etched metric. Only accept foil trend when the product has
        # no nonfoil trend (etched-only Cardmarket product shape).
        nonfoil_trend = entry.get("trend")
        foil_trend = entry.get("trend-foil")
        if nonfoil_trend not in (None, 0) and float(nonfoil_trend) > 0:
            return None
        if foil_trend is None or foil_trend <= 0:
            return None
        return float(foil_trend)
    return _price_from_guide_keys(entry, use_foil_keys=guide_uses_foil_keys(finish_id))


def _price_from_guide_keys(entry: dict, *, use_foil_keys: bool) -> float | None:
    key = "trend-foil" if use_foil_keys else "trend"
    value = entry.get(key)
    if value is None or value <= 0:
        return None
    return float(value)


# Download the Cardmarket price guide when the cache is missing or stale.
def ensure_price_guide(force: bool = False, logger: logging.Logger | None = None) -> Path:
    global _PRICE_GUIDE_CACHE_LOGGED
    request_log = logger or log
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not force and PRICE_GUIDE_CACHE.is_file():
        age = datetime.now() - datetime.fromtimestamp(PRICE_GUIDE_CACHE.stat().st_mtime)
        if age < PRICE_GUIDE_MAX_AGE:
            if not _PRICE_GUIDE_CACHE_LOGGED:
                request_log.info("Using cached Cardmarket price guide: %s", PRICE_GUIDE_CACHE)
                _PRICE_GUIDE_CACHE_LOGGED = True
            return PRICE_GUIDE_CACHE

    response = http_get(
        PRICE_GUIDE_URL,
        headers=REQUEST_HEADERS,
        timeout=120,
        logger=request_log,
        label="Cardmarket price guide",
    )
    response.raise_for_status()
    PRICE_GUIDE_CACHE.write_bytes(response.content)
    _invalidate_guide_index_cache()
    request_log.info("Saved Cardmarket price guide to %s", PRICE_GUIDE_CACHE)
    return PRICE_GUIDE_CACHE


# Load the Cardmarket price guide indexed by product id.
def load_price_guide_index(
    force_download: bool = False,
    logger: logging.Logger | None = None,
) -> dict[int, dict]:
    global _GUIDE_INDEX_MEMORY
    request_log = logger or log
    if not force_download and _GUIDE_INDEX_MEMORY is not None:
        return _GUIDE_INDEX_MEMORY

    ensure_price_guide(force=force_download, logger=request_log)
    if force_download:
        _invalidate_guide_index_cache()
    cached = _load_guide_index_cache()
    if cached is not None:
        if _GUIDE_INDEX_MEMORY is None:
            request_log.info(
                "Loaded %s products from Cardmarket price guide index cache",
                len(cached),
            )
        _GUIDE_INDEX_MEMORY = cached
        return cached
    data = json.loads(PRICE_GUIDE_CACHE.read_text(encoding="utf-8"))
    guide = {entry["idProduct"]: entry for entry in data["priceGuides"]}
    _save_guide_index_cache(guide)
    request_log.info("Loaded %s products from Cardmarket price guide", len(guide))
    _GUIDE_INDEX_MEMORY = guide
    return guide


# Look up a Cardmarket trend or fallback price for one product.
def lookup_cardmarket_price(
    cardmarket_url: str,
    finish: int | bool,
    force_download: bool = False,
    guide: dict[int, dict] | None = None,
) -> float | None:
    product_id = parse_id_product(cardmarket_url)
    if product_id is None:
        return None
    if guide is None:
        guide = load_price_guide_index(force_download=force_download)
    entry = guide.get(product_id)
    if not entry:
        return None
    return price_from_guide_entry(entry, finish)


# Persist a fetched Cardmarket price on the matching card row.
def update_card_price_in_db(
    set_code: str,
    collector_number: str,
    finish: int,
    price: float,
    conn: sqlite3.Connection | None = None,
    price_date: str | None = None,
) -> None:
    finish_id = normalize_finish(finish)
    column = MARKET_VALUE_COLUMNS[finish_id]
    sql = f"""
        UPDATE cards
        SET {column} = ?
        WHERE set_code = ? AND collector_number = ?
    """
    params = (price, set_code.upper(), str(collector_number))
    if conn is None:
        with sqlite3.connect(DB_PATH) as own_conn:
            own_conn.execute(sql, params)
            if price_date:
                record_card_price(
                    own_conn, set_code, collector_number, finish_id, price, "cardmarket", price_date,
                )
            own_conn.commit()
        return
    conn.execute(sql, params)
    if price_date:
        record_card_price(
            conn, set_code, collector_number, finish_id, price, "cardmarket", price_date,
        )


# Clear one stored market value when the price guide has no reliable price.
def clear_card_price_in_db(
    set_code: str,
    collector_number: str,
    finish: int,
    conn: sqlite3.Connection,
) -> None:
    column = MARKET_VALUE_COLUMNS[normalize_finish(finish)]
    conn.execute(
        f"""
        UPDATE cards
        SET {column} = NULL
        WHERE set_code = ? AND collector_number = ?
        """,
        (set_code.upper(), str(collector_number)),
    )


# List cards whose prices should be checked against the Cardmarket guide.
def list_cards_for_price_sync(
    set_codes: set[str] | None = None,
    qualifying_sets: set[str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[sqlite3.Row]:
    query = """
        SELECT
            set_code,
            collector_number,
            market_value,
            market_value_foil,
            market_value_etched,
            cardmarket_url,
            cardmarket_url_foil,
            has_nonfoil,
            has_foil,
            has_etched
        FROM cards
        WHERE (cardmarket_url IS NOT NULL AND TRIM(cardmarket_url) != '')
           OR (cardmarket_url_foil IS NOT NULL AND TRIM(cardmarket_url_foil) != '')
    """
    params: list[str] = []
    if set_codes:
        placeholders = ",".join("?" for _ in set_codes)
        query += f" AND set_code IN ({placeholders})"
        params.extend(sorted(code.upper() for code in set_codes))
    if qualifying_sets is not None:
        if conn is not None:
            include_deck = _deck_cards_table_exists(conn)
        else:
            with sqlite3.connect(DB_PATH) as own_conn:
                include_deck = _deck_cards_table_exists(own_conn)
        owned_clause = _owned_print_exists_clause(include_deck=include_deck)
        if qualifying_sets:
            placeholders = ",".join("?" for _ in qualifying_sets)
            query += f" AND ({owned_clause} OR set_code IN ({placeholders}))"
            params.extend(sorted(code.upper() for code in qualifying_sets))
        else:
            query += f" AND {owned_clause}"
    query += " ORDER BY set_code, CAST(collector_number AS INTEGER), collector_number"

    if conn is None:
        with sqlite3.connect(DB_PATH) as own_conn:
            own_conn.row_factory = sqlite3.Row
            return own_conn.execute(query, params).fetchall()

    row_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.row_factory = row_factory


# Try to resolve one finish from a Cardmarket guide entry.
def lookup_guide_price(
    entry: dict | None,
    finish: int | bool,
) -> float | None:
    if not entry:
        return None
    return price_from_guide_entry(entry, finish)


# Try to resolve one finish from the in-memory Cardmarket guide.
def lookup_missing_finish(
    cardmarket_url: str,
    finish: int | bool,
    guide: dict[int, dict],
) -> float | None:
    product_id = parse_id_product(cardmarket_url)
    if product_id is None:
        return None
    return lookup_guide_price(guide.get(product_id), finish)


def _finish_enabled(row: sqlite3.Row, finish: int) -> bool:
    finish_id = normalize_finish(finish)
    column = {
        FINISH_NONFOIL: "has_nonfoil",
        FINISH_FOIL: "has_foil",
        FINISH_ETCHED: "has_etched",
    }[finish_id]
    flag = row[column]
    if flag is None:
        return False
    return int(flag) == 1


def _values_equal(current_value, price: float) -> bool:
    return current_value is not None and float(current_value) == float(price)


def _bulk_update_market_values(
    conn: sqlite3.Connection,
    updates: list[tuple[float, str, str]],
    column: str,
) -> None:
    if not updates:
        return
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS _cm_sync_updates (
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            price REAL NOT NULL,
            PRIMARY KEY (set_code, collector_number)
        )
        """,
    )
    conn.execute("DELETE FROM _cm_sync_updates")
    conn.executemany(
        "INSERT INTO _cm_sync_updates (price, set_code, collector_number) VALUES (?, ?, ?)",
        updates,
    )
    conn.execute(
        f"""
        UPDATE cards
        SET {column} = (
            SELECT u.price
            FROM _cm_sync_updates u
            WHERE u.set_code = cards.set_code
              AND u.collector_number = cards.collector_number
        )
        WHERE EXISTS (
            SELECT 1
            FROM _cm_sync_updates u
            WHERE u.set_code = cards.set_code
              AND u.collector_number = cards.collector_number
        )
        """,
    )


def _bulk_clear_market_values(
    conn: sqlite3.Connection,
    clears: list[tuple[str, str]],
    column: str,
) -> None:
    if not clears:
        return
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS _cm_sync_clears (
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            PRIMARY KEY (set_code, collector_number)
        )
        """,
    )
    conn.execute("DELETE FROM _cm_sync_clears")
    conn.executemany(
        "INSERT INTO _cm_sync_clears (set_code, collector_number) VALUES (?, ?)",
        clears,
    )
    conn.execute(
        f"""
        UPDATE cards
        SET {column} = NULL
        WHERE EXISTS (
            SELECT 1
            FROM _cm_sync_clears c
            WHERE c.set_code = cards.set_code
              AND c.collector_number = cards.collector_number
        )
        """,
    )


# Apply batched card and history updates collected during one sync pass.
def _apply_price_sync_batches(
    conn: sqlite3.Connection,
    today: str,
    *,
    updates_by_finish: dict[int, list[tuple[float, str, str]]],
    clears_by_finish: dict[int, list[tuple[str, str]]],
) -> None:
    for finish_id, updates in updates_by_finish.items():
        if updates:
            _bulk_update_market_values(conn, updates, MARKET_VALUE_COLUMNS[finish_id])
    for finish_id, clears in clears_by_finish.items():
        if clears:
            _bulk_clear_market_values(conn, clears, MARKET_VALUE_COLUMNS[finish_id])
    snapshot_owned_cardmarket_prices(conn, today)


# Update card market values from the Cardmarket price guide.
def sync_prices_from_guide(
    today: str,
    *,
    set_codes: set[str] | None = None,
    force_download: bool = False,
    missing_only: bool = False,
    log=None,
) -> dict:
    out = log if log is not None else get_logger(__name__)
    guide = load_price_guide_index(force_download=force_download, logger=out)
    from util.cardmarket_urls import backfill_cardmarket_urls, cardmarket_url_for_finish

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = sqlite3.Row
        ensure_card_columns(conn)
        backfilled_urls = backfill_cardmarket_urls(conn, guide)
        if backfilled_urls:
            out.info("Backfilled Cardmarket URLs for %s cards", backfilled_urls)
        context = load_price_sync_context(conn, set_codes)
        cleared_unowned = clear_unowned_prices_for_non_qualifying_sets(
            conn, context, set_codes,
        )
        rows = list_cards_for_price_sync(
            set_codes,
            context.qualifying_sets,
            conn=conn,
        )

        if cleared_unowned:
            out.info(
                "Cleared %s unowned price value(s) in sets below the unowned sync threshold",
                cleared_unowned,
            )

        if not rows:
            conn.commit()
            out.info("No cards with a Cardmarket URL to price.")
            return {
                "queried_cards": 0,
                "updated_fields": 0,
                "still_missing_fields": 0,
                "unchanged_fields": 0,
                "cleared_fields": cleared_unowned,
                "cleared_unowned_fields": cleared_unowned,
                "qualifying_sets": len(context.qualifying_sets),
            }

        mode = "missing values" if missing_only else "owned plus qualifying unowned cards"
        out.info(
            "Updating Cardmarket prices for %s cards (%s; %s qualifying set(s))...",
            len(rows),
            mode,
            len(context.qualifying_sets),
        )
        totals = {
            "queried_cards": len(rows),
            "updated_fields": 0,
            "cleared_fields": cleared_unowned,
            "cleared_unowned_fields": cleared_unowned,
            "still_missing_fields": 0,
            "unchanged_fields": 0,
            "qualifying_sets": len(context.qualifying_sets),
        }
        set_stats: dict[str, dict[str, int]] = {}
        updates_by_finish: dict[int, list[tuple[float, str, str]]] = {
            FINISH_NONFOIL: [],
            FINISH_FOIL: [],
            FINISH_ETCHED: [],
        }
        clears_by_finish: dict[int, list[tuple[str, str]]] = {
            FINISH_NONFOIL: [],
            FINISH_FOIL: [],
            FINISH_ETCHED: [],
        }

        for row in rows:
            finish_rows = (
                (FINISH_NONFOIL, row["market_value"]),
                (FINISH_FOIL, row["market_value_foil"]),
                (FINISH_ETCHED, row["market_value_etched"]),
            )
            card_set = row["set_code"]
            collector_number = str(row["collector_number"])
            stats = set_stats.setdefault(
                card_set,
                {"queried": 0, "updated": 0, "still_missing": 0, "unchanged": 0},
            )
            stats["queried"] += 1

            for finish_id, current_value in finish_rows:
                if not _finish_enabled(row, finish_id):
                    continue
                if not should_sync_finish(
                    card_set, collector_number, finish_id, context,
                ):
                    continue
                if missing_only and current_value is not None:
                    continue

                finish_url = cardmarket_url_for_finish(row, finish_id, guide)
                if not finish_url:
                    if not missing_only and current_value is not None:
                        clears_by_finish[finish_id].append((card_set, collector_number))
                        stats["updated"] += 1
                        totals["updated_fields"] += 1
                        totals["cleared_fields"] += 1
                        continue
                    stats["still_missing"] += 1
                    totals["still_missing_fields"] += 1
                    continue
                product_id = parse_id_product(finish_url)
                guide_entry = guide.get(product_id) if product_id is not None else None
                price = lookup_guide_price(guide_entry, finish_id)
                if price is None:
                    if not missing_only and current_value is not None:
                        clears_by_finish[finish_id].append((card_set, collector_number))
                        stats["updated"] += 1
                        totals["updated_fields"] += 1
                        totals["cleared_fields"] += 1
                        continue

                    stats["still_missing"] += 1
                    totals["still_missing_fields"] += 1
                    continue

                if _values_equal(current_value, price):
                    stats["unchanged"] += 1
                    totals["unchanged_fields"] += 1
                    continue

                updates_by_finish[finish_id].append((price, card_set, collector_number))
                stats["updated"] += 1
                totals["updated_fields"] += 1

        _apply_price_sync_batches(
            conn,
            today,
            updates_by_finish=updates_by_finish,
            clears_by_finish=clears_by_finish,
        )
        conn.commit()

    for card_set in sorted(set_stats):
        stats = set_stats[card_set]
        out.info(
            "Set %s: queried %s cards, updated %s prices, unchanged %s, still missing %s",
            card_set,
            stats["queried"],
            stats["updated"],
            stats["unchanged"],
            stats["still_missing"],
        )

    out.info(
        "Cardmarket sync: updated %s, cleared %s, unchanged %s, still missing %s, %s qualifying set(s).",
        totals["updated_fields"],
        totals["cleared_fields"],
        totals["unchanged_fields"],
        totals["still_missing_fields"],
        totals["qualifying_sets"],
    )
    return totals


# Backfill only NULL market values from the Cardmarket price guide.
def fill_missing_prices_from_guide(
    today: str,
    force_download: bool = False,
    set_code: str | None = None,
) -> dict:
    set_codes = {set_code.upper()} if set_code and set_code.upper() != "ALL" else None
    return sync_prices_from_guide(
        today,
        set_codes=set_codes,
        force_download=force_download,
        missing_only=True,
    )
