import argparse
import webbrowser
from pathlib import Path

from lib.config import (
    OUTPUT_FILE_ALL,
    OUTPUT_FILE_CARD,
    OUTPUT_FILE_DECK_STATS,
    OUTPUT_FILE_DECKS,
    OUTPUT_FILE_FALLERS,
    OUTPUT_FILE_INDEX,
    OUTPUT_FILE_MANAGER,
    OUTPUT_FILE_OWNED,
    OUTPUT_FILE_RISERS,
    OUTPUT_FILE_STATS,
    OUTPUT_FILE_STORAGE,
    OUTPUT_FILE_TOP,
    REPORTS_DATA_DIR,
)
from lib.run_log import BuildTimer, configure_logging, get_logger
from report.card_detail_pages import build_card_detail_page, load_card_detail_assets
from report.deck_stats_report_pages import build_deck_stats_report_pages, load_deck_stats_report_assets
from report.decks_report_pages import build_decks_report_pages, load_decks_report_assets
from report.fallers_report_pages import build_fallers_report_pages, load_fallers_report_assets
from report.index_report_pages import build_index_page
from report.manager_report_pages import build_manager_report_pages, load_manager_report_assets
from report.ranked_cards_data import load_ranked_client_payload
from report.report_assets import (
    ASSET_CARD_JS,
    ASSET_DECK_STATS_JS,
    ASSET_DECKS_JS,
    ASSET_FALLERS_JS,
    ASSET_MANAGER_JS,
    ASSET_RISERS_JS,
    ASSET_STATS_JS,
    ASSET_STORAGE_JS,
    ASSET_TOP_JS,
    write_shared_assets,
)
from report.report_data import load_top_cards_data
from report.risers_report_pages import build_risers_report_pages, load_risers_report_assets
from report.stats_report_pages import build_stats_report_pages, load_stats_report_assets
from report.storage_report_pages import build_storage_report_pages, load_storage_report_assets
from report.top_report_pages import build_top_report_pages, load_top_report_assets

ALL_REPORT_IDS = (
    "index",
)

# Reports migrated to the Vue app; kept for reference when building selective legacy output.
DEPRECATED_REPORT_IDS = (
    "top",
    "risers",
    "fallers",
    "manager",
    "storage",
    "decks",
    "stats",
    "deck_stats",
    "card",
)

REPORT_PAGE_SCRIPTS = {
    "top": ASSET_TOP_JS,
    "risers": ASSET_RISERS_JS,
    "fallers": ASSET_FALLERS_JS,
    "manager": ASSET_MANAGER_JS,
    "storage": ASSET_STORAGE_JS,
    "decks": ASSET_DECKS_JS,
    "stats": ASSET_STATS_JS,
    "deck_stats": ASSET_DECK_STATS_JS,
    "card": ASSET_CARD_JS,
}


# Open a generated HTML report in the default browser.
def open_report_in_browser(path: Path) -> None:
    webbrowser.open(path.resolve().as_uri())


# Parse CLI arguments for selective report generation.
def parse_generate_report_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate HTML collection reports.",
    )
    parser.add_argument(
        "--reports",
        "-r",
        default="all",
        help=(
            "Comma-separated report ids to build "
            f"({', '.join(ALL_REPORT_IDS)}) or 'all'"
        ),
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the home page in a browser after building.",
    )
    parser.add_argument(
        "--force-assets",
        action="store_true",
        help="Recopy shared JS/CSS assets even when templates have not changed.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress logging.",
    )
    return parser.parse_args(argv)


# Resolve report ids from CLI input.
def resolve_report_ids(raw_value: str) -> list[str]:
    if raw_value.strip().lower() == "all":
        return list(ALL_REPORT_IDS)

    selected: list[str] = []
    for item in raw_value.split(","):
        report_id = item.strip().lower()
        if not report_id:
            continue
        if report_id not in ALL_REPORT_IDS:
            valid = ", ".join(ALL_REPORT_IDS)
            raise ValueError(f"Unknown report id '{report_id}'. Valid ids: {valid}")
        if report_id not in selected:
            selected.append(report_id)
    if not selected:
        raise ValueError("No report ids were provided.")
    return selected


# Remove legacy report files that are no longer generated.
def remove_obsolete_reports() -> None:
    for stale in (
        OUTPUT_FILE_OWNED,
        OUTPUT_FILE_ALL,
        REPORTS_DATA_DIR / "collection_owned.js",
        REPORTS_DATA_DIR / "collection_all.js",
    ):
        if stale.exists():
            stale.unlink()
            get_logger(__name__).info("Removed obsolete report: %s", stale)


