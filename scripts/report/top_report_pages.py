from pathlib import Path

from lib.config import TEMPLATE_TOP_PATH
from report.report_assets import ASSET_TOP_JS, asset_replacements, write_data_script
from report.report_data import get_all_set_codes, load_top_cards_data
from report.report_nav import build_ranked_report_toolbar_html, build_top_side_nav_html
from report.report_pages import ReportAssets, apply_template, build_pages, last_updated_replacements
from report.top_data import load_top_client_payload


# Read the HTML template used to build top report pages.
def load_top_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_TOP_PATH.read_text(encoding="utf-8"))


# Generate one top report HTML page.
def build_top_report_pages(
    output_file: Path | str,
    assets: ReportAssets,
    ranked_payload: dict | None = None,
) -> Path:
    output_path = Path(output_file)
    pages = build_pages(get_all_set_codes())
    payload = ranked_payload or load_top_client_payload(load_top_cards_data())
    data_js = write_data_script(output_path.stem, "TOP_DATA", payload)
    replacements = {
        "{{SET_SELECTOR}}": build_ranked_report_toolbar_html(),
        "{{CURRENT_SET}}": "All",
        "{{SIDE_NAV}}": build_top_side_nav_html(),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_TOP_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
