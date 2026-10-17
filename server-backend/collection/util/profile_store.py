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
