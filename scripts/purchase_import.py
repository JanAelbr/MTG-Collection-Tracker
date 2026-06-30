"""Import purchases from per-set CSV files into the database.

Deck lists are merged into data/{set_code}.csv first, then all purchase CSVs
are loaded into the purchases table.

Usage:

    python scripts/purchase_import.py

"""



import argparse



from lib.purchase_loader import import_purchases

from lib.run_log import configure_logging, get_logger



log = get_logger(__name__)





def main() -> None:

    parser = argparse.ArgumentParser(description="Import purchase and deck ownership CSVs.")

    parser.add_argument(

        "--verbose",

        "-v",

        action="store_true",

        help="Show detailed progress logging.",

    )

    args = parser.parse_args()

    configure_logging(verbose=args.verbose)

    log.info("Starting purchase import")

    import_purchases()

    log.info("Purchase import finished")





if __name__ == "__main__":

    main()

