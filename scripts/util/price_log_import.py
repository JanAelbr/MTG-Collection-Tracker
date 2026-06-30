import csv
import re
import sqlite3
from pathlib import Path

from lib.config import DB_PATH, LOGS_DIR
from util.card_prices import ensure_card_prices_table, prune_owned_price_history, record_card_price

CARDMARKET_LOG_PATTERN = re.compile(r"^cardmarket_prices_(?P<date>\d{4}-\d{2}-\d{2})\.csv$")


# Parse a numeric price from CSV text.
def parse_log_price(raw_value) -> float | None:
    if raw_value in (None, ""):
        return None
    try:
        return float(str(raw_value).replace(",", "."))
    except ValueError:
        return None


# Import one Cardmarket backfill log CSV into card_prices.
def import_cardmarket_log(conn: sqlite3.Connection, log_file: Path) -> int:
    match = CARDMARKET_LOG_PATTERN.match(log_file.name)
    if not match:
        return 0

    price_date = match.group("date")
    imported = 0

    with log_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("status") != "updated":
                continue
            price = parse_log_price(row.get("price"))
            if price is None:
                continue
            raw_finish = str(row.get("finish") or "").strip().lower()
            finish = {"0": 0, "1": 1, "2": 2, "nonfoil": 0, "foil": 1, "etched": 2}.get(raw_finish, 0)
            record_card_price(
                conn,
                row["set_code"],
                row["collector_number"],
                finish,
                price,
                "cardmarket",
                price_date,
            )
            imported += 1

    return imported


# Import Cardmarket price logs from logs/ into card_prices.
def import_price_logs(conn: sqlite3.Connection | None = None) -> dict:
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)
        ensure_card_prices_table(conn)

    stats = {
        "cardmarket_files": 0,
        "cardmarket_rows": 0,
        "dates": set(),
    }

    for log_file in sorted(LOGS_DIR.glob("*.csv")):
        cardmarket_match = CARDMARKET_LOG_PATTERN.match(log_file.name)
        if cardmarket_match:
            rows = import_cardmarket_log(conn, log_file)
            stats["cardmarket_files"] += 1
            stats["cardmarket_rows"] += rows
            stats["dates"].add(cardmarket_match.group("date"))
            print(
                f"Imported Cardmarket log {log_file.name}: "
                f"{rows} price snapshots for {cardmarket_match.group('date')}"
            )

    if own_conn:
        prune_owned_price_history(conn)
        conn.commit()
        conn.close()

    stats["dates"] = sorted(stats["dates"])
    return stats
