"""Cardmarket product URLs per card finish."""

from __future__ import annotations

import re
import sqlite3
from urllib.parse import parse_qs, urlparse

from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, normalize_finish
from util.scryfall_card import cardmarket_url as scryfall_cardmarket_url

_PRODUCT_ID_PATTERN = re.compile(r"idProduct=(\d+)", re.IGNORECASE)
PRIMARY_NONFOIL_KEYS = ("trend", "avg", "avg7", "avg30", "avg1")
PRIMARY_FOIL_KEYS = ("trend-foil", "avg-foil", "avg7-foil", "avg30-foil", "avg1-foil")

CARDMARKET_PRODUCT_URL = "https://www.cardmarket.com/en/Magic/Products?idProduct={product_id}"


def coerce_cardmarket_url(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def parse_id_product(cardmarket_url: str | None) -> int | None:
    cardmarket_url = coerce_cardmarket_url(cardmarket_url)
    if not cardmarket_url:
        return None
    match = _PRODUCT_ID_PATTERN.search(cardmarket_url)
    if match:
        return int(match.group(1))
    parsed = urlparse(cardmarket_url)
    query = parse_qs(parsed.query)
    if "idProduct" in query:
        return int(query["idProduct"][0])
    return None


def build_product_url(product_id: int) -> str:
    return CARDMARKET_PRODUCT_URL.format(product_id=product_id)


def _row_value(row, key: str):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def guide_entry_finish_bias(entry: dict | None) -> str:
    if not entry:
        return "unknown"
    has_nonfoil = any(
        entry.get(key) not in (None, 0) and entry.get(key) > 0
        for key in PRIMARY_NONFOIL_KEYS
    )
    has_foil = any(
        entry.get(key) not in (None, 0) and entry.get(key) > 0
        for key in PRIMARY_FOIL_KEYS
    )
    if has_nonfoil and has_foil:
        return "both"
    if has_nonfoil:
        return "nonfoil"
    if has_foil:
        return "foil"
    return "unknown"


def find_paired_product_id(
    product_id: int,
    guide: dict[int, dict],
    target_finish: int,
) -> int | None:
    want = "foil" if normalize_finish(target_finish) == FINISH_FOIL else "nonfoil"
    # Cardmarket lists nonfoil immediately before foil for the same printing.
    # Prefer +1 when resolving foil and -1 when resolving nonfoil so we do not
    # grab the foil product for the previous printing (e.g. LTR scroll showcase).
    deltas = (1, -1) if want == "foil" else (-1, 1)
    for delta in deltas:
        neighbor_id = product_id + delta
        entry = guide.get(neighbor_id)
        if not entry:
            continue
        if guide_entry_finish_bias(entry) == want:
            return neighbor_id
    return None


def normalize_cardmarket_url_columns(
    cardmarket_url: str | None,
    cardmarket_url_foil: str | None,
    guide: dict[int, dict],
) -> tuple[str | None, str | None]:
    nonfoil_url = coerce_cardmarket_url(cardmarket_url)
    foil_url = coerce_cardmarket_url(cardmarket_url_foil)

    if nonfoil_url and not foil_url:
        product_id = parse_id_product(nonfoil_url)
        if product_id is not None:
            bias = guide_entry_finish_bias(guide.get(product_id))
            if bias == "foil":
                foil_url = nonfoil_url
                paired = find_paired_product_id(product_id, guide, FINISH_NONFOIL)
                nonfoil_url = build_product_url(paired) if paired else None
            elif bias == "nonfoil":
                paired = find_paired_product_id(product_id, guide, FINISH_FOIL)
                if paired is not None:
                    foil_url = build_product_url(paired)
    elif foil_url and not nonfoil_url:
        product_id = parse_id_product(foil_url)
        if product_id is not None:
            bias = guide_entry_finish_bias(guide.get(product_id))
            if bias == "nonfoil":
                nonfoil_url = foil_url
                paired = find_paired_product_id(product_id, guide, FINISH_FOIL)
                foil_url = build_product_url(paired) if paired else None
            elif bias == "foil":
                paired = find_paired_product_id(product_id, guide, FINISH_NONFOIL)
                if paired is not None:
                    nonfoil_url = build_product_url(paired)

    return nonfoil_url, foil_url


def cardmarket_url_for_finish(
    row,
    finish: int,
    guide: dict[int, dict] | None = None,
) -> str | None:
    finish_id = normalize_finish(finish)
    if finish_id == FINISH_ETCHED:
        return None
    nonfoil_url = coerce_cardmarket_url(_row_value(row, "cardmarket_url"))
    foil_url = coerce_cardmarket_url(_row_value(row, "cardmarket_url_foil"))

    if finish_id == FINISH_FOIL:
        if foil_url:
            return foil_url
        if nonfoil_url and guide:
            product_id = parse_id_product(nonfoil_url)
            if product_id is not None:
                bias = guide_entry_finish_bias(guide.get(product_id))
                if bias == "nonfoil":
                    paired = find_paired_product_id(product_id, guide, FINISH_FOIL)
                    if paired is not None:
                        return build_product_url(paired)
        return nonfoil_url

    if nonfoil_url and guide:
        product_id = parse_id_product(nonfoil_url)
        if product_id is not None:
            bias = guide_entry_finish_bias(guide.get(product_id))
            if bias == "foil":
                paired = find_paired_product_id(product_id, guide, FINISH_NONFOIL)
                if paired is not None:
                    return build_product_url(paired)
            elif bias in ("nonfoil", "both", "unknown"):
                return nonfoil_url
    elif nonfoil_url:
        return nonfoil_url
    if foil_url and guide:
        product_id = parse_id_product(foil_url)
        if product_id is not None and guide_entry_finish_bias(guide.get(product_id)) == "foil":
            paired = find_paired_product_id(product_id, guide, FINISH_NONFOIL)
            if paired is not None:
                return build_product_url(paired)
    return foil_url


def scryfall_url_targets(card: dict) -> dict[int, str]:
    url = scryfall_cardmarket_url(card)
    if not url:
        return {}

    finishes = set(card.get("finishes") or [])
    foil_print = card.get("foil")
    if foil_print is True:
        return {FINISH_FOIL: url}
    if foil_print is False:
        return {FINISH_NONFOIL: url}
    if finishes == {"foil"}:
        return {FINISH_FOIL: url}
    if finishes == {"nonfoil"}:
        return {FINISH_NONFOIL: url}
    if "foil" in finishes and "nonfoil" not in finishes:
        return {FINISH_FOIL: url}
    if "nonfoil" in finishes and "foil" not in finishes:
        return {FINISH_NONFOIL: url}
    return {FINISH_NONFOIL: url}


def merge_cardmarket_urls(
    cardmarket_url: str | None,
    cardmarket_url_foil: str | None,
    card: dict,
) -> tuple[str | None, str | None]:
    nonfoil_url = coerce_cardmarket_url(cardmarket_url)
    foil_url = coerce_cardmarket_url(cardmarket_url_foil)
    for finish_id, url in scryfall_url_targets(card).items():
        if finish_id == FINISH_FOIL:
            foil_url = url
        else:
            nonfoil_url = url
    return nonfoil_url, foil_url


def load_existing_cardmarket_urls(
    cursor,
    set_code: str,
    collector_number: str,
) -> tuple[str | None, str | None]:
    row = cursor.execute(
        """
        SELECT cardmarket_url, cardmarket_url_foil
        FROM cards
        WHERE set_code = ? AND collector_number = ?
        """,
        (set_code.upper(), str(collector_number)),
    ).fetchone()
    if not row:
        return None, None
    return row[0], row[1]


def backfill_cardmarket_urls(conn: sqlite3.Connection, guide: dict[int, dict]) -> int:
    rows = conn.execute(
        """
        SELECT set_code, collector_number, cardmarket_url, cardmarket_url_foil
        FROM cards
        WHERE (cardmarket_url IS NOT NULL AND TRIM(cardmarket_url) != '')
           OR (cardmarket_url_foil IS NOT NULL AND TRIM(cardmarket_url_foil) != '')
        """
    ).fetchall()
    updated = 0
    for set_code, collector_number, cardmarket_url, cardmarket_url_foil in rows:
        normalized = normalize_cardmarket_url_columns(cardmarket_url, cardmarket_url_foil, guide)
        current = (
            (cardmarket_url or "").strip() or None,
            (cardmarket_url_foil or "").strip() or None,
        )
        if current == normalized:
            continue
        conn.execute(
            """
            UPDATE cards
            SET cardmarket_url = ?, cardmarket_url_foil = ?
            WHERE set_code = ? AND collector_number = ?
            """,
            (normalized[0], normalized[1], set_code, collector_number),
        )
        updated += 1
    return updated
