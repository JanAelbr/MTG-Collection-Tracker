from pathlib import Path

from lib.config import TEMPLATE_DECKS_PATH
from report.deck_list_data import load_decks_client_payload
from report.report_assets import ASSET_DECKS_JS, asset_replacements, write_data_script
from report.report_nav import build_deck_browse_toolbar_html, build_decks_side_nav_html
from report.report_pages import ReportAssets, apply_template, last_updated_replacements


def load_decks_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_DECKS_PATH.read_text(encoding="utf-8"))


def build_decks_report_pages(
    output_file: Path | str,
    assets: ReportAssets,
) -> Path:
    output_path = Path(output_file)
    payload = load_decks_client_payload()
    data_js = write_data_script(output_path.stem, "DECKS_DATA", payload)
    replacements = {
        "{{DECK_TOOLBAR}}": build_deck_browse_toolbar_html(),
        "{{SIDE_NAV}}": build_decks_side_nav_html(),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_DECKS_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
