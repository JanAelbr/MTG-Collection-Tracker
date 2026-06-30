from pathlib import Path

from lib.config import TEMPLATE_DECK_STATS_PATH
from report.deck_stats_data import load_deck_stats_client_payload
from report.report_assets import ASSET_DECK_STATS_JS, asset_replacements, write_data_script
from report.report_nav import build_deck_stats_side_nav_html, build_deck_toolbar_html
from report.report_pages import ReportAssets, apply_template, last_updated_replacements


def load_deck_stats_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_DECK_STATS_PATH.read_text(encoding="utf-8"))


def build_deck_stats_report_pages(
    output_file: Path | str,
    assets: ReportAssets,
) -> Path:
    output_path = Path(output_file)
    payload = load_deck_stats_client_payload()
    data_js = write_data_script(output_path.stem, "DECK_STATS_DATA", payload)
    replacements = {
        "{{DECK_SELECTOR}}": build_deck_toolbar_html(
            payload.get("decks", []),
            cross_link="browse",
        ),
        "{{SIDE_NAV}}": build_deck_stats_side_nav_html(),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_DECK_STATS_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
