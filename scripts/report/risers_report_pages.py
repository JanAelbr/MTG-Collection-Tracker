from pathlib import Path

from lib.config import TEMPLATE_RISERS_PATH
from report.report_assets import ASSET_RISERS_JS, asset_replacements, write_data_script
from report.report_data import get_all_set_codes
from report.report_nav import build_ranked_report_toolbar_html, build_risers_side_nav_html
from report.report_pages import ReportAssets, apply_template, build_pages, last_updated_replacements
from report.risers_data import load_risers_client_payload


# Read the HTML template used to build risers report pages.
def load_risers_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_RISERS_PATH.read_text(encoding="utf-8"))


# Generate one risers report HTML page.
def build_risers_report_pages(
    output_file: Path | str,
    assets: ReportAssets,
    ranked_payload: dict | None = None,
) -> Path:
    output_path = Path(output_file)
    pages = build_pages(get_all_set_codes())
    client_payload = ranked_payload or load_risers_client_payload()
    data_js = write_data_script(output_path.stem, "RISERS_DATA", client_payload)
    replacements = {
        "{{SET_SELECTOR}}": build_ranked_report_toolbar_html(),
        "{{CURRENT_SET}}": "All",
        "{{SIDE_NAV}}": build_risers_side_nav_html(),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_RISERS_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
