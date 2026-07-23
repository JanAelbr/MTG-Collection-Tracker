import sqlite3
from datetime import date

from lib.config import HTTP_USER_AGENT
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
    set_type TEXT,
    parent_set_code TEXT
);
"""

SET_COLUMNS = {
    "icon_svg_uri": "TEXT",
    "catalog_synced_at": "TEXT",
    "set_type": "TEXT",
    "parent_set_code": "TEXT",
}

UPSERT_SET_SQL = """
INSERT INTO sets (
    set_code, name, released_at, scryfall_uri, icon_svg_uri, updated_at,
    set_type, parent_set_code
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(set_code) DO UPDATE SET
    name = excluded.name,
    released_at = COALESCE(excluded.released_at, sets.released_at),
    scryfall_uri = COALESCE(excluded.scryfall_uri, sets.scryfall_uri),
    icon_svg_uri = COALESCE(excluded.icon_svg_uri, sets.icon_svg_uri),
    updated_at = excluded.updated_at,
    set_type = COALESCE(excluded.set_type, sets.set_type),
    parent_set_code = COALESCE(excluded.parent_set_code, sets.parent_set_code)
"""

UPDATE_SET_RELATIONS_SQL = """
UPDATE sets
SET set_type = ?, parent_set_code = ?
WHERE set_code = ?
"""


# Create the sets catalog table when missing.
def ensure_sets_table(conn: sqlite3.Connection) -> None:
    conn.executescript(SETS_TABLE_SQL)


# Add missing sets columns without recreating the database.
def ensure_sets_columns(conn: sqlite3.Connection) -> None:
    ensure_sets_table(conn)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(sets)")
    existing = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in SET_COLUMNS.items():
        if column_name in existing:
            continue
        cursor.execute(f"ALTER TABLE sets ADD COLUMN {column_name} {column_type}")


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
) -> None:
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
        response = scryfall_get(
            url,
            headers=resolved_headers,
            timeout=30,
            logger=log,
            label="Scryfall sets index",
            force=force,
        )
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
    response = scryfall_get(
        url,
        headers=headers,
        timeout=30,
        logger=log,
        label=f"Scryfall set {set_code.upper()}",
        force=force,
    )
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
    ensure_sets_columns(conn)
    rows = conn.execute(
        """
        SELECT set_code, name, released_at, scryfall_uri, icon_svg_uri, set_type, parent_set_code
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
        }
        for (
            set_code,
            name,
            released_at,
            scryfall_uri,
            icon_svg_uri,
            set_type,
            parent_set_code,
        ) in rows
    }


# Load Scryfall icon URIs keyed by uppercase set code.
def load_set_icon_uris(conn: sqlite3.Connection) -> dict[str, str]:
    ensure_sets_table(conn)
    ensure_sets_columns(conn)
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


# Return distinct catalog set codes that do not have a stored icon URI yet.
def load_set_codes_missing_icon(conn: sqlite3.Connection) -> list[str]:
    ensure_sets_table(conn)
    ensure_sets_columns(conn)
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cards' LIMIT 1"
    ).fetchone():
        return []
    rows = conn.execute(
        """
        SELECT DISTINCT c.set_code
        FROM cards c
        LEFT JOIN sets s ON s.set_code = c.set_code
        WHERE COALESCE(s.icon_svg_uri, '') = ''
        ORDER BY c.set_code
        """
    ).fetchall()
    return [set_code.upper() for set_code, in rows]


# Return tracked/owned/deck set codes that still need Scryfall type/parent metadata.
def load_set_codes_missing_relations(conn: sqlite3.Connection) -> list[str]:
    ensure_sets_table(conn)
    ensure_sets_columns(conn)
    from util.tracked_sets import list_tracked_set_codes

    candidates: set[str] = set(load_catalog_set_codes(conn))
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tracked_sets' LIMIT 1"
    ).fetchone():
        for raw in list_tracked_set_codes(conn):
            code = (raw or "").upper()
            if code:
                candidates.add(code)

    needing: list[str] = []
    for code in sorted(candidates):
        row = conn.execute(
            "SELECT set_type FROM sets WHERE set_code = ? LIMIT 1",
            (code,),
        ).fetchone()
        if not row or row[0] is None or not str(row[0]).strip():
            needing.append(code)
    return needing


