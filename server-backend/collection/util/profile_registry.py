"""Profile registry (``app.db``): which profiles exist and their display metadata."""

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from lib.db import connect_registry, get_layout, main_database_path

PROFILE_NAME_MAX_LENGTH = 40
PROFILE_AVATAR_MAX_LENGTH = 4
PROFILE_COLORS = (
    "indigo",
    "teal",
    "emerald",
    "amber",
    "orange",
    "rose",
    "violet",
    "sky",
    "slate",
    "lime",
)
DEFAULT_PROFILE_NAME = "My collection"

REGISTRY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    color TEXT NOT NULL,
    avatar TEXT NOT NULL DEFAULT '',
    is_default INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used_at TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

PROFILE_COLUMNS = (
    "id, name, color, avatar, is_default, sort_order, created_at, updated_at, last_used_at"
)


class ProfileValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    color: str
    avatar: str
    is_default: bool
    sort_order: int
    created_at: str
    updated_at: str
    last_used_at: str | None

    def to_api(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "avatar": self.avatar or profile_initials(self.name),
            "isDefault": self.is_default,
            "sortOrder": self.sort_order,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "lastUsedAt": self.last_used_at,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_profile_id() -> str:
    return uuid.uuid4().hex


def profile_initials(name: str) -> str:
    words = [word for word in str(name or "").split() if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def _row_to_profile(row) -> Profile:
    return Profile(
        id=row[0],
        name=row[1],
        color=row[2],
        avatar=row[3] or "",
        is_default=bool(row[4]),
        sort_order=int(row[5] or 0),
        created_at=row[6],
        updated_at=row[7],
        last_used_at=row[8],
    )


def ensure_registry_schema(conn: sqlite3.Connection | None = None) -> None:
    if conn is not None:
        conn.executescript(REGISTRY_SCHEMA_SQL)
        return
    with _registry() as own:
        own.executescript(REGISTRY_SCHEMA_SQL)


_lock = threading.Lock()
_ensured_paths: set[str] = set()
_profiles_cache: dict[str, tuple[Profile, ...]] = {}


def invalidate_profile_cache() -> None:
    with _lock:
        _profiles_cache.clear()


class _registry:
    """Short-lived registry connection that commits on success and always closes.

    Writes (``write=True``) invalidate the in-process profile list cache.
    """

    def __init__(self, *, write: bool = False) -> None:
        self.write = write

    def __enter__(self) -> sqlite3.Connection:
        self.conn = connect_registry(row_factory=None)
        path = main_database_path(self.conn)
        if path not in _ensured_paths:
            self.conn.executescript(REGISTRY_SCHEMA_SQL)
            _ensured_paths.add(path)
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
            if self.write:
                invalidate_profile_cache()


def normalize_profile_name(name: str | None) -> str:
    cleaned = " ".join(str(name or "").split())
    if not cleaned:
        raise ProfileValidationError("Profile name is required")
    if len(cleaned) > PROFILE_NAME_MAX_LENGTH:
        raise ProfileValidationError(
            f"Profile name must be at most {PROFILE_NAME_MAX_LENGTH} characters"
        )
    return cleaned


def normalize_profile_color(color: str | None, *, fallback_index: int = 0) -> str:
    value = str(color or "").strip().lower()
    if not value:
        return PROFILE_COLORS[fallback_index % len(PROFILE_COLORS)]
    if value not in PROFILE_COLORS:
        raise ProfileValidationError(f"Unknown profile color: {color}")
    return value


def normalize_profile_avatar(avatar: str | None) -> str:
    value = str(avatar or "").strip()
    if len(value) > PROFILE_AVATAR_MAX_LENGTH:
        raise ProfileValidationError(
            f"Avatar must be at most {PROFILE_AVATAR_MAX_LENGTH} characters"
        )
    return value


def list_profiles() -> list[Profile]:
    cache_key = str(get_layout().app_db)
    with _lock:
        cached = _profiles_cache.get(cache_key)
    if cached is not None:
        return list(cached)
    with _registry() as conn:
        rows = conn.execute(
            f"SELECT {PROFILE_COLUMNS} FROM profiles ORDER BY sort_order, created_at, name"
        ).fetchall()
    profiles = tuple(_row_to_profile(row) for row in rows)
    with _lock:
        _profiles_cache[cache_key] = profiles
    return list(profiles)


def get_profile(profile_id: str | None) -> Profile | None:
    if not profile_id:
        return None
    return next((profile for profile in list_profiles() if profile.id == profile_id), None)


def get_default_profile_id() -> str | None:
    profiles = list_profiles()
    if not profiles:
        return None
    default = next((profile for profile in profiles if profile.is_default), profiles[0])
    return default.id


def _name_taken(conn: sqlite3.Connection, name: str, *, exclude_id: str | None = None) -> bool:
    row = conn.execute(
        "SELECT 1 FROM profiles WHERE name = ? COLLATE NOCASE AND id != ? LIMIT 1",
        (name, exclude_id or ""),
    ).fetchone()
    return row is not None


def validate_new_profile(
    *,
    name: str,
    color: str | None = None,
    avatar: str | None = None,
) -> None:
    """Raise ProfileValidationError before any profile files are created."""
    clean_name = normalize_profile_name(name)
    normalize_profile_color(color)
    normalize_profile_avatar(avatar)
    if any(profile.name.casefold() == clean_name.casefold() for profile in list_profiles()):
        raise ProfileValidationError(f"A profile named '{clean_name}' already exists")


def insert_profile(
    *,
    name: str,
    color: str | None = None,
    avatar: str | None = None,
    is_default: bool = False,
    profile_id: str | None = None,
) -> Profile:
    clean_name = normalize_profile_name(name)
    clean_avatar = normalize_profile_avatar(avatar)
    now = _utc_now()
    new_id = profile_id or new_profile_id()
    with _registry(write=True) as conn:
        if _name_taken(conn, clean_name):
            raise ProfileValidationError(f"A profile named '{clean_name}' already exists")
        count, max_order = conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(sort_order), -1) FROM profiles"
        ).fetchone()
        clean_color = normalize_profile_color(color, fallback_index=int(count))
        make_default = is_default or int(count) == 0
        if make_default:
            conn.execute("UPDATE profiles SET is_default = 0")
        conn.execute(
            f"""
            INSERT INTO profiles ({PROFILE_COLUMNS})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (new_id, clean_name, clean_color, clean_avatar, int(make_default),
             int(max_order) + 1, now, now),
        )
    profile = get_profile(new_id)
    assert profile is not None
    return profile


def update_profile(
    profile_id: str,
    *,
    name: str | None = None,
    color: str | None = None,
    avatar: str | None = None,
    is_default: bool | None = None,
) -> Profile | None:
    with _registry(write=True) as conn:
        exists = conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not exists:
            return None
        assignments: list[str] = []
        params: list = []
        if name is not None:
            clean_name = normalize_profile_name(name)
            if _name_taken(conn, clean_name, exclude_id=profile_id):
                raise ProfileValidationError(f"A profile named '{clean_name}' already exists")
            assignments.append("name = ?")
            params.append(clean_name)
        if color is not None:
            assignments.append("color = ?")
            params.append(normalize_profile_color(color))
        if avatar is not None:
            assignments.append("avatar = ?")
            params.append(normalize_profile_avatar(avatar))
        if is_default:
            conn.execute("UPDATE profiles SET is_default = 0")
            assignments.append("is_default = 1")
        if assignments:
            assignments.append("updated_at = ?")
            params.append(_utc_now())
            conn.execute(
                f"UPDATE profiles SET {', '.join(assignments)} WHERE id = ?",
                (*params, profile_id),
            )
    return get_profile(profile_id)


def delete_profile_row(profile_id: str) -> bool:
    with _registry(write=True) as conn:
        row = conn.execute(
            "SELECT is_default FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        if row[0]:
            conn.execute(
                """
                UPDATE profiles SET is_default = 1
                WHERE id = (SELECT id FROM profiles ORDER BY sort_order, created_at LIMIT 1)
                """
            )
    return True


def reorder_profiles(profile_ids: list[str]) -> list[Profile]:
    """Apply a display order; ids not listed keep their relative order after."""
    known = [profile.id for profile in list_profiles()]
    ordered = [pid for pid in dict.fromkeys(profile_ids) if pid in known]
    ordered += [pid for pid in known if pid not in ordered]
    with _registry(write=True) as conn:
        conn.executemany(
            "UPDATE profiles SET sort_order = ? WHERE id = ?",
            [(index, pid) for index, pid in enumerate(ordered)],
        )
    return list_profiles()


def unique_profile_name(base: str) -> str:
    """``base`` or ``base (2)``, ``base (3)``... whichever is free."""
    clean = normalize_profile_name(base)
    taken = {profile.name.casefold() for profile in list_profiles()}
    if clean.casefold() not in taken:
        return clean
    index = 2
    while True:
        suffix = f" ({index})"
        candidate = clean[: PROFILE_NAME_MAX_LENGTH - len(suffix)].rstrip() + suffix
        if candidate.casefold() not in taken:
            return candidate
        index += 1


def touch_profile_last_used(profile_id: str) -> None:
    with _registry(write=True) as conn:
        conn.execute(
            "UPDATE profiles SET last_used_at = ? WHERE id = ?",
            (_utc_now(), profile_id),
        )


def get_app_meta(key: str) -> str:
    with _registry() as conn:
        row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else ""


def set_app_meta(key: str, value: str) -> None:
    with _registry(write=True) as conn:
        conn.execute(
            """
            INSERT INTO app_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
