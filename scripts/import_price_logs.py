"""Import historic price snapshots from logs/*.csv into card_prices.



Usage:

    python scripts/import_price_logs.py

"""



import argparse

import sqlite3



from lib.config import DB_PATH

from lib.run_log import configure_logging, get_logger

from util.card_prices import ensure_card_prices_table

from util.price_log_import import import_price_logs



log = get_logger(__name__)





def main() -> None:

    parser = argparse.ArgumentParser(description="Import price log CSV files into card_prices.")

    parser.add_argument(

        "--verbose",

        "-v",

        action="store_true",

        help="Show detailed progress logging.",

    )

    args = parser.parse_args()

    configure_logging(verbose=args.verbose)



    log.info("Importing price logs from logs/")

    conn = sqlite3.connect(DB_PATH)

    ensure_card_prices_table(conn)

    before = conn.execute("SELECT COUNT(*) FROM card_prices").fetchone()[0]

    stats = import_price_logs(conn)

    conn.commit()

    after = conn.execute("SELECT COUNT(*) FROM card_prices").fetchone()[0]

    conn.close()



    log.info(
        "Imported %s Cardmarket snapshots from %s file(s)",
        stats["cardmarket_rows"],
        stats["cardmarket_files"],
    )

    log.info("Dates covered: %s", ", ".join(stats["dates"]))

    log.info("card_prices rows: %s -> %s", before, after)





if __name__ == "__main__":

    main()

