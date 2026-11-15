"""Storage layout bootstrap.

Layout v2: ``app.db`` (registry) + ``catalog.db`` (shared catalog) +
``profiles/<id>/profile.db`` (per-profile state).
"""

import sqlite3

from lib.db import connect_profile, get_layout
from lib.run_log import get_logger
from util.profile_registry import (
    DEFAULT_PROFILE_NAME,
    ensure_registry_schema,
    get_app_meta,
    insert_profile,
    list_profiles,
    set_app_meta,
)
from util.profile_store import initialize_profile_database

log = get_logger(__name__)

LAYOUT_VERSION_KEY = "storage_layout_version"
LAYOUT_VERSION = "2"


def ensure_storage_layout() -> None:
    """Create app.db, catalog.db, and the profile directory layout."""
    layout = get_layout()
    layout.root.mkdir(parents=True, exist_ok=True)
    ensure_registry_schema()
    if get_app_meta(LAYOUT_VERSION_KEY) != LAYOUT_VERSION:
        set_app_meta(LAYOUT_VERSION_KEY, LAYOUT_VERSION)


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