# Apply set_type / parent_set_code from one Scryfall /sets index payload list.
def apply_scryfall_set_relations(
    conn: sqlite3.Connection,
    scryfall_sets: list[dict],
    *,
    only_codes: set[str] | None = None,
) -> int:
    ensure_sets_table(conn)
    ensure_sets_columns(conn)
    cursor = conn.cursor()
    stamp = date.today().isoformat()
    updated = 0
    for item in scryfall_sets or []:
        code = (item.get("code") or "").upper()
        if not code:
            continue
        if only_codes is not None and code not in only_codes:
            continue
        name = item.get("name") or code
        exists = cursor.execute(
            "SELECT 1 FROM sets WHERE set_code = ? LIMIT 1",
            (code,),
        ).fetchone()
        if exists:
            update_set_relations(
                cursor,
                code,
                set_type=item.get("set_type"),
                parent_set_code=item.get("parent_set_code"),
            )
            if item.get("icon_svg_uri"):
                cursor.execute(
                    """
                    UPDATE sets
                    SET icon_svg_uri = COALESCE(?, icon_svg_uri),
                        name = COALESCE(?, name),
                        released_at = COALESCE(?, released_at),
                        scryfall_uri = COALESCE(?, scryfall_uri),
                        updated_at = ?
                    WHERE set_code = ?
                    """,
                    (
                        item.get("icon_svg_uri"),
                        name,
                        item.get("released_at"),
                        item.get("scryfall_uri"),
                        stamp,
                        code,
                    ),
                )
        else:
            upsert_set_row(
                cursor,
                code,
                name,
                item.get("released_at"),
                item.get("scryfall_uri"),
                stamp,
                item.get("icon_svg_uri"),
                set_type=item.get("set_type"),
                parent_set_code=item.get("parent_set_code"),
            )
            update_set_relations(
                cursor,
                code,
                set_type=item.get("set_type"),
                parent_set_code=item.get("parent_set_code"),
            )
        updated += 1
    return updated


# Fetch and store icon URIs for catalog sets that are missing them.
def backfill_missing_set_icon_uris(
    conn: sqlite3.Connection,
    headers: dict[str, str],
    *,
    force_scryfall: bool = False,
) -> int:
    codes = load_set_codes_missing_icon(conn)
    if not codes:
        return 0

    cursor = conn.cursor()
    stamp = date.today().isoformat()
    synced = 0
    for set_code in codes:
        if sync_set_metadata(cursor, set_code, headers, stamp, force_scryfall=force_scryfall):
            synced += 1
    return synced


# Fetch set_type / parent_set_code for tracked sets that still lack Scryfall relations.
def backfill_missing_set_relations(
    conn: sqlite3.Connection,
    headers: dict[str, str],
    *,
    force_scryfall: bool = False,
) -> int:
    codes = load_set_codes_missing_relations(conn)
    if not codes:
        return 0

    # Prefer one bulk /sets fetch over N per-set requests.
    scryfall_sets = fetch_all_scryfall_sets(headers, force=force_scryfall)
    if scryfall_sets:
        updated = apply_scryfall_set_relations(
            conn,
            scryfall_sets,
            only_codes=set(codes),
        )
        conn.commit()
        if updated:
            log.info("Backfilled Scryfall set relations for %s set(s)", updated)
        return updated

    cursor = conn.cursor()
    stamp = date.today().isoformat()
    synced = 0
    for set_code in codes:
        if sync_set_metadata(cursor, set_code, headers, stamp, force_scryfall=force_scryfall):
            synced += 1
    if synced:
        conn.commit()
        log.info("Backfilled Scryfall set relations for %s set(s)", synced)
    return synced


# Fetch and store Scryfall metadata for owned and deck-list sets.
def sync_catalog_set_metadata(
    conn: sqlite3.Connection,
    headers: dict[str, str],
    updated_at: str | None = None,
    *,
    force_scryfall: bool = False,
) -> int:
    ensure_sets_table(conn)
    ensure_sets_columns(conn)
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
