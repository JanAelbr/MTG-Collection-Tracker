from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from lib.config import APP_TITLE, TEMPLATE_PATH
from report.collection_data import load_collection_client_payload
from report.report_assets import ASSET_COLLECTION_JS, asset_replacements, write_data_script
from report.report_data import get_all_set_codes
from report.report_nav import build_collection_side_nav_html, build_set_selector_html
from util.price_history import load_last_updated_display


@dataclass
class ReportAssets:
    template: str


# Read the HTML template used to build collection report pages.
def load_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_PATH.read_text(encoding="utf-8"))


# Return owned cards only, or filter to purchased rows in all-cards mode.
def select_owned_cards(cards_df: pd.DataFrame, owned_only: bool) -> pd.DataFrame:
    if owned_only:
        return cards_df.copy()
    return cards_df[cards_df["purchase_value"].notna()]


# Build the ordered list of set filters, starting with All.
def build_pages(set_codes: list[str]) -> list[str]:
    return ["All", *set_codes]


# Replace template placeholders in the base HTML template.
def apply_template(template: str, replacements: dict[str, str]) -> str:
    html = template
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


# Build footer and last-updated placeholders for HTML templates.
def last_updated_replacements() -> dict[str, str]:
    updated = load_last_updated_display()
    return {
        "{{LAST_UPDATED}}": updated,
        "{{REPORT_FOOTER}}": (
            f'<footer class="report-footer">'
            f'<span class="report-footer-updated">Last price update: {updated}</span>'
            f'<span class="report-footer-separator"> · </span>'
            f'<span class="report-footer-credit">{APP_TITLE}</span>'
            f"</footer>"
        ),
    }


# Generate one collection report HTML page.
def build_report_pages(
    output_file: Path | str,
    owned_only: bool,
    cards_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    assets: ReportAssets,
) -> Path:
    output_path = Path(output_file)
    pages = build_pages(get_all_set_codes())
    payload = load_collection_client_payload(cards_df, summary_df, owned_only)
    data_js = write_data_script(output_path.stem, "COLLECTION_DATA", payload)
    active = "owned" if owned_only else "all"
    replacements = {
        "{{SET_SELECTOR}}": build_set_selector_html(),
        "{{CURRENT_SET}}": "All",
        "{{SIDE_NAV}}": build_collection_side_nav_html(
            active,
            payload.get("compareDates", []),
            payload.get("defaultCompareDate"),
        ),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_COLLECTION_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
