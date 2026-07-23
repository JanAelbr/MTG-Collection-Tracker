"""Audit Cardmarket URLs against catalog finish flags and the local price guide."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server-backend" / "collection"))

from lib.config import DB_PATH  # noqa: E402
from lib.run_log import configure_logging, get_logger  # noqa: E402
from util.cardmarket_prices import load_price_guide_index  # noqa: E402
from util.cardmarket_urls import (  # noqa: E402
    AUDIT_ISSUE_CODES,
    audit_cardmarket_urls,
    repair_finish_flag_url_mismatches,
)

log = get_logger(__name__)


def _print_report(report: dict) -> None:
    counts = report.get("counts") or {}
    total = int(report.get("totalIssues") or 0)
    print(f"Total issues: {total}")
    for code in AUDIT_ISSUE_CODES:
        count = int(counts.get(code) or 0)
        print(f"  {code}: {count}")
        samples = (report.get("findings") or {}).get(code) or []
        for item in samples[:10]:
            detail = f" ({item['detail']})" if item.get("detail") else ""
            print(
                f"    - {item['setCode']}/{item['collectorNumber']} "
                f"{item.get('name') or ''}{detail}"
            )
            if item.get("cardmarketUrl"):
                print(f"      nonfoil: {item['cardmarketUrl']}")
            if item.get("cardmarketUrlFoil"):
                print(f"      foil:    {item['cardmarketUrlFoil']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Clear unambiguous finish/URL mismatches after reporting",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full audit payload as JSON",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=25,
        help="Max sample findings retained per issue class (default 25)",
    )
    args = parser.parse_args(argv)

    configure_logging(verbose=False)
    log.info("Auditing Cardmarket URLs in %s", DB_PATH)
    guide = load_price_guide_index()

    with sqlite3.connect(DB_PATH) as conn:
        report = audit_cardmarket_urls(conn, guide, sample_limit=max(1, args.sample_limit))
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            _print_report(report)

        if args.repair:
            repaired = repair_finish_flag_url_mismatches(conn, guide)
            conn.commit()
            log.info("Repaired %s Cardmarket URL row(s)", repaired)
            print(f"\nRepaired rows: {repaired}")
            after = audit_cardmarket_urls(conn, guide, sample_limit=max(1, args.sample_limit))
            print("\nAfter repair:")
            if args.json:
                print(json.dumps(after, indent=2))
            else:
                _print_report(after)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
