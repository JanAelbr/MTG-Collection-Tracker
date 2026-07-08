"""Shared path configuration for the MTG collection tracker."""

import os
from pathlib import Path

COLLECTION_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = COLLECTION_DIR.parent.parent / "scripts"
REPO_ROOT = SCRIPTS_DIR.parent
BACKEND_DIR = COLLECTION_DIR.parent
FRONTEND_DIR = REPO_ROOT / "server-frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

APP_TITLE = "MTG - Collection tracker"
HTTP_USER_AGENT = "MtgCollectionTracker/1.0"
APP_DATA_DIR_NAME = "MtgCollectionTracker"


def default_app_data_dir() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_DATA_DIR_NAME
    return Path.home() / APP_DATA_DIR_NAME


APP_DATA_DIR = default_app_data_dir()
APP_CACHE_DIR = APP_DATA_DIR / "cache"


def resolve_db_path(app_data_dir: Path | None = None) -> Path:
    target_dir = app_data_dir or APP_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "collection.db"


DB_PATH = resolve_db_path()
DATA_DIR = REPO_ROOT / "data"
ART_STYLES_DIR = DATA_DIR / "art_styles"
LOGS_DIR = REPO_ROOT / "logs"

CREATE_DB_SCRIPT = SCRIPTS_DIR / "db" / "create_db.py"
UPDATE_PRICES_SCRIPT = SCRIPTS_DIR / "update_prices.py"

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


# Return the art-style rules file for one set code.
def art_style_rules_path(set_code: str) -> Path:
    return ART_STYLES_DIR / f"{canonical_set_code_lower(set_code)}.json"
