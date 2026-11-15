import sqlite3
from datetime import date

import requests

from lib.config import HTTP_USER_AGENT
from lib.db import is_attached_table, table_exists
from lib.run_log import get_logger
from util.scryfall_client import scryfall_get

log = get_logger(__name__)

SETS_TABLE_SQL = """
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

UPSERT_SET_SQL = """
INSERT INTO sets (
    set_code, name, released_at, scryfall_uri, icon_svg_uri, updated_at,
    set_type, parent_set_code, digital
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(set_code) DO UPDATE SET
    name = excluded.name,
    released_at = COALESCE(excluded.released_at, sets.released_at),
    scryfall_uri = COALESCE(excluded.scryfall_uri, sets.scryfall_uri),
    icon_svg_uri = COALESCE(excluded.icon_svg_uri, sets.icon_svg_uri),
    updated_at = excluded.updated_at,
    set_type = COALESCE(excluded.set_type, sets.set_type),
    parent_set_code = COALESCE(excluded.parent_set_code, sets.parent_set_code),
    digital = COALESCE(excluded.digital, sets.digital)
"""

UPDATE_SET_RELATIONS_SQL = """
UPDATE sets
SET set_type = ?, parent_set_code = ?
WHERE set_code = ?
"""


# Create the sets catalog table when missing.
def ensure_sets_table(conn: sqlite3.Connection) -> None:
    if is_attached_table(conn, "sets"):
        return
    conn.executescript(SETS_TABLE_SQL)


def _normalize_parent_set_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = str(value).strip().upper()
    return code or None


# Store one set row from a Scryfall set payload.
def upsert_set_row(
    cursor: sqlite3.Cursor,
    set_code: str,
    name: str,
    released_at: str | None,
    scryfall_uri: str | None,
    updated_at: str,
    icon_svg_uri: str | None = None,
    *,
    set_type: str | None = None,
    parent_set_code: str | None = None,
    digital: bool | None = None,
) -> None:
    digital_value = None if digital is None else (1 if digital else 0)
    cursor.execute(
        UPSERT_SET_SQL,
        (
            set_code.upper(),
            name,
            released_at,
            scryfall_uri,
            icon_svg_uri,
            updated_at,
            (str(set_type).strip().lower() or None) if set_type is not None else None,
            _normalize_parent_set_code(parent_set_code),
            digital_value,
        ),
    )


def update_set_relations(
    cursor: sqlite3.Cursor,
    set_code: str,
    *,
    set_type: str | None,
    parent_set_code: str | None,
) -> None:
    normalized_type = (str(set_type).strip().lower() or None) if set_type is not None else None
    cursor.execute(
        UPDATE_SET_RELATIONS_SQL,
        (
            normalized_type,
            _normalize_parent_set_code(parent_set_code),
            set_code.upper(),
        ),
    )


# Read set metadata from one Scryfall card payload.
def upsert_set_from_card(
    cursor: sqlite3.Cursor,
    card: dict,
    updated_at: str | None = None,
) -> None:
    set_code = (card.get("set") or "").upper()
    set_name = card.get("set_name")
    if not set_code or not set_name:
        return
    upsert_set_row(
        cursor,
        set_code,
        set_name,
        None,
        card.get("set_uri"),
        updated_at or date.today().isoformat(),
    )


SCRYFALL_SETS_INDEX_URL = "https://api.scryfall.com/sets"


# Fetch every set from Scryfall's paginated /sets endpoint.
def fetch_all_scryfall_sets(
    headers: dict[str, str] | None = None,
    *,
    force: bool = False,
) -> list[dict]:
    resolved_headers = headers or {"User-Agent": HTTP_USER_AGENT}
    sets: list[dict] = []
    url: str | None = SCRYFALL_SETS_INDEX_URL
    while url:
        try:
            response = scryfall_get(
                url,
                headers=resolved_headers,
                timeout=30,
                logger=log,
                label="Scryfall sets index",
                force=force,
            )
        except requests.RequestException as exc:
            log.warning("Scryfall sets index fetch failed: %s", exc)
            break
        if response.status_code != 200:
            log.error("Scryfall sets index fetch failed: HTTP %s", response.status_code)
            log.error("%s", response.text)
            break
        payload = response.json()
        sets.extend(payload.get("data") or [])
        url = payload.get("next_page") if payload.get("has_more") else None
    return sets


# Fetch one set document from the Scryfall API.
def fetch_scryfall_set(
    set_code: str,
    headers: dict[str, str],
    *,
    force: bool = False,
) -> dict | None:
    url = f"https://api.scryfall.com/sets/{set_code.lower()}"
    try:
        response = scryfall_get(
            url,
            headers=headers,
            timeout=30,
            logger=log,
            label=f"Scryfall set {set_code.upper()}",
            force=force,
        )
    except requests.RequestException as exc:
        log.warning("Scryfall set fetch failed for %s: %s", set_code.upper(), exc)
        return None
    if response.status_code != 200:
        log.error("Scryfall set fetch failed for %s: HTTP %s", set_code.upper(), response.status_code)
        log.error("%s", response.text)
        return None
    return response.json()


# Fetch and store metadata for one set code.
def sync_set_metadata(
    cursor: sqlite3.Cursor,
    set_code: str,
    headers: dict[str, str],
    updated_at: str | None = None,
    *,
    force_scryfall: bool = False,
) -> bool:
    payload = fetch_scryfall_set(set_code, headers, force=force_scryfall)
    if payload is None:
        return False
    code = (payload.get("code") or set_code).upper()
    upsert_set_row(
        cursor,
        code,
        payload.get("name") or set_code.upper(),
        payload.get("released_at"),
        payload.get("scryfall_uri"),
        updated_at or date.today().isoformat(),
        payload.get("icon_svg_uri"),
        set_type=payload.get("set_type"),
        parent_set_code=payload.get("parent_set_code"),
        digital=bool(payload.get("digital")),
    )
    # Overwrite relations so a cleared Scryfall parent is not kept via COALESCE.
    update_set_relations(
        cursor,
        code,
        set_type=payload.get("set_type"),
        parent_set_code=payload.get("parent_set_code"),
    )
    return True


# Load set display names keyed by uppercase set code.
def load_set_display_names(conn: sqlite3.Connection) -> dict[str, str]:
    ensure_sets_table(conn)
    rows = conn.execute("SELECT set_code, name FROM sets ORDER BY set_code").fetchall()
    return {set_code.upper(): name for set_code, name in rows}


# Load set metadata keyed by uppercase set code for client payloads.
def load_sets_catalog(conn: sqlite3.Connection) -> dict[str, dict]:
    ensure_sets_table(conn)
    rows = conn.execute(
        """
        SELECT set_code, name, released_at, scryfall_uri, icon_svg_uri, set_type, parent_set_code, digital
        FROM sets
        ORDER BY set_code
        """
    ).fetchall()
    return {
        set_code.upper(): {
            "name": name,
            "released_at": released_at,
            "scryfall_uri": scryfall_uri,
            "icon_svg_uri": icon_svg_uri,
            "set_type": set_type,
            "parent_set_code": parent_set_code.upper() if parent_set_code else None,
            "digital": bool(digital),
        }
        for (
            set_code,
            name,
            released_at,
            scryfall_uri,
            icon_svg_uri,
            set_type,
            parent_set_code,
            digital,
        ) in rows
    }


# Load Scryfall icon URIs keyed by uppercase set code.
def load_set_icon_uris(conn: sqlite3.Connection) -> dict[str, str]:
    ensure_sets_table(conn)
    rows = conn.execute(
        """
        SELECT set_code, icon_svg_uri
        FROM sets
        WHERE icon_svg_uri IS NOT NULL AND icon_svg_uri != ''
        ORDER BY set_code
        """
    ).fetchall()
    return {set_code.upper(): icon_svg_uri for set_code, icon_svg_uri in rows}


# Return uppercase set codes that appear in purchases.
def load_owned_set_codes(conn: sqlite3.Connection) -> list[str]:
    ensure_sets_table(conn)
    rows = conn.execute(
        "SELECT DISTINCT set_code FROM purchases ORDER BY set_code"
    ).fetchall()
    return [set_code.upper() for set_code, in rows]


# Return set codes that should stay in the local catalog (owned plus deck lists).
def load_catalog_set_codes(conn: sqlite3.Connection) -> set[str]:
    from util.deck_tables import list_deck_sync_set_codes

    owned = set(load_owned_set_codes(conn))
    deck = set(list_deck_sync_set_codes(conn))
    return owned | deck


# Return set codes that have no row in the local sets table yet.
def sets_missing_metadata(cursor: sqlite3.Cursor, set_codes: list[str]) -> list[str]:
    missing: list[str] = []
    for set_code in set_codes:
        row = cursor.execute(
            "SELECT 1 FROM sets WHERE set_code = ? LIMIT 1",
            (set_code.upper(),),
        ).fetchone()
        if not row:
            missing.append(set_code)
    return missing


# Return catalog set codes that still need a Scryfall metadata fetch.
def sets_needing_metadata_sync(cursor: sqlite3.Cursor, set_codes: list[str]) -> list[str]:
    needing: list[str] = []
    for set_code in set_codes:
        row = cursor.execute(
            """
            SELECT icon_svg_uri, set_type
            FROM sets
            WHERE set_code = ?
            LIMIT 1
            """,
            (set_code.upper(),),
        ).fetchone()
        if not row or not row[0] or row[1] is None:
            needing.append(set_code)
    return needing


# Fetch and store Scryfall metadata for owned and deck-list sets.
def sync_catalog_set_metadata(
    conn: sqlite3.Connection,
    headers: dict[str, str],
    updated_at: str | None = None,
    *,
    force_scryfall: bool = False,
) -> int:
    ensure_sets_table(conn)
    catalog_codes = sorted(load_catalog_set_codes(conn))
    if not catalog_codes:
        return 0

    cursor = conn.cursor()
    missing_codes = sets_needing_metadata_sync(cursor, catalog_codes)
    if not missing_codes:
        return 0

    stamp = updated_at or date.today().isoformat()
    synced = 0
    for set_code in missing_codes:
        if sync_set_metadata(cursor, set_code, headers, stamp, force_scryfall=force_scryfall):
            synced += 1
    return synced


# Backwards-compatible alias for owned-only callers.
def sync_owned_set_metadata(
    conn: sqlite3.Connection,
    headers: dict[str, str],
    updated_at: str | None = None,
    *,
    force_scryfall: bool = False,
) -> int:
    return sync_catalog_set_metadata(
        conn,
        headers,
        updated_at,
        force_scryfall=force_scryfall,
    )


# Remove set rows that are not owned or referenced by deck lists.
def prune_unowned_sets(conn: sqlite3.Connection) -> int:
    ensure_sets_table(conn)
    allowed = load_catalog_set_codes(conn)
    if not allowed:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sets")
        return cursor.rowcount

    placeholders = ",".join("?" for _ in allowed)
    cursor = conn.cursor()
    cursor.execute(
        f"DELETE FROM sets WHERE set_code NOT IN ({placeholders})",
        tuple(sorted(allowed)),
    )
    return cursor.rowcount
