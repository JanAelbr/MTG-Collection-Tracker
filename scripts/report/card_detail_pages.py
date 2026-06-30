import json
from pathlib import Path

from lib.config import OUTPUT_FILE_INDEX, TEMPLATE_CARD_PATH
from lib.run_log import get_logger
from report.card_detail_data import (
    load_card_detail_assets as build_card_detail_payloads,
    write_card_history_scripts,
)
from report.report_assets import ASSET_CARD_JS, ASSET_FORMAT_JS, asset_replacements, write_data_script
from report.report_pages import ReportAssets, apply_template, last_updated_replacements

log = get_logger(__name__)

# Read the HTML template used to build the card detail page.
def load_card_detail_page_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_CARD_PATH.read_text(encoding="utf-8"))


# Backwards-compatible alias.
def load_card_detail_assets() -> ReportAssets:
    return load_card_detail_page_assets()


# Generate the card detail HTML shell and data script.
def build_card_detail_page(output_file: Path | str, assets: ReportAssets) -> Path:
    output_path = Path(output_file)
    payload, history_payloads = build_card_detail_payloads()
    data_js = write_data_script("cards", "CARDS_DATA", payload)
    history_files = write_card_history_scripts(history_payloads)
    log.info(
        "Card detail data: index %s bytes, %s set history file(s)",
        len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
        history_files,
    )
    replacements = {        "{{BACK_LINK}}": OUTPUT_FILE_INDEX.name,
        "{{SIDE_NAV}}": "",
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_CARD_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
