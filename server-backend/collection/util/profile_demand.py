"""Catalog demand aggregated across every profile.

Shared catalog jobs (Cardmarket price sync, orphan catalog cleanup) must price
and keep what *any* profile owns, favourites, or uses in a deck. Each profile
file is read on its own short-lived connection, so the attach limit never
applies regardless of how many profiles exist.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from lib.config import normalize_set_code
from lib.db import connect_catalog, connect_profile, single_database_path, table_exists
from lib.run_log import get_logger

log = get_logger(__name__)

PrintKey = tuple[str, str, int]


@dataclass
class CatalogDemand:
    purchase_keys: set[PrintKey] = field(default_factory=set)
    deck_owned_keys: set[PrintKey] = field(default_factory=set)
    favourite_sets: set[str] = field(default_factory=set)
    deck_set_codes: set[str] = field(default_factory=set)

    def merge(self, other: "CatalogDemand") -> None:
        self.purchase_keys |= other.purchase_keys
        self.deck_owned_keys |= other.deck_owned_keys
        self.favourite_sets |= other.favourite_sets
        self.deck_set_codes |= other.deck_set_codes

    @property
    def owned_set_codes(self) -> set[str]:
        return {key[0] for key in self.purchase_keys | self.deck_owned_keys}

    @property
    def referenced_set_codes(self) -> set[str]:
        return self.owned_set_codes | self.favourite_sets | self.deck_set_codes


def _print_keys(rows) -> set[PrintKey]:
    keys: set[PrintKey] = set()
    for set_code, collector_number, finish in rows:
        code = normalize_set_code(set_code)
        if code and collector_number is not None:
            keys.add((code, str(collector_number), int(finish or 0)))
    return keys


def _favourite_sets(conn: sqlite3.Connection) -> set[str]:
    if not table_exists(conn, "user_settings"):
        return set()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = 'favorite_sets'"
    ).fetchone()
    if not row:
        return set()
    try:
        parsed = json.loads(row[0] or "[]")
    except (TypeError, ValueError):
        log.warning("Ignoring malformed favorite_sets setting")
        return set()
    if not isinstance(parsed, list):
        return set()
    return {code for code in (normalize_set_code(str(item)) for item in parsed) if code}


def load_profile_demand(conn: sqlite3.Connection) -> CatalogDemand:
    """Demand of a single profile connection (or a legacy single-file database)."""
    demand = CatalogDemand(favourite_sets=_favourite_sets(conn))
    if table_exists(conn, "purchases"):
        demand.purchase_keys = _print_keys(
            conn.execute("SELECT set_code, collector_number, finish FROM purchases")
        )
    if table_exists(conn, "deck_cards"):
        demand.deck_owned_keys = _print_keys(
            conn.execute(
                """
                SELECT set_code, collector_number, finish FROM deck_cards
                WHERE owned_qty > 0 AND set_code IS NOT NULL AND collector_number IS NOT NULL
                """
            )
        )
        demand.deck_set_codes = {
            code
            for (raw,) in conn.execute(
                "SELECT DISTINCT set_code FROM deck_cards WHERE set_code IS NOT NULL"
            )
            if (code := normalize_set_code(raw))
        }
    return demand


def list_profile_ids() -> list[str]:
    from util.profile_registry import list_profiles

    return [profile.id for profile in list_profiles()]


def iter_profile_connections(
    *,
    exclude_profile_id: str | None = None,
    row_factory=None,
) -> Iterator[tuple[str | None, sqlite3.Connection]]:
    """Yield ``(profile_id, connection)`` one at a time; each is closed after use.

    In single-file mode the one database is yielded with a ``None`` id.
    """
    if single_database_path() is not None:
        conn = connect_catalog(row_factory=row_factory)
        try:
            yield None, conn
        finally:
            conn.close()
        return
    for profile_id in list_profile_ids():
        if profile_id == exclude_profile_id:
            continue
        conn = connect_profile(profile_id, row_factory=row_factory)
        try:
            yield profile_id, conn
        finally:
            conn.close()


def collect_catalog_demand(*, exclude_profile_id: str | None = None) -> CatalogDemand:
    """Union of demand over all registered profiles."""
    total = CatalogDemand()
    for _profile_id, conn in iter_profile_connections(exclude_profile_id=exclude_profile_id):
        total.merge(load_profile_demand(conn))
    return total


def other_profiles_demand() -> CatalogDemand:
    """Demand of every profile except the active one.

    Empty in single-file mode and when no request profile is set (unit tests
    that pass their own connection).
    """
    if single_database_path() is not None:
        return CatalogDemand()
    from lib.profile_context import get_current_profile_id

    current = get_current_profile_id()
    if not current:
        return CatalogDemand()
    return collect_catalog_demand(exclude_profile_id=current)


DEMAND_TABLES_SQL = """
CREATE TEMP TABLE IF NOT EXISTS purchases (
    set_code TEXT NOT NULL,
    collector_number TEXT NOT NULL,
    finish INTEGER NOT NULL,
    purchase_value REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (set_code, collector_number, finish)
);
CREATE TEMP TABLE IF NOT EXISTS deck_cards (
    set_code TEXT,
    collector_number TEXT,
    finish INTEGER NOT NULL DEFAULT 0,
    owned_qty INTEGER NOT NULL DEFAULT 0
);
DELETE FROM temp.purchases;
DELETE FROM temp.deck_cards;
"""


def install_demand_tables(conn: sqlite3.Connection, demand: CatalogDemand) -> None:
    """Expose cross-profile ownership as TEMP ``purchases`` / ``deck_cards``.

    The temp schema is searched first, so ownership SQL written against the
    profile tables (price sync scope, owned price history) works unchanged on
    a catalog connection.
    """
    conn.executescript(DEMAND_TABLES_SQL)
    conn.executemany(
        "INSERT OR IGNORE INTO temp.purchases (set_code, collector_number, finish) VALUES (?, ?, ?)",
        sorted(demand.purchase_keys),
    )
    conn.executemany(
        "INSERT INTO temp.deck_cards (set_code, collector_number, finish, owned_qty) VALUES (?, ?, ?, 1)",
        sorted(demand.deck_owned_keys),
    )


@contextmanager
def catalog_connection_with_demand(*, row_factory=sqlite3.Row) -> Iterator[sqlite3.Connection]:
    """Catalog connection that sees every profile's ownership (commits on success)."""
    conn = connect_catalog(row_factory=row_factory)
    try:
        if single_database_path() is None:
            install_demand_tables(conn, collect_catalog_demand())
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
