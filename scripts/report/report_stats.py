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


# Load the number of catalog cards available per set.
def load_catalog_counts(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    query = "SELECT set_code, COUNT(*) AS catalog_cards FROM cards GROUP BY set_code"
    if conn is not None:
        return pd.read_sql_query(query, conn)
    with sqlite3.connect(DB_PATH) as db_conn:
        return pd.read_sql_query(query, db_conn)


# Load catalog card counts grouped by set and art style.
def load_catalog_art_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT set_code, art_style, COUNT(*) AS catalog_cards
        FROM cards
        GROUP BY set_code, art_style
        """,
        conn,
    )


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

