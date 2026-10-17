"""Connection factory for the multi-profile storage layout.

Layout under the app data dir: ``app.db`` (profile registry), ``catalog.db``
(shared card catalog) and ``profiles/<id>/profile.db`` (per-profile state).
Profile connections open the profile file as ``main`` and attach the catalog
as ``catalog``; every table lives in exactly one file, so unqualified names
resolve without schema prefixes.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from lib.config import (
    APP_DATA_DIR,
    PROFILE_DB_FILENAME,
    is_valid_profile_id,
)
from lib.profile_context import ProfileNotFoundError, get_current_profile_id

CATALOG_SCHEMA = "catalog"


@dataclass(frozen=True)
class StorageLayout:
    root: Path

    @property
    def app_db(self) -> Path:
        return self.root / "app.db"

    @property
    def catalog_db(self) -> Path:
        return self.root / "catalog.db"

    @property
    def legacy_db(self) -> Path:
        return self.root / "collection.db"

    @property
    def profiles_dir(self) -> Path:
        return self.root / "profiles"

    @property
    def trash_dir(self) -> Path:
        return self.profiles_dir / ".trash"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    def profile_dir(self, profile_id: str) -> Path:
        if not is_valid_profile_id(profile_id):
            raise ProfileNotFoundError(profile_id)
        return self.profiles_dir / profile_id

    def profile_db(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / PROFILE_DB_FILENAME


_layout = StorageLayout(APP_DATA_DIR)
_single_db: Path | None = None


def get_layout() -> StorageLayout:
    return _layout


@contextmanager
def use_storage_root(root: Path) -> Iterator[StorageLayout]:
    """Point every connection at another app data dir (tests, tooling)."""
    global _layout
    previous = _layout
    _layout = StorageLayout(Path(root))
    try:
        yield _layout
    finally:
        _layout = previous


@contextmanager
def use_single_database(path: Path) -> Iterator[None]:
    """Serve catalog and profile tables from one file (legacy layout, unit tests)."""
    global _single_db
    previous = _single_db
    _single_db = Path(path)
    try:
        yield
    finally:
        _single_db = previous


def single_database_path() -> Path | None:
    return _single_db


def open_connection(path: Path, *, row_factory=sqlite3.Row) -> sqlite3.Connection:
    # timeout matches busy_timeout so concurrent request threads wait instead of
    # failing immediately when another writer holds the lock briefly.
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    if row_factory is not None:
        conn.row_factory = row_factory
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def connect_registry(*, row_factory=sqlite3.Row) -> sqlite3.Connection:
    return open_connection(_layout.app_db, row_factory=row_factory)


def connect_catalog(*, row_factory=sqlite3.Row) -> sqlite3.Connection:
    if _single_db is not None:
        return open_connection(_single_db, row_factory=row_factory)
    return open_connection(_layout.catalog_db, row_factory=row_factory)


def resolve_profile_id(profile_id: str | None = None) -> str:
    """Explicit id, else the request's active profile, else the registry default."""
    candidate = profile_id or get_current_profile_id()
    if candidate:
        return candidate
    from util.profile_registry import get_default_profile_id

    default_id = get_default_profile_id()
    if not default_id:
        raise ProfileNotFoundError(None)
    return default_id


def profile_db_file(profile_id: str) -> Path:
    path = _layout.profile_db(profile_id)
    if not path.is_file():
        raise ProfileNotFoundError(profile_id)
    return path


def attach_catalog(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"ATTACH DATABASE ? AS {CATALOG_SCHEMA}",
        (str(_layout.catalog_db),),
    )


def connect_profile(profile_id: str | None = None, *, row_factory=sqlite3.Row) -> sqlite3.Connection:
    if _single_db is not None:
        return open_connection(_single_db, row_factory=row_factory)
    path = profile_db_file(resolve_profile_id(profile_id))
    conn = open_connection(path, row_factory=row_factory)
    attach_catalog(conn)
    return conn


def connect_current(*, row_factory=sqlite3.Row) -> sqlite3.Connection:
    """Connection for the active profile with the shared catalog attached."""
    return connect_profile(None, row_factory=row_factory)


def table_schema(conn: sqlite3.Connection, name: str) -> str | None:
    """Schema (main, temp, catalog, ...) holding table ``name``, or None."""
    for row in conn.execute("PRAGMA database_list").fetchall():
        schema = row[1]
        found = conn.execute(
            f'SELECT 1 FROM "{schema}".sqlite_master WHERE type = \'table\' AND name = ? LIMIT 1',
            (name,),
        ).fetchone()
        if found:
            return schema
    return None


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """True when ``name`` exists in main, temp, or any attached schema."""
    return table_schema(conn, name) is not None


def is_attached_table(conn: sqlite3.Connection, name: str) -> bool:
    """True when ``name`` lives outside ``main``.

    Unqualified CREATE TABLE/INDEX always target ``main``, so schema helpers
    must skip DDL for tables owned by another file (e.g. catalog tables seen
    through a profile connection) instead of creating empty shadow copies.
    """
    schema = table_schema(conn, name)
    return schema is not None and schema != "main"


def main_database_path(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return row[2] if row else ""


@contextmanager
def session(conn_factory=connect_current) -> Iterator[sqlite3.Connection]:
    conn = conn_factory()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
