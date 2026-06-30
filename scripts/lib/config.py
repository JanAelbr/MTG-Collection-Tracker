"""Shared path configuration for the MTG collection tracker."""

import os
import shutil
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
BACKEND_DIR = REPO_ROOT / "server-backend"
FRONTEND_DIR = REPO_ROOT / "server-frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

APP_TITLE = "MTG - Collection tracker"
HTTP_USER_AGENT = "MtgCollectionTracker/1.0"
APP_DATA_DIR_NAME = "MtgCollectionTracker"

LEGACY_DB_PATH = REPO_ROOT / "collection.db"


def default_app_data_dir() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_DATA_DIR_NAME
    return Path.home() / APP_DATA_DIR_NAME


APP_DATA_DIR = default_app_data_dir()


def resolve_db_path(app_data_dir: Path | None = None) -> Path:
    target_dir = app_data_dir or APP_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    db_path = target_dir / "collection.db"
    _migrate_legacy_db(db_path)
    return db_path


def _migrate_legacy_db(db_path: Path) -> None:
    if db_path.exists() or not LEGACY_DB_PATH.exists():
        return

    shutil.move(str(LEGACY_DB_PATH), str(db_path))
    legacy_journal = LEGACY_DB_PATH.with_name(f"{LEGACY_DB_PATH.name}-journal")
    if legacy_journal.exists():
        shutil.move(str(legacy_journal), str(db_path.with_name(f"{db_path.name}-journal")))


DB_PATH = resolve_db_path()
DATA_DIR = REPO_ROOT / "data"
ART_STYLES_DIR = DATA_DIR / "art_styles"
DECKS_DIR = DATA_DIR / "decks"
DECKS_MANIFEST_NAME = "decks.csv"
TEMPLATES_DIR = REPO_ROOT / "templates"
REPORTS_DIR = REPO_ROOT / "reports"
REPORTS_ASSETS_DIR = REPORTS_DIR / "assets"
REPORTS_DATA_DIR = REPORTS_DIR / "data"
LOGS_DIR = REPO_ROOT / "logs"

CREATE_DB_SCRIPT = SCRIPTS_DIR / "db" / "create_db.py"
UPDATE_PRICES_SCRIPT = SCRIPTS_DIR / "update_prices.py"
SYNC_COLLECTION_SCRIPT = SCRIPTS_DIR / "sync_collection.py"
GENERATE_REPORT_SCRIPT = SCRIPTS_DIR / "generate_report.py"

OUTPUT_FILE_OWNED = REPORTS_DIR / "collection_owned.html"
OUTPUT_FILE_ALL = REPORTS_DIR / "collection_all.html"
OUTPUT_FILE_TOP = REPORTS_DIR / "collection_top.html"
OUTPUT_FILE_RISERS = REPORTS_DIR / "collection_risers.html"
OUTPUT_FILE_FALLERS = REPORTS_DIR / "collection_fallers.html"
OUTPUT_FILE_MANAGER = REPORTS_DIR / "collection_manager.html"
OUTPUT_FILE_STORAGE = REPORTS_DIR / "collection_storage.html"
OUTPUT_FILE_STATS = REPORTS_DIR / "collection_stats.html"
OUTPUT_FILE_DECK_STATS = REPORTS_DIR / "collection_deck_stats.html"
OUTPUT_FILE_DECKS = REPORTS_DIR / "collection_decks.html"
OUTPUT_FILE_CARD = REPORTS_DIR / "card.html"
OUTPUT_FILE_INDEX = REPORTS_DIR / "index.html"

TEMPLATE_PATH = TEMPLATES_DIR / "report.html"
TEMPLATE_TOP_PATH = TEMPLATES_DIR / "top_report.html"
TEMPLATE_RISERS_PATH = TEMPLATES_DIR / "risers_report.html"
TEMPLATE_FALLERS_PATH = TEMPLATES_DIR / "fallers_report.html"
TEMPLATE_MANAGER_PATH = TEMPLATES_DIR / "manager_report.html"
TEMPLATE_STORAGE_PATH = TEMPLATES_DIR / "storage_report.html"
TEMPLATE_STATS_PATH = TEMPLATES_DIR / "stats_report.html"
TEMPLATE_DECK_STATS_PATH = TEMPLATES_DIR / "deck_stats_report.html"
TEMPLATE_DECKS_PATH = TEMPLATES_DIR / "decks_report.html"
TEMPLATE_CARD_PATH = TEMPLATES_DIR / "card.html"
TEMPLATE_INDEX_PATH = TEMPLATES_DIR / "index.html"
TEMPLATE_CSS = TEMPLATES_DIR / "report.css"
TEMPLATE_FORMAT_JS = TEMPLATES_DIR / "report_format.js"
TEMPLATE_COLLECTION_JS = TEMPLATES_DIR / "collection.js"
TEMPLATE_JS = TEMPLATES_DIR / "report.js"
TEMPLATE_TOP_JS = TEMPLATES_DIR / "top_report.js"
TEMPLATE_RISERS_JS = TEMPLATES_DIR / "risers_report.js"
TEMPLATE_FALLERS_JS = TEMPLATES_DIR / "fallers_report.js"
TEMPLATE_MANAGER_JS = TEMPLATES_DIR / "manager_report.js"
TEMPLATE_STORAGE_JS = TEMPLATES_DIR / "storage_report.js"
TEMPLATE_STATS_JS = TEMPLATES_DIR / "stats_report.js"
TEMPLATE_DECK_STATS_JS = TEMPLATES_DIR / "deck_stats_report.js"
TEMPLATE_DECKS_JS = TEMPLATES_DIR / "decks_report.js"
TEMPLATE_CARD_JS = TEMPLATES_DIR / "card.js"
TEMPLATE_CARD_TOOLTIP_JS = TEMPLATES_DIR / "card_tooltip.js"


# Read shared report JavaScript, with optional page-specific script appended.
def load_report_javascript(page_script: Path) -> str:
    tooltip_js = TEMPLATE_CARD_TOOLTIP_JS.read_text(encoding="utf-8")
    page_js = page_script.read_text(encoding="utf-8")
    return f"{tooltip_js}\n{page_js}"


EXCLUDED_PURCHASE_CSV_NAMES = frozenset({"purchases.csv", "example.csv"})
EXCLUDED_SET_CODES = frozenset({"EXAMPLE"})


# Return the art-style rules file for one set code.
def art_style_rules_path(set_code: str) -> Path:
    return ART_STYLES_DIR / f"{set_code.lower()}.json"


# Return the purchase CSV path for one set code.
def purchase_csv_path(set_code: str) -> Path:
    return DATA_DIR / f"{set_code.lower()}.csv"


# Return per-set purchase CSV files from data/.
def list_set_csv_files() -> list[Path]:
    return sorted(
        p for p in DATA_DIR.glob("*.csv")
        if p.is_file() and p.name.lower() not in EXCLUDED_PURCHASE_CSV_NAMES
    )


# Return deck list CSV files registered in data/decks/decks.csv.
def list_deck_csv_files() -> list[Path]:
    from lib.deck_csv import load_deck_entries

    if not DECKS_DIR.is_dir():
        return []
    return [entry.path for entry in load_deck_entries()]
