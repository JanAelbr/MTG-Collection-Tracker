"""Storage layout bootstrap and the one-time split of the legacy collection.db.

Layout v2: ``app.db`` (registry) + ``catalog.db`` (shared catalog) +
``profiles/<id>/profile.db`` (per-profile state). The legacy single file is
split by copying it twice and pruning each copy, working on ``.tmp`` files
that are only renamed into place once complete.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lib.db import StorageLayout, connect_profile, get_layout
from lib.run_log import get_logger
from util.profile_registry import (
    DEFAULT_PROFILE_NAME,
    ensure_registry_schema,
    get_app_meta,
    insert_profile,
    list_profiles,
    new_profile_id,
    set_app_meta,
)
from util.profile_store import initialize_profile_database, sqlite_copy
from util.schema import PROFILE_TABLES

log = get_logger(__name__)

LAYOUT_VERSION_KEY = "storage_layout_version"
LAYOUT_VERSION = "2"
SYSTEM_SETTING_KEYS = (
    "price_sync_checked_date",
    "card_name_roles_backfill_v1",
    "card_detail_metadata_reload_v1",
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _user_tables(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return [
        (row[0], row[1] or "")
        for row in conn.execute(
            """
            SELECT name, sql FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    ]


def _drop_tables(conn: sqlite3.Connection, names: list[str]) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    tables = dict(_user_tables(conn))
    # Virtual tables first: dropping them also removes their shadow tables.
    ordered = sorted(names, key=lambda name: "VIRTUAL" not in tables.get(name, "").upper())
    for name in ordered:
        if name in dict(_user_tables(conn)):
            conn.execute(f'DROP TABLE IF EXISTS "{name}"')


def _prune_profile_copy(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        catalog_tables = [name for name, _ in _user_tables(conn) if name not in PROFILE_TABLES]
        _drop_tables(conn, catalog_tables)
        placeholders = ",".join("?" for _ in SYSTEM_SETTING_KEYS)
        if "user_settings" in dict(_user_tables(conn)):
            conn.execute(
                f"DELETE FROM user_settings WHERE key IN ({placeholders})",
                SYSTEM_SETTING_KEYS,
            )
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


def _prune_catalog_copy(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        tables = dict(_user_tables(conn))
        system_values: list[tuple[str, str]] = []
        if "user_settings" in tables:
            placeholders = ",".join("?" for _ in SYSTEM_SETTING_KEYS)
            system_values = [
                (row[0], row[1])
                for row in conn.execute(
                    f"SELECT key, value FROM user_settings WHERE key IN ({placeholders})",
                    SYSTEM_SETTING_KEYS,
                )
            ]
        _drop_tables(conn, [name for name in tables if name in PROFILE_TABLES])
        conn.execute(
            "CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO catalog_meta (key, value) VALUES (?, ?)",
            system_values,
        )
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


def _checkpoint(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def migrate_legacy_database(layout: StorageLayout) -> str:
    """Split ``collection.db`` into catalog.db + one profile. Returns the profile id."""
    legacy = layout.legacy_db
    log.info("Migrating legacy database %s to the multi-profile layout", legacy)
    _checkpoint(legacy)
    profile_id = new_profile_id()
    profile_tmp = layout.profile_dir(profile_id) / "profile.db.tmp"
    catalog_tmp = layout.root / "catalog.db.tmp"

    sqlite_copy(legacy, profile_tmp)
    _prune_profile_copy(profile_tmp)
    sqlite_copy(legacy, catalog_tmp)
    _prune_catalog_copy(catalog_tmp)

    os.replace(catalog_tmp, layout.catalog_db)
    os.replace(profile_tmp, layout.profile_db(profile_id))
    insert_profile(name=DEFAULT_PROFILE_NAME, profile_id=profile_id, is_default=True)
    log.info("Legacy collection migrated into profile %s", profile_id)
    return profile_id


def _archive_legacy_database(layout: StorageLayout) -> None:
    """Keep the pre-migration file as a backup once the split is committed."""
    legacy = layout.legacy_db
    if not legacy.is_file():
        return
    _checkpoint(legacy)
    layout.backups_dir.mkdir(parents=True, exist_ok=True)
    target = layout.backups_dir / f"collection-pre-profiles-{_timestamp()}.db"
    os.replace(legacy, target)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{legacy}{suffix}")
        if sidecar.exists():
            sidecar.unlink()
    log.info("Archived legacy database to %s", target)


def ensure_storage_layout() -> None:
    """Create or migrate files so app.db, catalog.db and >=1 profile exist."""
    layout = get_layout()
    layout.root.mkdir(parents=True, exist_ok=True)
    ensure_registry_schema()
    if get_app_meta(LAYOUT_VERSION_KEY) != LAYOUT_VERSION:
        if layout.legacy_db.is_file() and not list_profiles():
            migrate_legacy_database(layout)
        set_app_meta(LAYOUT_VERSION_KEY, LAYOUT_VERSION)
    _archive_legacy_database(layout)


def _ensure_catalog() -> None:
    from util.profile_demand import catalog_connection_with_demand
    from util.schema import ensure_catalog_schema

    with catalog_connection_with_demand() as conn:
        ensure_catalog_schema(conn)


def _relink_profile_decks(profile_id: str) -> None:
    """Resolve deck prints against catalog sets loaded by shared jobs."""
    from util.deck_helpers import relink_unresolved_deck_cards
    from util.tracked_sets import list_tracked_set_codes

    conn = connect_profile(profile_id)
    try:
        relink_unresolved_deck_cards(conn, list_tracked_set_codes(conn))
        conn.commit()
    finally:
        conn.close()


def bootstrap_storage() -> list[str]:
    """Run at API startup. Returns ids of every usable profile."""
    ensure_storage_layout()
    _ensure_catalog()
    if not list_profiles():
        profile = insert_profile(name=DEFAULT_PROFILE_NAME, is_default=True)
        log.info("Created default profile %s", profile.id)
    ready: list[str] = []
    for profile in list_profiles():
        try:
            initialize_profile_database(profile.id)
            _relink_profile_decks(profile.id)
        except sqlite3.Error:
            log.exception("Profile %s (%s) could not be opened", profile.name, profile.id)
            continue
        ready.append(profile.id)
    return ready
