import sqlite3
import threading
import time

from lib.config import HTTP_USER_AGENT
from lib.art_styles import ensure_art_style_rules_table
from lib.db import main_database_path
from lib.run_log import format_duration, get_logger
from util.app_tables import ensure_app_tables
from util.card_prices import ensure_card_prices_table
from util.catalog_meta import ensure_catalog_meta_table
from util.db_migrate import (
    ensure_card_indexes,
    ensure_cards_fts,
    ensure_purchase_unique_index,
)
from util.deck_tables import ensure_deck_tables
from util.set_catalog import ensure_sets_table
from util.set_family_sync import ensure_tracked_family_children
from util.card_name_roles import ensure_card_name_roles_table
from util.tracked_sets import ensure_tracked_sets_ready

log = get_logger(__name__)

CATALOG_CORE_TABLES_SQL = """
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
    image_uri_back TEXT,
    cardmarket_url TEXT,
    cardmarket_url_foil TEXT,
    scryfall_cardmarket_url TEXT,
    colors TEXT,
    type_line TEXT,
    card_type TEXT,
    color_identity TEXT,
    oracle_text TEXT,
    mana_cost TEXT,
    cmc REAL,
    legalities TEXT,
    is_basic_land INTEGER,
    scryfall_id TEXT,
    power TEXT,
    toughness TEXT,
    rarity TEXT
);

CREATE TABLE IF NOT EXISTS sets (
    set_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    released_at TEXT,
    scryfall_uri TEXT,
    icon_svg_uri TEXT,
    updated_at TEXT NOT NULL,
    catalog_synced_at TEXT,
    set_type TEXT,
    parent_set_code TEXT,
    digital INTEGER
);
"""

PROFILE_CORE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS purchases (
    purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    purchase_value REAL NOT NULL DEFAULT 0,
    finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
    UNIQUE (set_code, collector_number, finish)
);
"""

CORE_TABLES_SQL = CATALOG_CORE_TABLES_SQL + PROFILE_CORE_TABLES_SQL

# Tables owned by catalog.db; every other application table belongs to profile.db.
CATALOG_TABLES = frozenset({
    "cards",
    "cards_fts",
    "sets",
    "tracked_sets",
    "card_prices",
    "art_style_rules",
    "card_name_roles",
    "catalog_meta",
})
PROFILE_TABLES = frozenset({
    "purchases",
    "decks",
    "deck_cards",
    "storage_locations",
    "card_instances",
    "storage_breakdown_snapshots",
    "sale_listings",
    "user_settings",
})
PROFILE_SCHEMA_VERSION = 1

_schema_lock = threading.Lock()
_initialized_db_paths: set[str] = set()
_initialized_profile_paths: set[str] = set()


def _database_path(conn: sqlite3.Connection) -> str:
    return main_database_path(conn)


def _enrich_sets_from_scryfall(conn: sqlite3.Connection) -> None:
    """Load missing family child sets. Never blocks local schema bootstrap."""
    headers = {"User-Agent": HTTP_USER_AGENT}
    try:
        family_sync = ensure_tracked_family_children(conn, headers)
    except Exception:
        log.warning("Family child sync skipped", exc_info=True)
        return
    if family_sync.get("added"):
        log.info(
            "Loaded %s family child set(s): %s",
            len(family_sync["added"]),
            ", ".join(family_sync["added"]),
        )


def _run_catalog_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(CATALOG_CORE_TABLES_SQL)
    ensure_sets_table(conn)
    ensure_tracked_sets_ready(conn)
    _enrich_sets_from_scryfall(conn)
    ensure_card_prices_table(conn)
    ensure_card_indexes(conn)
    ensure_cards_fts(conn)
    ensure_catalog_meta_table(conn)
    ensure_art_style_rules_table(conn)
    ensure_card_name_roles_table(conn)


def _run_profile_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(PROFILE_CORE_TABLES_SQL)
    ensure_deck_tables(conn)
    ensure_purchase_unique_index(conn)
    ensure_app_tables(conn)
    conn.execute(f"PRAGMA main.user_version = {PROFILE_SCHEMA_VERSION}")
    conn.commit()


def _ensure_once(conn: sqlite3.Connection, done: set[str], label: str, migrate) -> None:
    db_path = _database_path(conn)
    if db_path and db_path in done:
        log.debug("%s schema ensure skipped (already initialized): %s", label, db_path)
        return
    with _schema_lock:
        if db_path and db_path in done:
            return
        started = time.perf_counter()
        log.info("Ensuring %s schema%s", label, f" for {db_path}" if db_path else "")
        migrate(conn)
        if db_path:
            done.add(db_path)
        log.info(
            "%s schema ready (%s)",
            label.capitalize(),
            format_duration(time.perf_counter() - started),
        )


def ensure_catalog_schema(conn: sqlite3.Connection) -> None:
    """Create the shared catalog. ``conn`` must have catalog.db as ``main``."""
    _ensure_once(conn, _initialized_db_paths, "catalog", _run_catalog_migrations)


def ensure_profile_schema(conn: sqlite3.Connection) -> None:
    """Migrate one profile database. ``conn`` must have profile.db as ``main``."""
    _ensure_once(conn, _initialized_profile_paths, "profile", _run_profile_migrations)


def _catalog_attached(conn: sqlite3.Connection) -> bool:
    return any(row[1] == "catalog" for row in conn.execute("PRAGMA database_list"))


def ensure_database_schema(conn: sqlite3.Connection) -> None:
    """Ensure every table ``conn`` needs.

    On a profile connection (catalog attached) only the profile schema is
    migrated; unqualified catalog DDL there would create shadow tables in
    profile.db. Otherwise this is the single-file layout used by unit tests.
    """
    if _catalog_attached(conn):
        ensure_profile_schema(conn)
        return
    db_path = _database_path(conn)
    if db_path and db_path in _initialized_db_paths and db_path in _initialized_profile_paths:
        log.debug("Schema ensure skipped (already initialized): %s", db_path)
        return
    conn.executescript(PROFILE_CORE_TABLES_SQL)
    ensure_deck_tables(conn)
    ensure_catalog_schema(conn)
    ensure_profile_schema(conn)
