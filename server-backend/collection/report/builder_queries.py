import sqlite3

from util.alchemy_cards import exclude_alchemy_sql
from util.card_metadata import card_metadata_api, is_legendary_commander_candidate, parse_card_colors
from util.card_role_seed import card_roles
from util.commander_rules import card_is_legal_for_deck, commander_color_identity

OWNED_PRINTS_QUERY = """
SELECT
    c.name,
    c.set_code,
    c.collector_number,
    ci.finish,
    ci.location_slug,
    c.colors,
    c.color_identity,
    c.type_line,
    c.card_type,
    c.oracle_text,
    c.mana_cost,
    c.cmc,
    c.legalities,
    c.is_basic_land,
    c.image_uri,
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched,
    COUNT(ci.instance_id) AS copy_count
FROM card_instances ci
JOIN cards c
    ON c.set_code = ci.set_code
    AND c.collector_number = ci.collector_number
WHERE ci.location_slug IN ({placeholders})
  AND {exclude_alchemy}
GROUP BY c.name, c.set_code, c.collector_number, ci.finish, ci.location_slug
"""

CATALOG_CARDS_QUERY = """
SELECT
    c.name,
    c.set_code,
    c.collector_number,
    c.colors,
    c.color_identity,
    c.type_line,
    c.card_type,
    c.oracle_text,
    c.mana_cost,
    c.cmc,
    c.legalities,
    c.is_basic_land,
    c.image_uri,
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched
FROM cards c
JOIN tracked_sets ts ON ts.set_code = c.set_code
WHERE {exclude_alchemy}
"""


def _row_to_card(row, *, owned: bool = False, finish: int | None = None) -> dict:
    keys = row.keys() if hasattr(row, "keys") else []
    payload = {key: row[key] for key in keys}
    meta = card_metadata_api(payload)
    card = {
        "name": payload.get("name") or "",
        "setCode": payload.get("set_code") or "",
        "collectorNumber": str(payload.get("collector_number") or ""),
        "finish": int(finish if finish is not None else payload.get("finish") or 0),
        "owned": owned,
        **meta,
    }
    if payload.get("location_slug"):
        card["locationSlug"] = payload["location_slug"]
    if payload.get("copy_count") is not None:
        card["copyCount"] = int(payload["copy_count"])
    for field, api_field in (
        ("market_value", "marketValue"),
        ("market_value_foil", "marketValueFoil"),
        ("market_value_etched", "marketValueEtched"),
        ("image_uri", "imageUri"),
    ):
        if payload.get(field) is not None:
            card[api_field] = payload[field]
    return card


def _filter_locations(location_slugs: list[str], *, include_deck_storage: bool) -> list[str]:
    cleaned = [slug.strip() for slug in location_slugs if slug and slug.strip()]
    if include_deck_storage:
        return cleaned
    return [slug for slug in cleaned if not slug.startswith("deck:")]


def load_owned_pool(
    conn: sqlite3.Connection,
    location_slugs: list[str],
    *,
    include_deck_storage: bool = False,
) -> list[dict]:
    slugs = _filter_locations(location_slugs, include_deck_storage=include_deck_storage)
    if not slugs:
        return []
    placeholders = ", ".join("?" for _ in slugs)
    query = OWNED_PRINTS_QUERY.format(
        placeholders=placeholders,
        exclude_alchemy=exclude_alchemy_sql("c.collector_number"),
    )
    rows = conn.execute(query, slugs).fetchall()
    return [_row_to_card(row, owned=True) for row in rows]


