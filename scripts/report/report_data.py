import sqlite3

import pandas as pd

from lib.config import DB_PATH, EXCLUDED_SET_CODES, list_set_csv_files
from lib.deck_csv import list_deck_sync_set_codes
from report.ranked_cards_data import load_ranked_cards_data
from report.report_queries import cards_query, ORPHAN_PURCHASES_QUERY, summary_query, TOP_OWNED_CARDS_QUERY
from report.set_order import SET_SORT_ALPHABETICAL, sort_set_codes
from util.set_catalog import load_set_display_names as query_set_display_names
from util.price_history import default_compare_date, enrich_with_compare_date, enrich_with_previous_prices, get_price_snapshot_dates


_set_display_names_cache: dict[str, str] | None = None


# Load set display names from the sets catalog table.
def get_set_display_names(refresh: bool = False) -> dict[str, str]:
    global _set_display_names_cache
    if _set_display_names_cache is None or refresh:
        with sqlite3.connect(DB_PATH) as conn:
            _set_display_names_cache = query_set_display_names(conn)
    return _set_display_names_cache


# Format one set code for use in HTML select option labels.
def format_set_option_label(
    set_code: str,
    set_names: dict[str, str] | None = None,
) -> str:
    if set_code == "All":
        return "All"
    code = set_code.upper()
    names = set_names if set_names is not None else get_set_display_names()
    name = names.get(code)
    if name:
        return f"{name} ({code})"
    return code


def scryfall_set_icon_uri(set_code: str) -> str | None:
    if not set_code or set_code == "All":
        return None
    return f"https://svgs.scryfall.io/sets/{set_code.lower()}.svg"


def build_set_option(
    set_code: str,
    set_names: dict[str, str],
    favorite_sets: list[str] | None = None,
    *,
    owned_count: int | None = None,
    catalog_count: int | None = None,
) -> dict:
    favorite_upper = {code.upper() for code in (favorite_sets or [])}
    normalized = set_code.upper() if set_code != "All" else set_code
    label = "All sets" if set_code == "All" else format_set_option_label(set_code, set_names)
    option = {
        "setCode": set_code,
        "label": label,
        "favorite": normalized != "All" and normalized in favorite_upper,
        "iconUri": scryfall_set_icon_uri(set_code),
    }
    if owned_count is not None:
        option["ownedCount"] = owned_count
    if catalog_count is not None:
        option["catalogCount"] = catalog_count
    return option


def load_owned_count_by_set(conn: sqlite3.Connection) -> dict[str, int]:
    has_instances = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
    ).fetchone()
    if has_instances:
        rows = conn.execute(
            """
            SELECT set_code, COUNT(*) AS owned_count
            FROM (
                SELECT set_code, collector_number, finish FROM purchases
                UNION
                SELECT set_code, collector_number, finish FROM card_instances
            ) owned_prints
            GROUP BY set_code
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT set_code, COUNT(*) AS owned_count
            FROM purchases
            GROUP BY set_code
            """
        ).fetchall()
    return {str(set_code).upper(): int(count) for set_code, count in rows}


def load_catalog_count_by_set(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT set_code, COUNT(*) AS catalog_count
        FROM cards
        GROUP BY set_code
        """
    ).fetchall()
    return {str(set_code).upper(): int(count) for set_code, count in rows}


def build_sorted_set_options(
    conn: sqlite3.Connection,
    *,
    favorite_sets: list[str] | None = None,
    sort_mode: str = SET_SORT_ALPHABETICAL,
    include_all: bool = True,
) -> list[dict]:
    favorites = favorite_sets or []
    set_names = get_set_display_names()
    owned_counts = load_owned_count_by_set(conn)
    catalog_counts = load_catalog_count_by_set(conn)
    sorted_codes = sort_set_codes(
        get_all_set_codes(),
        favorites,
        sort_mode=sort_mode,
        owned_counts=owned_counts,
    )

    options: list[dict] = []
    if include_all:
        options.append(
            build_set_option(
                "All",
                set_names,
                favorites,
                owned_count=sum(owned_counts.values()),
                catalog_count=sum(catalog_counts.values()),
            )
        )
    for set_code in sorted_codes:
        code_upper = set_code.upper()
        options.append(
            build_set_option(
                set_code,
                set_names,
                favorites,
                owned_count=owned_counts.get(code_upper, 0),
                catalog_count=catalog_counts.get(code_upper, 0),
            )
        )
    return options


def build_art_style_option(
    art_style: str,
    *,
    owned_count: int = 0,
    catalog_count: int = 0,
) -> dict:
    return {
        "artStyle": art_style,
        "label": art_style,
        "ownedCount": owned_count,
        "catalogCount": catalog_count,
    }


def _load_art_style_owned_counts(conn: sqlite3.Connection, *, set_code: str | None = None) -> dict[str, int]:
    if set_code is not None:
        rows = conn.execute(
            """
            SELECT c.art_style, COUNT(*) AS owned_count
            FROM purchases p
            JOIN cards c
              ON c.set_code = p.set_code
             AND c.collector_number = p.collector_number
            WHERE p.set_code = ?
              AND c.art_style IS NOT NULL
              AND TRIM(c.art_style) != ''
            GROUP BY c.art_style
            """,
            (set_code.upper(),),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT c.art_style, COUNT(*) AS owned_count
            FROM purchases p
            JOIN cards c
              ON c.set_code = p.set_code
             AND c.collector_number = p.collector_number
            WHERE c.art_style IS NOT NULL
              AND TRIM(c.art_style) != ''
            GROUP BY c.art_style
            """
        ).fetchall()
    return {str(art_style): int(count) for art_style, count in rows}


