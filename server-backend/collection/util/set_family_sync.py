"""Ensure Scryfall family siblings are tracked for families already in the DB."""

from __future__ import annotations

import sqlite3

from lib.config import EXCLUDED_SET_CODES, HTTP_USER_AGENT, normalize_set_code
from lib.run_log import get_logger
from util.scryfall_catalog_sync import import_set_catalog_from_scryfall
from util.set_catalog import fetch_all_scryfall_sets
from util.set_families import (
    relations_from_scryfall_sets,
    scryfall_family_members,
    scryfall_family_root,
)
from util.tracked_sets import add_tracked_set, is_set_tracked, list_tracked_set_codes

log = get_logger(__name__)

# Auto-imported family children (not promos / alchemy / etc.).
AUTO_LOAD_CHILD_TYPES = frozenset({
    "commander",
    "token",
    "memorabilia",
    "minigame",
})

_children_ensured_dbs: set[str] = set()


def _connection_db_path(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        if row and len(row) >= 3 and row[2]:
            return str(row[2])
    except sqlite3.Error:
        pass
    return ""


def ensure_tracked_family_children(
    conn: sqlite3.Connection,
    headers: dict[str, str] | None = None,
    *,
    force_scryfall: bool = False,
) -> dict:
    """
    For every tracked set, import missing Scryfall family children of selected types
    (commander, token, memorabilia, minigame).

    Returns {added: [...], skipped: int, families: int}.
    """
    tracked = [
        code
        for code in (normalize_set_code(raw) for raw in list_tracked_set_codes(conn))
        if code and code not in EXCLUDED_SET_CODES
    ]
    if not tracked:
        return {"added": [], "skipped": 0, "families": 0}

    resolved_headers = headers or {"User-Agent": HTTP_USER_AGENT}
    scryfall_sets = fetch_all_scryfall_sets(resolved_headers, force=force_scryfall)
    relations = relations_from_scryfall_sets(scryfall_sets)
    roots = {
        scryfall_family_root(code, relations)
        for code in tracked
        if scryfall_family_root(code, relations)
    }

    added: list[str] = []
    skipped = 0
    for root in sorted(roots):
        members = [
            code
            for code in scryfall_family_members(root, relations=relations)
            if code and code not in EXCLUDED_SET_CODES and code.isalnum()
        ]
        for code in members:
            if code == root or is_set_tracked(conn, code):
                continue
            set_type = (relations.get(code) or {}).get("set_type") or ""
            if set_type not in AUTO_LOAD_CHILD_TYPES:
                skipped += 1
                continue
            try:
                add_tracked_set(conn, code)
                import_set_catalog_from_scryfall(conn, code)
                added.append(code)
                log.info("Loaded family child set %s (%s, family %s)", code, set_type, root)
            except ValueError as exc:
                log.warning("Could not load family child %s: %s", code, exc)
                from util.tracked_sets import remove_tracked_set

                remove_tracked_set(conn, code)

    if added:
        conn.commit()
        try:
            from api.cache import bump_cache_epoch

            bump_cache_epoch()
        except Exception:
            pass
    return {"added": added, "skipped": skipped, "families": len(roots)}


def ensure_tracked_family_children_once(
    conn: sqlite3.Connection,
    headers: dict[str, str] | None = None,
    *,
    force_scryfall: bool = False,
) -> dict:
    """Run ensure_tracked_family_children at most once per DB path per process."""
    db_path = _connection_db_path(conn) or "default"
    if db_path in _children_ensured_dbs:
        return {"added": [], "skipped": 0, "families": 0}
    result = ensure_tracked_family_children(
        conn,
        headers,
        force_scryfall=force_scryfall,
    )
    _children_ensured_dbs.add(db_path)
    return result
