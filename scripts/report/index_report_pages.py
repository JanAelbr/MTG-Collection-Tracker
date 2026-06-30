from pathlib import Path

from lib.config import OUTPUT_FILE_INDEX, TEMPLATE_INDEX_PATH
from report.report_nav import REPORT_TYPES
from report.report_pages import last_updated_replacements


def build_index_page(output_file: Path | str | None = None) -> Path:
    output_path = Path(output_file or OUTPUT_FILE_INDEX)

    report_links = "\n".join(
        f'<a href="{filename}" class="index-report-link">{label}</a>'
        for _, label, filename in REPORT_TYPES
    )

    html = TEMPLATE_INDEX_PATH.read_text(encoding="utf-8")
    for key, value in {
        **last_updated_replacements(),
        "{{REPORT_LINKS}}": report_links,
    }.items():
        html = html.replace(key, value)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
