import sqlite3

import pandas as pd

from lib.config import DB_PATH


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


# Load completion slot counts grouped by rarity for one set.
def load_catalog_rarity_counts(conn: sqlite3.Connection, set_code: str) -> dict[str, int]:
    from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql
    from util.set_completion import count_completion_keys_by_rarity

    normalized = str(set_code or "").strip().upper()
    if not normalized or normalized == "ALL":
        return {}
    rows = conn.execute(
        f"""
        SELECT set_code, collector_number, rarity
        FROM cards
        WHERE set_code = ?
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        """,
        (normalized,),
    ).fetchall()
    return count_completion_keys_by_rarity(rows, set_code=normalized)


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