# Generate selected report HTML pages and optionally open the default page.
def generate_report(
    report_ids: list[str] | None = None,
    *,
    open_in_browser: bool = True,
    force_assets: bool = False,
) -> list[Path]:
    log = get_logger(__name__)
    targets = report_ids or list(ALL_REPORT_IDS)
    timer = BuildTimer(log)
    log.warning(
        "Legacy static HTML report generation is deprecated; prefer the interactive app "
        "(scripts/run_app.ps1). Use update_prices_report.py --static-reports only when needed."
    )
    log.info("Generating report(s): %s", ", ".join(targets))

    page_scripts = {
        REPORT_PAGE_SCRIPTS[report_id]
        for report_id in targets
        if report_id in REPORT_PAGE_SCRIPTS
    }
    with timer.step("Shared assets"):
        copied_assets = write_shared_assets(
            page_scripts=page_scripts,
            force=force_assets,
        )
        if force_assets and not copied_assets:
            log.info("Forced asset refresh: all files already up to date")

    ranked_payload = None
    if {"top", "risers", "fallers"}.intersection(targets):
        with timer.step("Ranked card payload"):
            ranked_payload = load_ranked_client_payload(load_top_cards_data())

    top_assets = load_top_report_assets() if "top" in targets else None
    risers_assets = load_risers_report_assets() if "risers" in targets else None
    fallers_assets = load_fallers_report_assets() if "fallers" in targets else None
    manager_assets = load_manager_report_assets() if "manager" in targets else None
    storage_assets = load_storage_report_assets() if "storage" in targets else None
    stats_assets = load_stats_report_assets() if "stats" in targets else None
    deck_stats_assets = load_deck_stats_report_assets() if "deck_stats" in targets else None
    decks_assets = load_decks_report_assets() if "decks" in targets else None
    card_assets = load_card_detail_assets() if "card" in targets else None

    builders: list[tuple[str, Path]] = []
    if "index" in targets:
        with timer.step("Report: index"):
            builders.append(("Home page", build_index_page(OUTPUT_FILE_INDEX)))
    if "top" in targets:
        with timer.step("Report: top"):
            builders.append((
                "Top cards",
                build_top_report_pages(
                    OUTPUT_FILE_TOP,
                    top_assets,
                    ranked_payload=ranked_payload,
                ),
            ))
    if "risers" in targets:
        with timer.step("Report: risers"):
            builders.append((
                "Top risers",
                build_risers_report_pages(
                    OUTPUT_FILE_RISERS,
                    risers_assets,
                    ranked_payload=ranked_payload,
                ),
            ))
    if "fallers" in targets:
        with timer.step("Report: fallers"):
            builders.append((
                "Top fallers",
                build_fallers_report_pages(
                    OUTPUT_FILE_FALLERS,
                    fallers_assets,
                    ranked_payload=ranked_payload,
                ),
            ))
    if "manager" in targets:
        with timer.step("Report: manager"):
            builders.append((
                "Set Manager",
                build_manager_report_pages(OUTPUT_FILE_MANAGER, manager_assets),
            ))
    if "storage" in targets:
        with timer.step("Report: storage"):
            builders.append((
                "Storage",
                build_storage_report_pages(OUTPUT_FILE_STORAGE, storage_assets),
            ))
    if "decks" in targets:
        with timer.step("Report: decks"):
            builders.append((
                "Decks",
                build_decks_report_pages(OUTPUT_FILE_DECKS, decks_assets),
            ))
    if "stats" in targets:
        with timer.step("Report: stats"):
            builders.append((
                "Statistics",
                build_stats_report_pages(OUTPUT_FILE_STATS, stats_assets),
            ))
    if "deck_stats" in targets:
        with timer.step("Report: deck_stats"):
            builders.append((
                "Deck statistics",
                build_deck_stats_report_pages(OUTPUT_FILE_DECK_STATS, deck_stats_assets),
            ))
    if "card" in targets:
        with timer.step("Report: card detail"):
            builders.append((
                "Card detail",
                build_card_detail_page(OUTPUT_FILE_CARD, card_assets),
            ))

    for label, path in builders:
        log.info("Report created (%s): %s", label, path)

    if "index" in targets or len(targets) == len(ALL_REPORT_IDS):
        remove_obsolete_reports()

    log.info("Built %s report(s)", len(builders))
    if open_in_browser and "index" in targets:
        log.info("Opening home page in browser: %s", OUTPUT_FILE_INDEX)
        open_report_in_browser(OUTPUT_FILE_INDEX)

    timer.log_summary("Report generation timing")
    return [path for _, path in builders]


def main(argv: list[str] | None = None) -> None:
    args = parse_generate_report_args(argv)
    configure_logging(verbose=args.verbose)
    report_ids = resolve_report_ids(args.reports)
    generate_report(
        report_ids,
        open_in_browser=not args.no_browser,
        force_assets=args.force_assets,
    )


if __name__ == "__main__":
    main()
