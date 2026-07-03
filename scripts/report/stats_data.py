import sqlite3

import pandas as pd

from lib.config import DB_PATH
from report.report_stats import load_catalog_art_counts, stats_scope
from report.serialize_helpers import deck_card_display_name, str_or_empty
from util.price_history import PriceSnapshotCache, load_price_snapshot_cache


def _float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _collector_sort_key(collector_number: str) -> tuple:
    if str(collector_number).isdigit():
        return (0, int(collector_number))
    return (1, str(collector_number))


def _serialize_unknown_cards(unknown_df: pd.DataFrame) -> list[dict]:
    cards = []
    for _, row in unknown_df.iterrows():
        cards.append({
            "set_code": row["set_code"],
            "collector_number": str(row["collector_number"]),
            "name": deck_card_display_name(row),
            "art_style": str_or_empty(row["art_style"]),
            "finish": int(row["finish"]) if not pd.isna(row["finish"]) else 0,
            "foil": int(row["finish"]) if not pd.isna(row["finish"]) else 0,
        })
    return sorted(
        cards,
        key=lambda card: (
            card["set_code"],
            _collector_sort_key(card["collector_number"]),
            card["name"],
        ),
    )


def _normalize_art_style(value) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    if isinstance(value, tuple):
        value = value[-1]
    return str(value)


def _group_set_and_art(page: str, key) -> tuple[str, str]:
    if page == "All":
        if isinstance(key, tuple):
            set_code, art_style = key[0], key[1]
        else:
            set_code, art_style = page, key
    else:
        set_code = page
        art_style = key[0] if isinstance(key, tuple) else key
    return str(set_code), _normalize_art_style(art_style)


def _build_catalog_art_lookup(catalog_art_df: pd.DataFrame) -> dict[tuple[str, str], int]:
    lookup: dict[tuple[str, str], int] = {}
    for _, row in catalog_art_df.iterrows():
        art_style = _normalize_art_style(row["art_style"])
        lookup[(str(row["set_code"]), art_style)] = int(row["catalog_cards"])
    return lookup


def _lookup_catalog_art_count(
    catalog_art_lookup: dict[tuple[str, str], int],
    set_code: str,
    art_style: str,
) -> int:
    return catalog_art_lookup.get((str(set_code), str(art_style)), 0)


def _compute_stats_from_owned(
    owned: pd.DataFrame,
    catalog_count: int,
    conn: sqlite3.Connection,
    snapshot_cache: PriceSnapshotCache,
) -> dict:
    unknown = owned[owned["current_value"].isna()]
    invested = owned["purchase_value"].sum(min_count=1)
    current = owned["current_value"].sum(min_count=1)
    profit = owned["profit_loss"].sum(min_count=1)
    valued = owned[owned["current_value"].notna()]
    average = valued["current_value"].mean() if not valued.empty else None

    return {
        "current": _float_or_none(current),
        "invested": _float_or_none(invested),
        "profit": _float_or_none(profit),
        "ownedCount": len(owned),
        "catalogCount": catalog_count,
        "average": _float_or_none(average),
        "unknownInvested": _float_or_none(unknown["purchase_value"].sum(min_count=1)),
        "unknownCount": len(unknown),
        "unknownCards": _serialize_unknown_cards(unknown),
        "winners": int(len(owned[owned["profit_loss"] > 0])),
        "losers": int(len(owned[owned["profit_loss"] < 0])),
    }


def _compute_art_style_stats(owned: pd.DataFrame, page: str) -> list[dict]:
    if owned.empty:
        return []

    group_keys = ["art_style"] if page != "All" else ["set_code", "art_style"]
    rows = []
    grouped = owned.groupby(group_keys, dropna=False)
    for key, group in grouped:
        set_code, art_style = _group_set_and_art(page, key)
        rows.append({
            "set_code": set_code,
            "art_style": art_style,
            "count": len(group),
            "current": _float_or_none(group["current_value"].sum(min_count=1)),
            "invested": _float_or_none(group["purchase_value"].sum(min_count=1)),
            "profit": _float_or_none(group["profit_loss"].sum(min_count=1)),
        })

    return sorted(rows, key=lambda row: (row["set_code"], row["art_style"]))


