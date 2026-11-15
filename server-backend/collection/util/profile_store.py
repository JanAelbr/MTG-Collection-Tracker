"""File-level operations on profile databases (create, duplicate, trash, size)."""

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lib.db import attach_catalog, get_layout, open_connection
from lib.run_log import get_logger

log = get_logger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sqlite_copy(source: Path, target: Path) -> None:
    """Consistent copy (includes WAL content) via the SQLite online backup API."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def initialize_profile_database(profile_id: str) -> Path:
    """Create (or migrate) the profile file and its schema."""
    from util.schema import ensure_profile_schema

    path = get_layout().profile_db(profile_id)
    conn = open_connection(path)
    try:
        attach_catalog(conn)
        ensure_profile_schema(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def duplicate_profile_database(source_id: str, target_id: str) -> Path:
    layout = get_layout()
    target = layout.profile_db(target_id)
    sqlite_copy(layout.profile_db(source_id), target)
    return initialize_profile_database(target_id)


def _attached_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    source = {row[1] for row in conn.execute(f"PRAGMA source.table_info({table})")}
    target = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return [name for name in target if name in source]


def _copy_rows(conn: sqlite3.Connection, table: str, where_sql: str = "", params: tuple = ()) -> None:
    columns = _attached_columns(conn, table)
    if not columns:
        return
    listed = ", ".join(columns)
    conn.execute(
        f"INSERT INTO {table} ({listed}) SELECT {listed} FROM source.{table} {where_sql}",
        params,
    )


_STORAGE_SOLUTION_WHERE = """
WHERE location_type != 'deck' AND location_slug NOT LIKE 'deck:%'
"""


def _copy_locations(conn: sqlite3.Connection, where_sql: str, *, clear_deck_id: bool) -> None:
    columns = _attached_columns(conn, "storage_locations")
    if not columns:
        return
    selected = ", ".join(
        "NULL" if clear_deck_id and name == "deck_id" else name for name in columns
    )
    listed = ", ".join(columns)
    conn.execute(
        f"INSERT INTO storage_locations ({listed}) SELECT {selected} FROM source.storage_locations {where_sql}"
    )


def _replace_storage_solutions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        DELETE FROM storage_locations
        WHERE location_type != 'deck' AND location_slug NOT LIKE 'deck:%'
        """
    )
    _copy_locations(conn, _STORAGE_SOLUTION_WHERE, clear_deck_id=True)


def _copy_decks(conn: sqlite3.Connection) -> None:
    _copy_rows(conn, "decks")
    _copy_rows(conn, "deck_cards")
    _copy_locations(
        conn,
        "WHERE location_type = 'deck' OR location_slug LIKE 'deck:%'",
        clear_deck_id=False,
    )


def _copy_missing_instance_locations(conn: sqlite3.Connection) -> None:
    _copy_locations(
        conn,
        """
        WHERE location_slug IN (SELECT location_slug FROM source.card_instances)
          AND location_slug NOT IN (SELECT location_slug FROM storage_locations)
        """,
        clear_deck_id=True,
    )


def _copy_collection(conn: sqlite3.Connection) -> None:
    _copy_missing_instance_locations(conn)
    _copy_rows(conn, "purchases")
    _copy_rows(conn, "card_instances")


def _copy_default_storage_setting(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        """
        SELECT value FROM source.user_settings
        WHERE key = 'default_storage_location'
        """
    ).fetchone()
    if row is None:
        return
    slug = row[0]
    exists = conn.execute(
        "SELECT 1 FROM storage_locations WHERE location_slug = ?",
        (slug,),
    ).fetchone()
    if exists is None:
        return
    conn.execute(
        """
        INSERT INTO user_settings (key, value) VALUES ('default_storage_location', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (slug,),
    )


def copy_profile_parts(source_id: str, target_id: str, parts: set[str]) -> None:
    """Copy selected pieces into an already initialized profile database."""
    conn = open_connection(get_layout().profile_db(target_id), row_factory=None)
    try:
        conn.execute("ATTACH DATABASE ? AS source", (str(get_layout().profile_db(source_id)),))
        if "storage" in parts:
            _replace_storage_solutions(conn)
        if "decks" in parts:
            _copy_decks(conn)
        if "collection" in parts:
            _copy_collection(conn)
        if "storage" in parts or "collection" in parts:
            _copy_default_storage_setting(conn)
        conn.commit()
    finally:
        conn.close()


def trash_profile_database(profile_id: str) -> Path | None:
    """Soft delete: move the profile folder into ``profiles/.trash``."""
    layout = get_layout()
    source = layout.profile_dir(profile_id)
    if not source.exists():
        return None
    layout.trash_dir.mkdir(parents=True, exist_ok=True)
    target = layout.trash_dir / f"{profile_id}-{_timestamp()}"
    shutil.move(str(source), str(target))
    log.info("Moved profile %s to %s", profile_id, target)
    return target


def discard_profile_database(profile_id: str) -> None:
    """Remove files of a profile that was never registered (failed create/import)."""
    shutil.rmtree(get_layout().profile_dir(profile_id), ignore_errors=True)


def profile_disk_size(profile_id: str) -> int:
    folder = get_layout().profile_dir(profile_id)
    if not folder.is_dir():
        return 0
    return sum(item.stat().st_size for item in folder.iterdir() if item.is_file())
