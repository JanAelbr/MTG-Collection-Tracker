import sqlite3
import time
from datetime import date

from lib.art_styles import get_art_style
from lib.config import (
    DB_PATH,
    HTTP_USER_AGENT,
    canonical_set_code_lower,
    normalize_set_code,
)
from lib.run_log import BuildTimer, get_logger
from util.cardmarket_prices import sync_prices_from_guide
from util.card_finishes import card_finish_flags
from util.card_prices import load_existing_card_prices
from util.cardmarket_urls import load_existing_cardmarket_urls, merge_cardmarket_urls
from util.db_migrate import ensure_card_columns, ensure_card_prices_table
from util.deck_tables import list_deck_sync_set_codes
from util.scryfall_card import (
    card_colors_json,
    card_image_uri,
    card_primary_type,
    card_type_line,
)
from util.alchemy_cards import is_alchemy_scryfall_card
from util.scryfall_client import scryfall_get
from util.set_catalog import upsert_set_from_card
from util.tracked_sets import ensure_tracked_sets_ready, list_tracked_set_codes

HEADERS = {"User-Agent": HTTP_USER_AGENT}
INSERT_CARD_SQL = """
INSERT OR REPLACE INTO cards (
    id, set_code, collector_number, name, art_style,
    market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched,
    image_uri, cardmarket_url, cardmarket_url_foil, colors, type_line, card_type
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

log = get_logger(__name__)


def get_set_codes() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        ensure_tracked_sets_ready(conn)
        purchase_sets = {
            canonical_set_code_lower(code)
            for code in list_tracked_set_codes(conn)
        }
        deck_sets = {canonical_set_code_lower(code) for code in list_deck_sync_set_codes(conn)}
    return sorted(code for code in (purchase_sets | deck_sets) if code)


def scryfall_search_url(set_code: str) -> str:
    return (
        f"https://api.scryfall.com/cards/search"
        f"?q=set:{set_code}&unique=prints&order=set"
    )


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


def upsert_card(
    cursor,
    set_code: str,
    card: dict,
    price_date: str,
    owned_set_codes: set[str] | None = None,
) -> None:
    if is_alchemy_scryfall_card(card):
        return
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


def write_price_page(
    cursor,
    set_code: str,
    page_cards: list[dict],
    price_date: str,
    owned_set_codes: set[str] | None = None,
) -> int:
    written = 0
    for card in page_cards:
        if is_alchemy_scryfall_card(card):
            continue
        upsert_card(cursor, set_code, card, price_date, owned_set_codes)
        written += 1
    log_page_fetch(set_code, page_cards)
    return written


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
    while url:
        data = fetch_scryfall_page(url, force=force_scryfall)
        if data is None:
            break
        count += write_price_page(
            cursor,
            set_code,
            data.get("data", []),
            today,
            owned_set_codes,
        )
        url = data.get("next_page")
        time.sleep(0.1)

    cursor.execute(
        "DELETE FROM cards WHERE set_code = ? AND UPPER(collector_number) LIKE 'A-%'",
        (set_code.upper(),),
    )

    log.info("Set %s: retrieved %s cards from Scryfall", set_code.upper(), count)
    return count


def update_cardmarket_prices_only(*, force_cardmarket: bool = False) -> None:
    set_codes = get_set_codes()
    if not set_codes:
        log.warning("No set codes found from tracked sets/decks; nothing to price")
        return

    log.info(
        "Applying Cardmarket prices for set(s): %s",
        ", ".join(code.upper() for code in set_codes),
    )
    timer = BuildTimer(log)
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    ensure_card_prices_table(conn)
    conn.close()

    tracked_set_codes = {normalize_set_code(code) for code in set_codes}
    with timer.step("Cardmarket price guide"):
        sync_prices_from_guide(
            today,
            set_codes=tracked_set_codes,
            force_download=force_cardmarket,
            log=log,
        )

    timer.log_summary("Cardmarket price update timing")
    log.info("Cardmarket price update complete")
