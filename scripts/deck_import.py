"""Import deck lists from CSV files in data/decks/ into the database.



Usage:

    python scripts/deck_import.py

"""



import argparse



from lib.deck_loader import import_decks

from lib.run_log import configure_logging, get_logger



log = get_logger(__name__)





def main() -> None:

    parser = argparse.ArgumentParser(description="Import deck lists into the database.")

    parser.add_argument(

        "--verbose",

        "-v",

        action="store_true",

        help="Show detailed progress logging.",

    )

    args = parser.parse_args()

    configure_logging(verbose=args.verbose)

    log.info("Starting deck import")

    import_decks()

    log.info("Deck import finished")





if __name__ == "__main__":

    main()

