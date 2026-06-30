# Refresh prices and optionally regenerate legacy static HTML reports.

import argparse

from generate_report import generate_report
from lib.run_log import configure_logging, get_logger
from update_prices import update_prices

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update prices and optionally regenerate legacy static HTML reports.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress logging.",
    )
    parser.add_argument(
        "--static-reports",
        action="store_true",
        help="Also regenerate legacy HTML reports in reports/ (deprecated; use the web app).",
    )
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)

    log.info("Updating prices (Cardmarket guide + Scryfall catalog when needed)")
    update_prices()
    if args.static_reports:
        log.info("Generating legacy HTML index from database")
        generate_report(["index"], open_in_browser=False)
    else:
        log.info(
            "Skipped legacy HTML report generation. "
            "Run with --static-reports to rebuild reports/, or use the web app "
            "(scripts/run_app.ps1)."
        )
    log.info("Price update complete")


if __name__ == "__main__":
    main()
