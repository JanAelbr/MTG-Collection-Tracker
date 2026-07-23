import sqlite3
import threading
import time

from lib.config import HTTP_USER_AGENT
from lib.art_styles import ensure_art_style_rules_table
from lib.run_log import format_duration, get_logger
from util.app_tables import ensure_app_tables
from util.card_prices import ensure_card_prices_table
from util.db_migrate import (
    backfill_basic_land_flags,
    backfill_card_types,
    ensure_card_columns,
    ensure_card_detail_metadata,
    ensure_card_indexes,
    ensure_purchase_unique_index,
    ensure_set_code_aliases,
    mark_complete_catalog_sets,
)
from util.deck_tables import ensure_deck_tables
from util.set_catalog import (
    backfill_missing_set_icon_uris,
    backfill_missing_set_relations,
    ensure_sets_columns,
    ensure_sets_table,
)
from util.set_family_sync import ensure_tracked_family_children
from util.alchemy_cards import prune_alchemy_cards
from util.card_name_roles import backfill_card_name_roles, ensure_card_name_roles_table
from util.tracked_sets import ensure_tracked_sets_ready

log = get_logger(__name__)

CORE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    name TEXT NOT NULL,
    art_style TEXT,
    market_value REAL DEFAULT NULL,
    market_value_foil REAL DEFAULT NULL,
    market_value_etched REAL DEFAULT NULL,
    has_nonfoil INTEGER,
    has_foil INTEGER,
    has_etched INTEGER,
    image_uri TEXT,
    cardmarket_url TEXT,
    cardmarket_url_foil TEXT,
    colors TEXT,
    type_line TEXT,
    card_type TEXT
);

CREATE TABLE IF NOT EXISTS purchases (
    purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    purchase_value REAL NOT NULL DEFAULT 0,
    finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
    UNIQUE (set_code, collector_number, finish)
);

CREATE TABLE IF NOT EXISTS sets (
    set_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    released_at TEXT,
    scryfall_uri TEXT,
    icon_svg_uri TEXT,
    updated_at TEXT NOT NULL
);
"""


_schema_lock = threading.Lock()
_initialized_db_paths: set[str] = set()


def _database_path(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return row[2] if row else ""


def ensure_database_schema(conn: sqlite3.Connection) -> None:
    """Create core collection tables and run incremental migrations once per database file."""
    db_path = _database_path(conn)
    if db_path and db_path in _initialized_db_paths:
        log.debug("Schema ensure skipped (already initialized): %s", db_path or "(memory)")
        return
    with _schema_lock:
        if db_path and db_path in _initialized_db_paths:
            log.debug("Schema ensure skipped (already initialized): %s", db_path or "(memory)")
            return
        started = time.perf_counter()
        log.info("Ensuring database schema%s", f" for {db_path}" if db_path else "")
        conn.executescript(CORE_TABLES_SQL)
        ensure_deck_tables(conn)
        ensure_sets_table(conn)
        ensure_sets_columns(conn)
        backfill_missing_set_icon_uris(conn, {"User-Agent": HTTP_USER_AGENT})
        backfill_missing_set_relations(conn, {"User-Agent": HTTP_USER_AGENT})
        ensure_tracked_sets_ready(conn)
        family_sync = ensure_tracked_family_children(conn, {"User-Agent": HTTP_USER_AGENT})
        if family_sync.get("added"):
            log.info(
                "Loaded %s family child set(s): %s",
                len(family_sync["added"]),
                ", ".join(family_sync["added"]),
            )
        ensure_card_prices_table(conn)
        ensure_card_columns(conn)
        prune_alchemy_cards(conn)
        backfill_card_types(conn)
        backfill_basic_land_flags(conn)
        mark_complete_catalog_sets(conn)
        ensure_card_indexes(conn)
        ensure_purchase_unique_index(conn)
        ensure_set_code_aliases(conn)
        ensure_app_tables(conn)
        ensure_tracked_sets_ready(conn)
        ensure_card_detail_metadata(conn)
        ensure_art_style_rules_table(conn)
        ensure_card_name_roles_table(conn)
        roles_upserted = backfill_card_name_roles(conn)
        if roles_upserted:
            log.info("Card name roles backfill upserted %s name(s)", roles_upserted)
        if db_path:
            _initialized_db_paths.add(db_path)
        log.info(
            "Database schema ready (%s)",
            format_duration(time.perf_counter() - started),
        )
