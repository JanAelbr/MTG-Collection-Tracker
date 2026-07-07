"""Shared path configuration for the MTG collection tracker."""

import os
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
BACKEND_DIR = REPO_ROOT / "server-backend"
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
DECKS_DIR = DATA_DIR / "decks"
DECKS_MANIFEST_NAME = "decks.csv"
LOGS_DIR = REPO_ROOT / "logs"

CREATE_DB_SCRIPT = SCRIPTS_DIR / "db" / "create_db.py"
UPDATE_PRICES_SCRIPT = SCRIPTS_DIR / "update_prices.py"
SYNC_COLLECTION_SCRIPT = SCRIPTS_DIR / "sync_collection.py"

EXCLUDED_PURCHASE_CSV_NAMES = frozenset({"purchases.csv", "example.csv"})
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


# Return the purchase CSV path for one set code.
def purchase_csv_path(set_code: str) -> Path:
    return DATA_DIR / f"{canonical_set_code_lower(set_code)}.csv"


# Return per-set purchase CSV files from data/.
def list_set_csv_files() -> list[Path]:
    paths = sorted(
        p for p in DATA_DIR.glob("*.csv")
        if p.is_file() and p.name.lower() not in EXCLUDED_PURCHASE_CSV_NAMES
    )
    seen_canonical: set[str] = set()
    unique_paths: list[Path] = []
    for path in paths:
        canonical = normalize_set_code(path.stem)
        if canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)
        unique_paths.append(path)
    return unique_paths


# Return deck list CSV files registered in data/decks/decks.csv.
def list_deck_csv_files() -> list[Path]:
    from lib.deck_csv import load_deck_entries

    if not DECKS_DIR.is_dir():
        return []
    return [entry.path for entry in load_deck_entries()]