def load_owned_commanders(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    params: list[object] = []
    search_clause = ""
    trimmed = str(search or "").strip()
    if trimmed:
        search_clause = "AND LOWER(c.name) LIKE ?"
        params.append(f"%{trimmed.lower()}%")

    query = f"""
    SELECT DISTINCT
        c.name,
        c.set_code,
        c.collector_number,
        ci.finish,
        c.colors,
        c.color_identity,
        c.type_line,
        c.card_type,
        c.oracle_text,
        c.mana_cost,
        c.cmc,
        c.legalities,
        c.is_basic_land,
        c.image_uri,
        c.market_value,
        c.market_value_foil,
        c.market_value_etched
    FROM card_instances ci
    JOIN cards c
        ON c.set_code = ci.set_code
        AND c.collector_number = ci.collector_number
    WHERE {exclude_alchemy_sql("c.collector_number")}
      {search_clause}
    ORDER BY c.name, c.set_code, c.collector_number, ci.finish
    """
    rows = conn.execute(query, params).fetchall()
    cards = []
    seen = set()
    for row in rows:
        card = _row_to_card(row, owned=True)
        if not is_legendary_commander_candidate(card.get("typeLine") or ""):
            continue
        key = (card["name"], card["setCode"], card["collectorNumber"], card["finish"])
        if key in seen:
            continue
        seen.add(key)
        cards.append(card)

    total = len(cards)
    start = max(0, (max(1, page) - 1) * max(1, page_size))
    end = start + max(1, page_size)
    return {
        "cards": cards[start:end],
        "total": total,
        "page": max(1, page),
        "pageSize": max(1, page_size),
    }


def load_catalog_candidates(
    conn: sqlite3.Connection,
    *,
    allowed_identity: list[str],
    exclude_names: set[str],
) -> list[dict]:
    query = CATALOG_CARDS_QUERY.format(exclude_alchemy=exclude_alchemy_sql("c.collector_number"))
    rows = conn.execute(query).fetchall()
    cards = []
    for row in rows:
        card = _row_to_card(row, owned=False)
        name = card.get("name") or ""
        if name in exclude_names:
            continue
        if not card_is_legal_for_deck(card, allowed_identity):
            continue
        cards.append(card)
    return cards


def preview_storage_pool(
    conn: sqlite3.Connection,
    location_slugs: list[str],
    *,
    include_deck_storage: bool = False,
) -> dict:
    pool = load_owned_pool(conn, location_slugs, include_deck_storage=include_deck_storage)
    unique_names = {card["name"] for card in pool if card.get("name")}
    commanders = sum(
        1 for card in pool if is_legendary_commander_candidate(card.get("typeLine") or "")
    )
    return {
        "cardCount": len(pool),
        "uniqueNames": len(unique_names),
        "commanderCandidates": commanders,
        "locations": _filter_locations(location_slugs, include_deck_storage=include_deck_storage),
    }


def resolve_commander_rows(conn: sqlite3.Connection, commanders: list[dict]) -> list[dict]:
    rows = []
    for commander in commanders:
        set_code = str(commander.get("setCode") or commander.get("set_code") or "").upper()
        collector_number = str(commander.get("collectorNumber") or commander.get("collector_number") or "")
        finish = int(commander.get("finish") or 0)
        row = conn.execute(
            f"""
            SELECT *
            FROM cards
            WHERE set_code = ? AND collector_number = ?
              AND {exclude_alchemy_sql()}
            """,
            (set_code, collector_number),
        ).fetchone()
        if row is None:
            continue
        card = _row_to_card(row, owned=True, finish=finish)
        rows.append(card)
    return rows


def cheapest_finish_value(card: dict, finish: int) -> float | None:
    if finish == 1:
        return card.get("marketValueFoil")
    if finish == 2:
        return card.get("marketValueEtched")
    return card.get("marketValue")


def pick_best_print(cards: list[dict], *, prefer_owned: bool) -> dict | None:
    if not cards:
        return None

    def sort_key(card: dict):
        owned_rank = 0 if card.get("owned") else 1
        if prefer_owned:
            owned_rank = 0 if card.get("owned") else 1
        value = cheapest_finish_value(card, int(card.get("finish") or 0))
        value_rank = value if value is not None else 999999.0
        return (owned_rank, value_rank, card.get("setCode") or "", card.get("collectorNumber") or "")

    return sorted(cards, key=sort_key)[0]


def dedupe_pool_by_name(pool: list[dict], *, prefer_owned: bool = True) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for card in pool:
        name = card.get("name") or ""
        if not name:
            continue
        grouped.setdefault(name, []).append(card)
    return {
        name: pick_best_print(cards, prefer_owned=prefer_owned)
        for name, cards in grouped.items()
        if pick_best_print(cards, prefer_owned=prefer_owned)
    }


def commander_keywords(commander_rows: list[dict]) -> set[str]:
    stopwords = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "you",
        "your", "that", "this", "when", "each", "other", "target", "card", "creature",
        "per", "up", "one", "two", "three", "may", "if", "its", "it", "from", "into",
    }
    keywords: set[str] = set()
    for commander in commander_rows:
        for source in (
            commander.get("name") or "",
            commander.get("oracleText") or commander.get("oracle_text") or "",
            commander.get("typeLine") or commander.get("type_line") or "",
        ):
            for token in str(source).replace("—", " ").replace(",", " ").split():
                word = "".join(char for char in token.lower() if char.isalnum())
                if len(word) >= 4 and word not in stopwords:
                    keywords.add(word)
    return keywords


def identity_for_commanders(commander_rows: list[dict]) -> list[str]:
    return commander_color_identity(commander_rows)
