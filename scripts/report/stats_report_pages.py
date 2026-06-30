from pathlib import Path

from lib.config import TEMPLATE_STATS_PATH
from report.report_assets import ASSET_STATS_JS, asset_replacements, write_data_script
from report.report_data import get_all_set_codes, load_collection_data
from report.report_nav import build_side_nav_html, build_stats_toolbar_html
from report.report_pages import ReportAssets, apply_template, build_pages, last_updated_replacements, select_owned_cards
from report.report_stats import load_catalog_counts
from report.stats_data import load_stats_client_payload


# Read the HTML template used to build stats report pages.
def load_stats_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_STATS_PATH.read_text(encoding="utf-8"))


# Generate one stats report HTML page.
def build_stats_report_pages(
    output_file: Path | str,
    assets: ReportAssets,
) -> Path:
    output_path = Path(output_file)
    cards_df, _ = load_collection_data(owned_only=True)
    owned_df = select_owned_cards(cards_df, True)
    catalog_df = load_catalog_counts()
    pages = build_pages(get_all_set_codes())
    payload = load_stats_client_payload(owned_df, catalog_df, pages)
    data_js = write_data_script(output_path.stem, "STATS_DATA", payload)
    replacements = {
        "{{SET_SELECTOR}}": build_stats_toolbar_html(),
        "{{CURRENT_SET}}": "All",
        "{{SIDE_NAV}}": build_side_nav_html(),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_STATS_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
