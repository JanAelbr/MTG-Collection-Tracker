from pathlib import Path

from lib.config import TEMPLATE_MANAGER_PATH
from report.manager_data import load_manager_client_payload
from report.report_assets import ASSET_MANAGER_JS, asset_replacements, write_data_script
from report.report_nav import build_foil_filter_html, build_manager_side_nav_html, build_set_selector_html
from report.report_pages import ReportAssets, apply_template, last_updated_replacements


def load_manager_report_assets() -> ReportAssets:
    return ReportAssets(template=TEMPLATE_MANAGER_PATH.read_text(encoding="utf-8"))


def build_manager_report_pages(
    output_file: Path | str,
    assets: ReportAssets,
) -> Path:
    output_path = Path(output_file)
    client_payload = load_manager_client_payload()
    data_js = write_data_script(output_path.stem, "MANAGER_DATA", client_payload)
    replacements = {
        "{{SET_SELECTOR}}": (
            f'{build_set_selector_html(include_all=False)}{build_foil_filter_html()}'
        ),
        "{{SIDE_NAV}}": build_manager_side_nav_html(),
    }
    replacements.update(last_updated_replacements())
    replacements.update(asset_replacements(ASSET_MANAGER_JS, data_js))
    html = apply_template(assets.template, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
