import sqlite3

import pandas as pd

from lib.config import DB_PATH
from report.report_formatting import (
    build_best_card_html,
    best_valued_card,
    format_invested,
    format_monetary,
    format_total_profit,
    is_missing,
)


# Load the number of completion slots available per set.
def load_catalog_counts(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    from report.report_data import load_catalog_count_by_set

    if conn is not None:
        counts = load_catalog_count_by_set(conn)
    else:
        with sqlite3.connect(DB_PATH) as db_conn:
            counts = load_catalog_count_by_set(db_conn)
    if not counts:
        return pd.DataFrame(columns=["set_code", "catalog_cards"])
    return pd.DataFrame(
        [{"set_code": set_code, "catalog_cards": count} for set_code, count in sorted(counts.items())]
    )


# Load completion slot counts grouped by set and art style.
def load_catalog_art_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    from report.report_data import _load_art_style_catalog_counts

    rows = []
    set_codes = conn.execute("SELECT DISTINCT set_code FROM cards ORDER BY set_code").fetchall()
    for (set_code,) in set_codes:
        counts = _load_art_style_catalog_counts(conn, set_code=str(set_code))
        for art_style, count in sorted(counts.items()):
            rows.append({
                "set_code": str(set_code),
                "art_style": art_style,
                "catalog_cards": count,
            })
    return pd.DataFrame(rows)


# Filter owned and catalog rows to one report page scope.
def stats_scope(
    page: str,
    owned_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if page == "All":
        return owned_df.copy(), catalog_df.copy()
    owned = owned_df[owned_df["set_code"] == page].copy()
    catalog = catalog_df[catalog_df["set_code"] == page].copy()
    return owned, catalog


# Format return on investment as a percentage string.
def format_roi(profit, invested) -> str:
    if is_missing(profit) or is_missing(invested) or invested == 0:
        return "Unknown"
    return f"{(profit / invested) * 100:.1f}%"


# Build completion text showing owned cards versus catalog size.
def format_completion(owned_count: int, catalog_count: int) -> str:
    if catalog_count <= 0:
        return "Unknown"
    percent = (owned_count / catalog_count) * 100
    return f"{owned_count} / {catalog_count} ({percent:.1f}%)"


# Compute formatted collection statistics for one stats report page.
def compute_collection_stats(
    page: str,
    owned_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
) -> dict[str, str]:
    owned, catalog = stats_scope(page, owned_df, catalog_df)
    unknown = owned[owned["current_value"].isna()]
    invested = owned["purchase_value"].sum(min_count=1)
    current = owned["current_value"].sum(min_count=1)
    profit = owned["profit_loss"].sum(min_count=1)
    valued = owned[owned["current_value"].notna()]
    average = valued["current_value"].mean() if not valued.empty else None
    winners = len(owned[owned["profit_loss"] > 0])
    losers = len(owned[owned["profit_loss"] < 0])
    return {
        "{{STAT_CURRENT}}": format_monetary(current),
        "{{STAT_INVESTED}}": format_invested(invested),
        "{{STAT_PROFIT}}": format_total_profit(profit),
        "{{STAT_ROI}}": format_roi(profit, invested),
        "{{STAT_OWNED}}": str(len(owned)),
        "{{STAT_COMPLETION}}": format_completion(len(owned), int(catalog["catalog_cards"].sum())),
        "{{STAT_AVERAGE}}": format_monetary(average),
        "{{STAT_UNKNOWN}}": format_monetary(unknown["purchase_value"].sum(min_count=1)),
        "{{STAT_UNKNOWN_COUNT}}": f"{len(unknown)} cards",
        "{{STAT_WINNERS}}": str(winners),
        "{{STAT_LOSERS}}": str(losers),
        "{{STAT_BEST_CARD}}": build_best_card_html(best_valued_card(owned)),
    }

