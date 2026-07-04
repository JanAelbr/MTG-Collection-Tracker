import json
import sqlite3

import pandas as pd

from lib.config import APP_CACHE_DIR, DB_PATH
from lib.run_log import get_logger
from report.card_detail_data import collector_sort_key
from report.serialize_helpers import deck_card_display_name, sanitize_json_payload, str_or_empty
from util.card_metadata import card_metadata_snake

log = get_logger(__name__)

STORAGE_LOCATIONS_DATA_DIR = APP_CACHE_DIR / "storage_locations"

ALL_LOCATION_CARDS_QUERY = """
SELECT
    ci.location_slug,
    ci.set_code,
    ci.collector_number,
    ci.finish,
    COUNT(*) AS copy_count,
    MAX(ci.purchase_value) AS purchase_value,
    c.name,
    c.art_style,
    c.image_uri,
    c.colors,
    c.type_line,
    c.card_type,
    c.market_value,
    c.market_value_foil,
    c.market_value_etched
FROM card_instances ci
LEFT JOIN cards c
    ON c.set_code = ci.set_code
    AND c.collector_number = ci.collector_number
GROUP BY ci.location_slug, ci.set_code, ci.collector_number, ci.finish
ORDER BY ci.location_slug, ci.set_code, ci.collector_number, ci.finish
"""

LOCATION_SUMMARIES_QUERY = """
SELECT
    sl.location_slug,
    sl.label,
    sl.location_type,
    sl.description,
    sl.sort_order,
    COUNT(ci.instance_id) AS card_count,
    COUNT(DISTINCT ci.set_code || '|' || ci.collector_number || '|' || ci.finish) AS unique_prints
FROM storage_locations sl
LEFT JOIN card_instances ci ON ci.location_slug = sl.location_slug
GROUP BY sl.location_slug
HAVING card_count > 0
ORDER BY sl.sort_order, sl.label
"""


def _float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def location_script_stem(location_slug: str) -> str:
    return str(location_slug).replace(":", "_")


def location_script_filename(location_slug: str) -> str:
    return f"{location_script_stem(location_slug)}.js"


def _serialize_location_card(row) -> dict:
    finish = int(row[3])
    market_value = row[12] if finish == 0 else (row[13] if finish == 1 else row[14])
    meta = card_metadata_snake({
        "colors": row[9],
        "type_line": row[10],
        "card_type": row[11],
    })
    return {
        "set_code": row[1],
        "collector_number": str(row[2]),
        "finish": finish,
        "foil": finish,
        "copy_count": int(row[4]),
        "purchase_value": _float_or_none(row[5]),
        "name": deck_card_display_name({
            "catalog_name": row[6],
            "card_name": row[6],
            "set_code": row[1],
            "collector_number": row[2],
        }),
        "art_style": str_or_empty(row[7]),
        "image_uri": str_or_empty(row[8]),
        **meta,
        "current_value": _float_or_none(market_value),
    }


def _sort_location_cards(cards: list[dict]) -> list[dict]:
    return sorted(cards, key=lambda card: (
        card["set_code"],
        collector_sort_key(card["collector_number"]),
        card["finish"],
    ))


def _card_instances_available(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_instances'"
    ).fetchone()
    return row is not None


def _load_location_summaries(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(LOCATION_SUMMARIES_QUERY).fetchall()
    return [
        {
            "slug": slug,
            "label": label,
            "locationType": location_type,
            "description": description or "",
            "sortOrder": int(sort_order),
            "cardCount": int(card_count),
            "uniquePrints": int(unique_prints),
        }
        for slug, label, location_type, description, sort_order, card_count, unique_prints in rows
    ]


def _load_all_location_cards(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    rows = conn.execute(ALL_LOCATION_CARDS_QUERY).fetchall()
    cards_by_location: dict[str, list[dict]] = {}
    for row in rows:
        location_slug = row[0]
        cards_by_location.setdefault(location_slug, []).append(_serialize_location_card(row))

    return {
        slug: _sort_location_cards(cards)
        for slug, cards in cards_by_location.items()
    }


def load_storage_location_cards(conn: sqlite3.Connection | None = None) -> dict[str, list[dict]]:
    if conn is None:
        with sqlite3.connect(DB_PATH) as connection:
            if not _card_instances_available(connection):
                return {}
            return _load_all_location_cards(connection)
    if not _card_instances_available(conn):
        return {}
    return _load_all_location_cards(conn)


def load_storage_report_data() -> tuple[dict, dict[str, list[dict]]]:
    with sqlite3.connect(DB_PATH) as conn:
        if not _card_instances_available(conn):
            payload = {
                "locations": [],
                "defaultLocation": "",
            }
            return payload, {}
        locations = _load_location_summaries(conn)
        cards_by_location = _load_all_location_cards(conn)

    default_location = locations[0]["slug"] if locations else ""
    payload = {
        "locations": locations,
        "defaultLocation": default_location,
    }
    return payload, cards_by_location


# Build the lightweight client payload for the storage report page.
def load_storage_client_payload() -> dict:
    payload, _cards = load_storage_report_data()
    return payload


# Write one JS file per storage location, skipping unchanged payloads.
def write_storage_location_scripts(
    cards_by_location: dict[str, list[dict]] | None = None,
) -> int:
    if cards_by_location is None:
        cards_by_location = load_storage_location_cards()

    STORAGE_LOCATIONS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    expected_names = {
        location_script_filename(slug)
        for slug in cards_by_location
    }

    for location_slug, cards in sorted(cards_by_location.items()):
        filename = location_script_filename(location_slug)
        path = STORAGE_LOCATIONS_DATA_DIR / filename
        safe_payload = sanitize_json_payload(cards)
        content = (
            "window.STORAGE_LOCATION_CARDS = "
            f"{json.dumps(safe_payload, ensure_ascii=False, separators=(',', ':'))};"
        )
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
        written += 1

    for stale in STORAGE_LOCATIONS_DATA_DIR.glob("*.js"):
        if stale.name not in expected_names:
            stale.unlink()
            written += 1

    if written:
        log.info(
            "Storage location data: %s location file(s) updated",
            written,
        )
    return written
