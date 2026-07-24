import sqlite3

import pandas as pd

from lib.config import DB_PATH, EXCLUDED_SET_CODES, normalize_set_code
from util.deck_tables import list_deck_sync_set_codes
from report.report_queries import (
    OWNED_CARDS_FOR_SET_QUERY,
    OWNED_CARDS_QUERY,
    ORPHAN_PURCHASES_QUERY,
    SET_ORPHAN_PURCHASES_QUERY,
    cards_query,
    summary_query,
)
from report.set_order import SET_SORT_ALPHABETICAL, sort_set_codes
from util.set_catalog import load_set_display_names as query_set_display_names
from util.set_catalog import load_set_icon_uris, load_sets_catalog
from util.set_families import (
    build_family_index,
    effective_family_root,
    load_set_relations,
    ordered_set_codes_by_family,
)
from util.tracked_sets import list_tracked_set_codes
from util.alchemy_cards import (
    exclude_alchemy_art_style_sql,
    exclude_alchemy_sql,
    is_alchemy_art_style,
)


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
    icon_uri: str | None = None,
    set_type: str | None = None,
    parent_set_code: str | None = None,
    family_root: str | None = None,
    family_members: list[str] | None = None,
    family_owned_count: int | None = None,
    family_catalog_count: int | None = None,
) -> dict:
    favorite_upper = {code.upper() for code in (favorite_sets or [])}
    normalized = set_code.upper() if set_code != "All" else set_code
    label = "All sets" if set_code == "All" else format_set_option_label(set_code, set_names)
    members = [code.upper() for code in (family_members or [])]
    root = (family_root or normalized).upper() if normalized != "All" else None
    option = {
        "setCode": set_code,
        "label": label,
        "favorite": normalized != "All" and normalized in favorite_upper,
        "iconUri": icon_uri or scryfall_set_icon_uri(set_code),
        "setType": set_type,
        "parentSetCode": parent_set_code.upper() if parent_set_code else None,
        "familyRoot": root,
        "familyMembers": members,
        "isFamilyRoot": bool(root and normalized == root and len(members) > 1),
    }
    if owned_count is not None:
        option["ownedCount"] = owned_count
    if catalog_count is not None:
        option["catalogCount"] = catalog_count
    if family_owned_count is not None:
        option["familyOwnedCount"] = family_owned_count
    if family_catalog_count is not None:
        option["familyCatalogCount"] = family_catalog_count
    return option


def _table_has_card_instances(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
        ).fetchone()
        is not None
    )


def _owned_prints_sql(has_instances: bool) -> str:
    if has_instances:
        return """
            SELECT set_code, collector_number FROM purchases
            UNION
            SELECT set_code, collector_number FROM card_instances
        """
    return "SELECT set_code, collector_number FROM purchases"


_SET_COUNT_CACHE_TTL = 300


def _database_identity(conn: sqlite3.Connection) -> str | None:
    """On-disk path for this connection, or None when not safely cacheable.

    ``:memory:`` / temp databases (used heavily in tests) get a distinct DB per
    connection but share the process-wide memory_cache, so caching them by
    epoch alone would leak results across unrelated databases.
    """
    row = conn.execute("PRAGMA database_list").fetchone()
    path = row[2] if row else ""
    return path if path else None


def load_owned_count_by_set(conn: sqlite3.Connection) -> dict[str, int]:
    from util.set_completion import count_completion_keys_by_set

    def _compute() -> dict[str, int]:
        owned_prints = _owned_prints_sql(_table_has_card_instances(conn))
        rows = conn.execute(
            f"""
            SELECT set_code, collector_number
            FROM ({owned_prints}) owned_prints
            WHERE {exclude_alchemy_sql()}
            """
        ).fetchall()
        return count_completion_keys_by_set(rows)

    db_path = _database_identity(conn)
    if db_path is None:
        return _compute()

    from api.cache import get_cache_epoch, memory_cache

    epoch = get_cache_epoch()
    cache_key = memory_cache.make_key("report_data.owned_count_by_set", {"db": db_path}, epoch)
    cached = memory_cache.get(cache_key)
    if cached is not None:
        return cached

    result = _compute()
    memory_cache.set(cache_key, result, _SET_COUNT_CACHE_TTL)
    return result


