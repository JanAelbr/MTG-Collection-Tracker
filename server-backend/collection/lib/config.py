"""Shared path configuration for the MTG collection tracker."""

import os
import re
from pathlib import Path

COLLECTION_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = COLLECTION_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = REPO_ROOT / "server-frontend"


def resolve_frontend_dist() -> Path:
    override = (os.environ.get("MTG_FRONTEND_DIST") or "").strip()
    if override:
        return Path(override)
    return FRONTEND_DIR / "dist"


FRONTEND_DIST = resolve_frontend_dist()

APP_TITLE = "MTG - Collection tracker"
HTTP_USER_AGENT = "MtgCollectionTracker/1.0"
APP_DATA_DIR_NAME = "MtgCollectionTracker"


def default_app_data_dir() -> Path:
    override = (os.environ.get("MTG_APP_DATA_DIR") or "").strip()
    if override:
        return Path(override)
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_DATA_DIR_NAME
    return Path.home() / APP_DATA_DIR_NAME


APP_DATA_DIR = default_app_data_dir()
APP_CACHE_DIR = APP_DATA_DIR / "cache"


def resolve_db_path(app_data_dir: Path | None = None) -> Path:
    """Legacy single-file database (pre multi-profile); only read by the layout migration."""
    target_dir = app_data_dir or APP_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "collection.db"


LEGACY_DB_PATH = resolve_db_path()
APP_DB_PATH = APP_DATA_DIR / "app.db"
CATALOG_DB_PATH = APP_DATA_DIR / "catalog.db"
PROFILES_DIR = APP_DATA_DIR / "profiles"
PROFILES_TRASH_DIR = PROFILES_DIR / ".trash"
BACKUPS_DIR = APP_DATA_DIR / "backups"
PROFILE_DB_FILENAME = "profile.db"
PROFILE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def is_valid_profile_id(profile_id: str | None) -> bool:
    return bool(profile_id) and bool(PROFILE_ID_PATTERN.match(str(profile_id)))


def profile_dir(profile_id: str, profiles_dir: Path | None = None) -> Path:
    if not is_valid_profile_id(profile_id):
        raise ValueError(f"Invalid profile id: {profile_id!r}")
    return (profiles_dir or PROFILES_DIR) / profile_id


def profile_db_path(profile_id: str, profiles_dir: Path | None = None) -> Path:
    return profile_dir(profile_id, profiles_dir) / PROFILE_DB_FILENAME


DATA_DIR = REPO_ROOT / "data"
ART_STYLES_DIR = DATA_DIR / "art_styles"

EXCLUDED_SET_CODES = frozenset({"EXAMPLE"})

# Legacy or mistaken set codes mapped to Scryfall's canonical code.
SET_CODE_ALIASES: dict[str, str] = {
    "PLIST": "PLST",
}


def normalize_set_code(set_code: str | None) -> str:
    normalized = str(set_code or "").strip().upper()
    if not normalized:
        return ""
    return SET_CODE_ALIASES.get(normalized, normalized)


def canonical_set_code_lower(set_code: str | None) -> str:
    return normalize_set_code(set_code).lower()