def _compute_set_stats(owned: pd.DataFrame, catalog_df: pd.DataFrame) -> list[dict]:
    if owned.empty:
        return []

    catalog_by_set: dict[str, int] = {}
    if not catalog_df.empty:
        for _, row in catalog_df.iterrows():
            catalog_by_set[str(row["set_code"])] = int(row["catalog_cards"])

    rows = []
    for set_code, group in owned.groupby("set_code", dropna=False):
        set_key = str(set_code)
        rows.append({
            "set_code": set_key,
            "count": len(group),
            "catalog_count": catalog_by_set.get(set_key, 0),
            "current": _float_or_none(group["current_value"].sum(min_count=1)),
            "invested": _float_or_none(group["purchase_value"].sum(min_count=1)),
            "profit": _float_or_none(group["profit_loss"].sum(min_count=1)),
        })

    return sorted(rows, key=lambda row: row["set_code"])


def _build_by_foil(
    page: str,
    owned: pd.DataFrame,
    catalog_count: int,
    catalog_df: pd.DataFrame,
    catalog_art_lookup: dict[tuple[str, str], int],
    conn: sqlite3.Connection,
    snapshot_cache: PriceSnapshotCache,
) -> dict[str, dict]:
    if owned.empty:
        return {}

    by_foil: dict[str, dict] = {}
    for finish_value in (0, 1, 2):
        subset = owned[owned["finish"] == finish_value]
        if subset.empty:
            continue
        stats = _compute_stats_from_owned(subset, catalog_count, conn, snapshot_cache)
        stats["artStyles"] = _compute_art_style_stats(subset, page)
        if page == "All":
            stats["setBreakdown"] = _compute_set_stats(subset, catalog_df)
        stats["byArtStyle"] = _build_by_art_style(
            page,
            subset,
            catalog_art_lookup,
            conn,
            snapshot_cache,
        )
        by_foil[str(finish_value)] = stats

    return by_foil


def _build_by_art_style(
    page: str,
    owned: pd.DataFrame,
    catalog_art_lookup: dict[tuple[str, str], int],
    conn: sqlite3.Connection,
    snapshot_cache: PriceSnapshotCache,
) -> dict[str, dict]:
    if owned.empty:
        return {}

    by_art: dict[str, dict] = {}
    group_keys = ["set_code", "art_style"] if page == "All" else ["art_style"]
    grouped = owned.groupby(group_keys, dropna=False)
    for key, group in grouped:
        set_code, art_style = _group_set_and_art(page, key)
        art_key = f"{set_code}|{art_style}"
        catalog_count = _lookup_catalog_art_count(catalog_art_lookup, set_code, art_style)
        by_art[art_key] = _compute_stats_from_owned(
            group,
            catalog_count,
            conn,
            snapshot_cache,
        )

    return by_art


# Build raw stats for one page scope.
def compute_stats_page(
    page: str,
    owned_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    catalog_art_lookup: dict[tuple[str, str], int],
    conn: sqlite3.Connection,
    snapshot_cache: PriceSnapshotCache,
    *,
    include_client_drilldowns: bool = True,
) -> dict:
    owned, catalog = stats_scope(page, owned_df, catalog_df)
    catalog_count = int(catalog["catalog_cards"].sum()) if not catalog.empty else 0
    stats = _compute_stats_from_owned(owned, catalog_count, conn, snapshot_cache)
    stats["artStyles"] = _compute_art_style_stats(owned, page)
    if page == "All":
        stats["setBreakdown"] = _compute_set_stats(owned, catalog_df)
    if include_client_drilldowns:
        stats["byArtStyle"] = _build_by_art_style(
            page,
            owned,
            catalog_art_lookup,
            conn,
            snapshot_cache,
        )
        stats["byFoil"] = _build_by_foil(
            page,
            owned,
            catalog_count,
            catalog_df,
            catalog_art_lookup,
            conn,
            snapshot_cache,
        )
    return stats


# Build the client payload for stats report pages.
def load_stats_client_payload(
    owned_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    pages: list[str],
    conn: sqlite3.Connection | None = None,
) -> dict:
    if conn is not None:
        return _load_stats_client_payload(conn, owned_df, catalog_df, pages)
    with sqlite3.connect(DB_PATH) as db_conn:
        return _load_stats_client_payload(db_conn, owned_df, catalog_df, pages)


def _load_stats_client_payload(
    conn: sqlite3.Connection,
    owned_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    pages: list[str],
) -> dict:
    catalog_art_df = load_catalog_art_counts(conn)
    catalog_art_lookup = _build_catalog_art_lookup(catalog_art_df)
    snapshot_cache = load_price_snapshot_cache(conn)
    page_payload = {
        page: compute_stats_page(
            page,
            owned_df,
            catalog_df,
            catalog_art_lookup,
            conn,
            snapshot_cache,
        )
        for page in pages
    }
    return {"pages": page_payload}