def load_catalog_count_by_set(conn: sqlite3.Connection) -> dict[str, int]:
    from util.set_completion import count_completion_keys_by_set

    def _compute() -> dict[str, int]:
        rows = conn.execute(
            f"""
            SELECT set_code, collector_number
            FROM cards
            WHERE {exclude_alchemy_sql()}
              AND {exclude_alchemy_art_style_sql()}
            """
        ).fetchall()
        return count_completion_keys_by_set(rows)

    db_path = _database_identity(conn)
    if db_path is None:
        return _compute()

    from api.cache import get_cache_epoch, memory_cache

    epoch = get_cache_epoch()
    cache_key = memory_cache.make_key("report_data.catalog_count_by_set", {"db": db_path}, epoch)
    cached = memory_cache.get(cache_key)
    if cached is not None:
        return cached

    result = _compute()
    memory_cache.set(cache_key, result, _SET_COUNT_CACHE_TTL)
    return result


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
    icon_uris = load_set_icon_uris(conn)
    catalog = load_sets_catalog(conn)
    relations = load_set_relations(conn)
    all_codes = get_all_set_codes()
    known = {code.upper() for code in all_codes}
    families = build_family_index(known, relations)

    roots = sorted(
        {
            effective_family_root(code, relations, known)
            for code in known
        }
    )
    favorite_roots: list[str] = []
    seen_favorite_roots: set[str] = set()
    for favorite in favorites:
        root = effective_family_root(str(favorite), relations, known)
        if not root or root not in known or root in seen_favorite_roots:
            continue
        favorite_roots.append(root)
        seen_favorite_roots.add(root)
    sorted_roots = sort_set_codes(
        roots,
        favorite_roots,
        sort_mode=sort_mode,
        owned_counts={
            root: sum(owned_counts.get(member, 0) for member in (families.get(root) or [root]))
            for root in roots
        },
    )
    ordered_codes = ordered_set_codes_by_family(
        all_codes,
        relations,
        sorted_roots=sorted_roots,
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
    for set_code in ordered_codes:
        code_upper = set_code.upper()
        meta = catalog.get(code_upper) or {}
        rel = relations.get(code_upper) or {}
        root = effective_family_root(code_upper, relations, known)
        members = families.get(root) or [code_upper]
        family_owned = sum(owned_counts.get(member, 0) for member in members)
        family_catalog = sum(catalog_counts.get(member, 0) for member in members)
        options.append(
            build_set_option(
                set_code,
                set_names,
                favorites,
                owned_count=owned_counts.get(code_upper, 0),
                catalog_count=catalog_counts.get(code_upper, 0),
                icon_uri=icon_uris.get(code_upper) or meta.get("icon_svg_uri"),
                set_type=rel.get("set_type") or meta.get("set_type"),
                parent_set_code=rel.get("parent_set_code") or meta.get("parent_set_code"),
                family_root=root,
                family_members=members,
                family_owned_count=family_owned if len(members) > 1 else None,
                family_catalog_count=family_catalog if len(members) > 1 else None,
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
    from util.set_completion import count_completion_keys_by_art_style

    owned_prints = _owned_prints_sql(_table_has_card_instances(conn))
    where_parts = [
        "c.art_style IS NOT NULL",
        "TRIM(c.art_style) != ''",
        exclude_alchemy_sql("c.collector_number"),
        exclude_alchemy_sql("owned.collector_number"),
        exclude_alchemy_art_style_sql("c.art_style"),
    ]
    params: tuple[str, ...] = ()
    if set_code is not None:
        where_parts.insert(0, "owned.set_code = ?")
        params = (set_code.upper(),)
    where_clause = "WHERE " + " AND ".join(where_parts)
    rows = conn.execute(
        f"""
        SELECT owned.set_code, owned.collector_number, c.art_style
        FROM ({owned_prints}) owned
        JOIN cards c
          ON c.set_code = owned.set_code
         AND c.collector_number = owned.collector_number
        {where_clause}
        """,
        params,
    ).fetchall()
    return count_completion_keys_by_art_style(rows, set_code=set_code)


def _load_art_style_catalog_counts(conn: sqlite3.Connection, *, set_code: str | None = None) -> dict[str, int]:
    from util.set_completion import count_completion_keys_by_art_style

    where_parts = [
        "art_style IS NOT NULL",
        "TRIM(art_style) != ''",
        exclude_alchemy_sql(),
        exclude_alchemy_art_style_sql(),
    ]
    params: tuple[str, ...] = ()
    if set_code is not None:
        where_parts.insert(0, "set_code = ?")
        params = (set_code.upper(),)
    where_clause = "WHERE " + " AND ".join(where_parts)
    rows = conn.execute(
        f"""
        SELECT set_code, collector_number, art_style
        FROM cards
        {where_clause}
        """,
        params,
    ).fetchall()
    return count_completion_keys_by_art_style(rows, set_code=set_code)


def _build_art_style_options_from_counts(
    owned_counts: dict[str, int],
    catalog_counts: dict[str, int],
) -> list[dict]:
    names = sorted(
        style
        for style in (set(catalog_counts.keys()) | set(owned_counts.keys()))
        if not is_alchemy_art_style(style)
    )
    return [
        build_art_style_option(
            name,
            owned_count=owned_counts.get(name, 0),
            catalog_count=catalog_counts.get(name, 0),
        )
        for name in names
    ]


def build_art_style_options_for_set(conn: sqlite3.Connection, set_code: str) -> list[dict]:
    from api.cache import get_cache_epoch, memory_cache

    normalized = set_code.strip().upper()
    epoch = get_cache_epoch()
    cache_key = memory_cache.make_key(
        "report_data.art_styles",
        {"setCode": normalized},
        epoch,
    )
    cached = memory_cache.get(cache_key)
    if cached is not None:
        return cached
    owned_counts = _load_art_style_owned_counts(conn, set_code=normalized)
    catalog_counts = _load_art_style_catalog_counts(conn, set_code=normalized)
    options = _build_art_style_options_from_counts(owned_counts, catalog_counts)
    memory_cache.set(cache_key, options, _SET_COUNT_CACHE_TTL)
    return options


def build_art_style_options(conn: sqlite3.Connection, set_code: str = "All") -> list[dict]:
    if set_code and str(set_code).strip().lower() != "all":
        return build_art_style_options_for_set(conn, set_code)
    owned_counts = _load_art_style_owned_counts(conn)
    catalog_counts = _load_art_style_catalog_counts(conn)
    return _build_art_style_options_from_counts(owned_counts, catalog_counts)


# Collect set codes from tracked sets, the database, and deck lists.
def get_all_set_codes() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        tracked_sets = list_tracked_set_codes(conn)
        deck_sets = list_deck_sync_set_codes(conn)
        db_sets = pd.read_sql_query(
            "SELECT DISTINCT set_code FROM cards ORDER BY set_code",
            conn,
        )["set_code"].tolist()

    return sorted(
        code for code in {normalize_set_code(raw) for raw in (set(db_sets) | set(tracked_sets) | set(deck_sets))}
        if code and code not in EXCLUDED_SET_CODES
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


def select_owned_cards(cards_df: pd.DataFrame, owned_only: bool) -> pd.DataFrame:
    if owned_only:
        return cards_df.copy()
    return cards_df[cards_df["purchase_value"].notna()]


def load_owned_collection_data(
    conn: sqlite3.Connection,
    set_code: str | None = None,
) -> pd.DataFrame:
    normalized = (set_code or "").strip().upper()
    if normalized and normalized != "ALL":
        cards_df = pd.read_sql_query(OWNED_CARDS_FOR_SET_QUERY, conn, params=(normalized,))
        orphan_df = pd.read_sql_query(SET_ORPHAN_PURCHASES_QUERY, conn, params=(normalized,))
    else:
        cards_df = pd.read_sql_query(OWNED_CARDS_QUERY, conn)
        orphan_df = pd.read_sql_query(ORPHAN_PURCHASES_QUERY, conn)
    if not orphan_df.empty:
        cards_df = pd.concat([cards_df, orphan_df], ignore_index=True)
    return cards_df
