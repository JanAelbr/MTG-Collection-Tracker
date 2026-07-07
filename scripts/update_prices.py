import csv
import json
import sqlite3
import time
from datetime import date

from lib.config import (
    DB_PATH,
    HTTP_USER_AGENT,
    LOGS_DIR,
    canonical_set_code_lower,
    list_set_csv_files,
    normalize_set_code,
)
from lib.art_styles import ensure_art_style_rules_file, get_art_style
from lib.deck_csv import list_deck_sync_set_codes
from lib.run_log import BuildTimer, configure_logging, get_logger
from util.cardmarket_prices import sync_prices_from_guide
from util.card_prices import (
    load_existing_card_prices,
    restore_market_values_from_history,
)
from util.cardmarket_urls import load_existing_cardmarket_urls, merge_cardmarket_urls
from util.card_finishes import card_finish_flags
from util.db_migrate import ensure_card_columns, ensure_card_prices_table
from util.set_catalog import (
    ensure_sets_table,
    load_catalog_set_codes,
    prune_unowned_sets,
    sync_owned_set_metadata,
    upsert_set_from_card,
)
from util.scryfall_client import scryfall_get
from util.scryfall_card import (
    card_colors_json,
    card_image_uri,
    card_primary_type,
    card_type_line,
)

HEADERS = {"User-Agent": HTTP_USER_AGENT}
INSERT_CARD_SQL = """
INSERT OR REPLACE INTO cards (
    id, set_code, collector_number, name, art_style,
    market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched,
    image_uri, cardmarket_url, cardmarket_url_foil, colors, type_line, card_type
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
LOG_HEADERS = [
    "card_id", "collector_number", "name", "art_style",
    "image_uri", "cardmarket_url", "colors", "type_line", "card_type",
]

log = get_logger(__name__)


# Recompute art_style for every card already stored in the database.
def refresh_art_styles() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    set_codes = {
        str(row[0]).lower()
        for row in cursor.execute("SELECT DISTINCT set_code FROM cards").fetchall()
        if row[0]
    }
    for set_code in sorted(set_codes):
        ensure_art_style_rules_file(set_code)
    rows = cursor.execute(
        "SELECT id, set_code, collector_number FROM cards"
    ).fetchall()
    updated = 0
    for card_id, set_code, collector_number in rows:
        art_style = get_art_style(set_code.lower(), collector_number)
        cursor.execute(
            "UPDATE cards SET art_style = ? WHERE id = ?",
            (art_style, card_id),
        )
        updated += 1
    conn.commit()
    conn.close()
    log.info("Refreshed art styles for %s cards", updated)


# Return lowercase set codes for purchase CSVs and deck-required prints.
def get_set_codes() -> list[str]:
    purchase_sets = {
        canonical_set_code_lower(path.stem)
        for path in list_set_csv_files()
    }
    deck_sets = {canonical_set_code_lower(code) for code in list_deck_sync_set_codes()}
    return sorted(code for code in (purchase_sets | deck_sets) if code)


# Build the initial Scryfall search URL for one set.
def scryfall_search_url(set_code: str) -> str:
    return (
        f"https://api.scryfall.com/cards/search"
        f"?q=set:{set_code}&unique=prints&order=set"
    )


# Fetch one page of Scryfall search results.
def fetch_scryfall_page(url: str, *, force: bool = False) -> dict | None:
    response = scryfall_get(
        url,
        headers=HEADERS,
        timeout=30,
        logger=log,
        label="Scryfall catalog page",
        force=force,
    )
    if response.status_code != 200:
        log.error("Scryfall request failed: HTTP %s", response.status_code)
        log.error("%s", response.text)
        return None
    return response.json()


# Build one CSV log row for a fetched card.
def card_log_row(
    set_code: str,
    collector_number: str,
    name: str,
    art_style: str,
    image_uri: str | None,
    cardmarket_link: str | None,
    colors: str,
    type_line: str,
    card_type: str,
) -> tuple[str, str, str, str, str, str, str, str, str]:
    card_id = f"{set_code.upper()}-{collector_number}"
    return (
        card_id,
        collector_number,
        name,
        art_style,
        image_uri or "",
        cardmarket_link or "",
        colors,
        type_line,
        card_type,
    )


# Insert or update one card in the database and return its log row.
def upsert_card(
    cursor,
    set_code: str,
    card: dict,
    price_date: str,
    owned_set_codes: set[str] | None = None,
) -> tuple[str, str, str, str, str, str]:
    collector_number = str(card.get("collector_number", ""))
    market_value, market_value_foil, market_value_etched = load_existing_card_prices(
        cursor, set_code, collector_number,
    )
    existing_nonfoil_url, existing_foil_url = load_existing_cardmarket_urls(
        cursor, set_code, collector_number,
    )
    has_nonfoil, has_foil, has_etched = card_finish_flags(card)
    art_style = get_art_style(set_code, collector_number)
    name = card.get("name", "")
    image_uri = card_image_uri(card)
    nonfoil_url, foil_url = merge_cardmarket_urls(
        existing_nonfoil_url,
        existing_foil_url,
        card,
    )
    colors = card_colors_json(card)
    type_line = card_type_line(card)
    card_type = card_primary_type(card)
    cursor.execute(
        INSERT_CARD_SQL,
        (
            f"{set_code.upper()}-{collector_number}",
            set_code.upper(),
            collector_number,
            name,
            art_style,
            market_value,
            market_value_foil,
            market_value_etched,
            has_nonfoil,
            has_foil,
            has_etched,
            image_uri,
            nonfoil_url,
            foil_url,
            colors,
            type_line,
            card_type,
        ),
    )
    if owned_set_codes is None or set_code.upper() in owned_set_codes:
        upsert_set_from_card(cursor, card, price_date)
    cardmarket_link = nonfoil_url or foil_url
    return card_log_row(
        set_code,
        collector_number,
        name,
        art_style,
        image_uri,
        cardmarket_link,
        colors,
        type_line,
        card_type,
    )


# Print a progress line for one fetched Scryfall page.
def log_page_fetch(set_code: str, page_cards: list[dict]) -> None:
    if not page_cards:
        return
    start = page_cards[0].get("collector_number", "")
    end = page_cards[-1].get("collector_number", "")
    log.debug(
        "Fetched %s cards for set %s from %s to %s",
        len(page_cards),
        set_code,
        start,
        end,
    )


# Upsert one Scryfall page of cards and append rows to the price log.
def write_price_page(
    cursor,
    writer,
    set_code: str,
    page_cards: list[dict],
    price_date: str,
    owned_set_codes: set[str] | None = None,
) -> int:
    count = 0
    for card in page_cards:
        writer.writerow(
            upsert_card(
                cursor,
                set_code,
                card,
                price_date,
                owned_set_codes,
            )
        )
        count += 1
    log_page_fetch(set_code, page_cards)
    return count


# Fetch all Scryfall pages for one set and write a daily catalog log CSV.
def sync_set_catalog(
    cursor,
    set_code: str,
    today: str,
    owned_set_codes: set[str] | None = None,
    *,
    force_scryfall: bool = False,
) -> int:
    url = scryfall_search_url(set_code)
    log.info("Fetching Scryfall catalog for set %s", set_code.upper())
    log.debug("Scryfall URL: %s", url)
    count = 0
    log_file = LOGS_DIR / f"prices_{set_code}_{today}.csv"

    with log_file.open("w", newline="", encoding="utf-8") as log_handle:
        writer = csv.writer(log_handle)
        writer.writerow(LOG_HEADERS)
        while url:
            data = fetch_scryfall_page(url, force=force_scryfall)
            if data is None:
                break
            count += write_price_page(
                cursor,
                writer,
                set_code,
                data.get("data", []),
                today,
                owned_set_codes,
            )
            url = data.get("next_page")
            time.sleep(0.1)

    log.info("Set %s: retrieved %s cards from Scryfall", set_code.upper(), count)
    return count


# Return set codes that have no cards stored yet.
def sets_missing_catalog(cursor, set_codes: list[str]) -> list[str]:
    missing: list[str] = []
    for set_code in set_codes:
        row = cursor.execute(
            "SELECT COUNT(*) FROM cards WHERE set_code = ?",
            (set_code.upper(),),
        ).fetchone()
        if not row or row[0] == 0:
            missing.append(set_code)
    return missing


# Return set codes with cards missing color or type metadata.
def sets_missing_metadata(cursor, set_codes: list[str]) -> list[str]:
    missing: list[str] = []
    for set_code in set_codes:
        row = cursor.execute(
            """
            SELECT COUNT(*) FROM cards
            WHERE set_code = ?
              AND (
                colors IS NULL
                OR type_line IS NULL
                OR TRIM(type_line) = ''
                OR card_type IS NULL
                OR TRIM(card_type) = ''
              )
            """,
            (set_code.upper(),),
        ).fetchone()
        if row and row[0] > 0:
            missing.append(set_code)
    return missing


# Fetch current prices for every configured set.
def update_prices(
    *,
    skip_scryfall: bool = False,
    force_cardmarket: bool = False,
    force_scryfall: bool = False,
    refresh_metadata: bool = False,
) -> None:
    set_codes = get_set_codes()
    if not set_codes:
        log.warning("No set codes found from purchase/deck files; nothing to fetch")
        return

    for set_code in set_codes:
        ensure_art_style_rules_file(set_code)

    log.info("Updating prices for set(s): %s", ", ".join(code.upper() for code in set_codes))
    if skip_scryfall:
        log.info("Skipping Scryfall catalog sync (--no-scryfall)")
    else:
        log.info("Scryfall catalog sync only for sets not yet stored in the local database")
    timer = BuildTimer(log)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    ensure_card_columns(conn)
    ensure_card_prices_table(conn)
    ensure_sets_table(conn)

    with timer.step("Set catalog sync"):
        synced_sets = sync_owned_set_metadata(
            conn,
            HEADERS,
            today,
            force_scryfall=force_scryfall,
        )
        pruned_sets = prune_unowned_sets(conn)
        if synced_sets:
            log.info("Synced %s catalog set(s) from Scryfall", synced_sets)
        if pruned_sets:
            log.info("Removed %s untracked set(s) from catalog", pruned_sets)

    catalog_set_codes = load_catalog_set_codes(conn)
    with timer.step("Restore price history"):
        restored = restore_market_values_from_history(conn)
        if restored:
            log.info("Restored %s market value(s) from price history", restored)

    cursor = conn.cursor()
    catalog_count = 0
    if not skip_scryfall:
        scryfall_sets = sets_missing_catalog(cursor, set_codes)
        if refresh_metadata:
            scryfall_sets = sorted(set(scryfall_sets) | set(set_codes))
        else:
            metadata_sets = sets_missing_metadata(cursor, set_codes)
            scryfall_sets = sorted(set(scryfall_sets) | set(metadata_sets))
        if scryfall_sets:
            log.info(
                "Fetching Scryfall catalog for %s set(s): %s",
                len(scryfall_sets),
                ", ".join(code.upper() for code in scryfall_sets),
            )
        for set_code in scryfall_sets:
            with timer.step(f"Scryfall catalog: {set_code.upper()}"):
                catalog_count += sync_set_catalog(
                    cursor,
                    set_code,
                    today,
                    catalog_set_codes,
                    force_scryfall=force_scryfall,
                )
        if not scryfall_sets:
            log.info("All tracked sets already have a local catalog")

    conn.commit()
    conn.close()
    if catalog_count:
        log.info("Synced %s card rows from Scryfall", catalog_count)

    tracked_set_codes = {code.upper() for code in set_codes}
    with timer.step("Cardmarket price guide"):
        sync_prices_from_guide(
            today,
            set_codes=tracked_set_codes,
            force_download=force_cardmarket,
            log=log,
        )

    timer.log_summary("Price update timing")
    log.info("Price update complete")


# Apply Cardmarket guide prices only (no Scryfall catalog or set-metadata work).
def update_cardmarket_prices_only(*, force_cardmarket: bool = False) -> None:
    set_codes = get_set_codes()
    if not set_codes:
        log.warning("No set codes found from purchase/deck files; nothing to price")
        return

    log.info(
        "Applying Cardmarket prices for set(s): %s",
        ", ".join(code.upper() for code in set_codes),
    )
    timer = BuildTimer(log)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    ensure_card_prices_table(conn)
    conn.close()

    tracked_set_codes = {code.upper() for code in set_codes}
    with timer.step("Cardmarket price guide"):
        sync_prices_from_guide(
            today,
            set_codes=tracked_set_codes,
            force_download=force_cardmarket,
            log=log,
        )

    timer.log_summary("Cardmarket price update timing")
    log.info("Cardmarket price update complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Update card catalog and EUR prices for tracked sets.",
    )
    parser.add_argument(
        "--no-scryfall",
        action="store_true",
        help="Skip Scryfall entirely; update prices from Cardmarket only.",
    )
    parser.add_argument(
        "--force-cardmarket",
        action="store_true",
        help="Re-download the Cardmarket price guide even if the cache is fresh.",
    )
    parser.add_argument(
        "--force-scryfall",
        action="store_true",
        help="Re-query Scryfall even when a cached response exists for today.",
    )
    parser.add_argument(
        "--refresh-art-styles",
        action="store_true",
        help="Recompute art styles from local data/art_styles/{set}.json rules only.",
    )
    parser.add_argument(
        "--refresh-metadata",
        action="store_true",
        help="Re-fetch Scryfall catalog metadata (colors and type line) for all tracked sets.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed Scryfall page progress.",
    )
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)
    if args.refresh_art_styles:
        refresh_art_styles()
    else:
        update_prices(
            skip_scryfall=args.no_scryfall,
            force_cardmarket=args.force_cardmarket,
            force_scryfall=args.force_scryfall,
            refresh_metadata=args.refresh_metadata,
        )