def _load_art_style_catalog_counts(conn: sqlite3.Connection, *, set_code: str | None = None) -> dict[str, int]:
    if set_code is not None:
        rows = conn.execute(
            """
            SELECT art_style, COUNT(*) AS catalog_count
            FROM cards
            WHERE set_code = ?
              AND art_style IS NOT NULL
              AND TRIM(art_style) != ''
            GROUP BY art_style
            """,
            (set_code.upper(),),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT art_style, COUNT(*) AS catalog_count
            FROM cards
            WHERE art_style IS NOT NULL
              AND TRIM(art_style) != ''
            GROUP BY art_style
            """
        ).fetchall()
    return {str(art_style): int(count) for art_style, count in rows}


def _build_art_style_options_from_counts(
    owned_counts: dict[str, int],
    catalog_counts: dict[str, int],
) -> list[dict]:
    names = sorted(set(catalog_counts.keys()) | set(owned_counts.keys()))
    return [
        build_art_style_option(
            name,
            owned_count=owned_counts.get(name, 0),
            catalog_count=catalog_counts.get(name, 0),
        )
        for name in names
    ]


def build_art_style_options_for_set(conn: sqlite3.Connection, set_code: str) -> list[dict]:
    normalized = set_code.strip().upper()
    owned_counts = _load_art_style_owned_counts(conn, set_code=normalized)
    catalog_counts = _load_art_style_catalog_counts(conn, set_code=normalized)
    return _build_art_style_options_from_counts(owned_counts, catalog_counts)


def build_art_style_options(conn: sqlite3.Connection, set_code: str = "All") -> list[dict]:
    if set_code and str(set_code).strip().lower() != "all":
        return build_art_style_options_for_set(conn, set_code)
    owned_counts = _load_art_style_owned_counts(conn)
    catalog_counts = _load_art_style_catalog_counts(conn)
    return _build_art_style_options_from_counts(owned_counts, catalog_counts)


# Collect set codes from the database, purchase CSVs, and deck lists.
def get_all_set_codes() -> list[str]:
    csv_sets = [path.stem.upper() for path in list_set_csv_files()]
    deck_sets = list_deck_sync_set_codes()

    with sqlite3.connect(DB_PATH) as conn:
        db_sets = pd.read_sql_query(
            "SELECT DISTINCT set_code FROM cards ORDER BY set_code",
            conn,
        )["set_code"].tolist()

    return sorted(
        code for code in (set(db_sets) | set(csv_sets) | set(deck_sets))
        if code not in EXCLUDED_SET_CODES
    )


# Load card rows and art-style summary rows for owned-only or all-cards reports.
def load_collection_data(
    owned_only: bool = False,
    conn: sqlite3.Connection | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if conn is not None:
        return _load_collection_data(conn, owned_only)
    with sqlite3.connect(DB_PATH) as db_conn:
        return _load_collection_data(db_conn, owned_only)


def _load_collection_data(conn: sqlite3.Connection, owned_only: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    cards_df = pd.read_sql_query(cards_query(owned_only), conn)
    if owned_only:
        orphan_df = pd.read_sql_query(ORPHAN_PURCHASES_QUERY, conn)
        if not orphan_df.empty:
            cards_df = pd.concat([cards_df, orphan_df], ignore_index=True)
    summary_df = pd.read_sql_query(summary_query(owned_only), conn)
    return cards_df, summary_df


# Load ranked cards for top/risers/fallers reports, including owned cards without prices.
def load_top_cards_data() -> pd.DataFrame:
    cards_df = load_ranked_cards_data()
    with sqlite3.connect(DB_PATH) as conn:
        return enrich_with_previous_prices(conn, cards_df)


# Load owned cards with the largest price increase since a snapshot date.
def load_top_risers_data(compare_date: str | None = None) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        cards_df = pd.read_sql_query(TOP_OWNED_CARDS_QUERY, conn)
        dates = get_price_snapshot_dates(conn)
        if compare_date is None:
            compare_date = default_compare_date(dates)
        if compare_date:
            cards_df = enrich_with_compare_date(conn, cards_df, compare_date)
        else:
            cards_df = enrich_with_previous_prices(conn, cards_df)

    risers = cards_df[cards_df["price_change"].notna() & (cards_df["price_change"] > 0)].copy()
    return risers.sort_values(
        ["price_change", "current_value"],
        ascending=[False, False],
    )
