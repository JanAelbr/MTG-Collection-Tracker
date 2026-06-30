from pathlib import Path

from lib.config import TEMPLATE_STORAGE_PATH
from lib.run_log import get_logger
from report.report_assets import ASSET_STORAGE_JS, asset_replacements, write_data_script
from report.report_nav import build_storage_side_nav_html
from report.report_pages import ReportAssets, apply_template, last_updated_replacements
from report.storage_data import (
    load_storage_report_data,
    write_storage_location_scripts,
)

log = get_logger(__name__)


def load_storage_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_STORAGE_PATH.read_text(encoding="utf-8"))


def build_storage_report_pages(
    output_file: Path | str,
    assets: ReportAssets,
) -> Path:
    output_path = Path(output_file)
    client_payload, cards_by_location = load_storage_report_data()
    location_files = write_storage_location_scripts(cards_by_location)
    data_js = write_data_script(output_path.stem, "STORAGE_DATA", client_payload)
    log.info(
        "Storage report data: %s location(s), %s card row(s), %s file(s) written",
        len(client_payload.get("locations", [])),
        sum(len(cards) for cards in cards_by_location.values()),
        location_files,
    )
    replacements = {
        "{{SIDE_NAV}}": build_storage_side_nav_html(),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_STORAGE_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
