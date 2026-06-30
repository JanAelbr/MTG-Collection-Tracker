import json
import shutil
from pathlib import Path

from lib.config import (
    REPORTS_ASSETS_DIR,
    REPORTS_DATA_DIR,
    TEMPLATE_CARD_TOOLTIP_JS,
    TEMPLATE_COLLECTION_JS,
    TEMPLATE_CSS,
    TEMPLATE_FALLERS_JS,
    TEMPLATE_FORMAT_JS,
    TEMPLATE_MANAGER_JS,
    TEMPLATE_STORAGE_JS,
    TEMPLATE_RISERS_JS,
    TEMPLATE_STATS_JS,
    TEMPLATE_DECK_STATS_JS,
    TEMPLATE_DECKS_JS,
    TEMPLATE_CARD_JS,
    TEMPLATE_TOP_JS,
)
from lib.run_log import get_logger
from report.serialize_helpers import sanitize_json_payload

log = get_logger(__name__)
ASSET_CSS = "assets/report.css"
ASSET_TOOLTIP_JS = "assets/card_tooltip.js"
ASSET_FORMAT_JS = "assets/report_format.js"
ASSET_COLLECTION_JS = "assets/collection.js"
ASSET_TOP_JS = "assets/top.js"
ASSET_RISERS_JS = "assets/risers.js"
ASSET_FALLERS_JS = "assets/fallers.js"
ASSET_MANAGER_JS = "assets/manager.js"
ASSET_STORAGE_JS = "assets/storage.js"
ASSET_STATS_JS = "assets/stats.js"
ASSET_DECK_STATS_JS = "assets/deck_stats.js"
ASSET_DECKS_JS = "assets/decks.js"
ASSET_CARD_JS = "assets/card.js"


# Copy shared CSS and JS bundles into reports/assets once per run.
def write_shared_assets(
    page_scripts: set[str] | None = None,
    force: bool = False,
) -> int:
    REPORTS_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    copies = {
        TEMPLATE_CSS: REPORTS_ASSETS_DIR / "report.css",
        TEMPLATE_CARD_TOOLTIP_JS: REPORTS_ASSETS_DIR / "card_tooltip.js",
        TEMPLATE_FORMAT_JS: REPORTS_ASSETS_DIR / "report_format.js",
    }
    optional_copies = {
        TEMPLATE_COLLECTION_JS: REPORTS_ASSETS_DIR / "collection.js",
        TEMPLATE_TOP_JS: REPORTS_ASSETS_DIR / "top.js",
        TEMPLATE_RISERS_JS: REPORTS_ASSETS_DIR / "risers.js",
        TEMPLATE_FALLERS_JS: REPORTS_ASSETS_DIR / "fallers.js",
        TEMPLATE_MANAGER_JS: REPORTS_ASSETS_DIR / "manager.js",
        TEMPLATE_STORAGE_JS: REPORTS_ASSETS_DIR / "storage.js",
        TEMPLATE_STATS_JS: REPORTS_ASSETS_DIR / "stats.js",
        TEMPLATE_DECK_STATS_JS: REPORTS_ASSETS_DIR / "deck_stats.js",
        TEMPLATE_DECKS_JS: REPORTS_ASSETS_DIR / "decks.js",
        TEMPLATE_CARD_JS: REPORTS_ASSETS_DIR / "card.js",
    }

    script_to_template = {
        ASSET_TOP_JS: TEMPLATE_TOP_JS,
        ASSET_RISERS_JS: TEMPLATE_RISERS_JS,
        ASSET_FALLERS_JS: TEMPLATE_FALLERS_JS,
        ASSET_MANAGER_JS: TEMPLATE_MANAGER_JS,
        ASSET_STORAGE_JS: TEMPLATE_STORAGE_JS,
        ASSET_STATS_JS: TEMPLATE_STATS_JS,
        ASSET_DECK_STATS_JS: TEMPLATE_DECK_STATS_JS,
        ASSET_DECKS_JS: TEMPLATE_DECKS_JS,
        ASSET_CARD_JS: TEMPLATE_CARD_JS,
        ASSET_COLLECTION_JS: TEMPLATE_COLLECTION_JS,
    }

    if page_scripts is not None:
        for script_path in page_scripts:
            template_path = script_to_template.get(script_path)
            if template_path is not None:
                copies[template_path] = REPORTS_ASSETS_DIR / Path(script_path).name
    else:
        copies.update(optional_copies)

    copied = 0
    for source, target in copies.items():
        if force or not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
            shutil.copy2(source, target)
            copied += 1
            log.debug("Copied asset %s -> %s", source.name, target.name)
    if copied:
        log.info("Copied %s asset file(s) to reports/assets", copied)
    else:
        log.info("All requested assets already up to date")
    return copied


# Write one window.* assignment script for client-side report rendering.
def write_data_script(stem: str, var_name: str, payload: dict) -> str:
    filename = f"{stem}.js"
    path = REPORTS_DATA_DIR / filename
    safe_payload = sanitize_json_payload(payload)
    content = f"window.{var_name} = {json.dumps(safe_payload, ensure_ascii=False, separators=(',', ':'))};"
    path.write_text(content, encoding="utf-8")
    log.debug("Wrote data script %s (%s bytes)", path.name, len(content))
    return f"data/{filename}"


# Build standard asset placeholders for HTML templates.
def asset_replacements(page_js: str, data_js: str) -> dict[str, str]:
    return {
        "{{ASSET_CSS}}": ASSET_CSS,
        "{{ASSET_TOOLTIP_JS}}": ASSET_TOOLTIP_JS,
        "{{ASSET_FORMAT_JS}}": ASSET_FORMAT_JS,
        "{{PAGE_JS}}": page_js,
        "{{DATA_JS}}": data_js,
    }
