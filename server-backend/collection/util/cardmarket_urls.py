"""Cardmarket product URLs per card finish."""

from __future__ import annotations

import re
import sqlite3
from urllib.parse import parse_qs, urlparse

from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    card_finish_flags,
    is_etched_only_print,
    normalize_finish,
)
from util.scryfall_card import cardmarket_url as scryfall_cardmarket_url

_PRODUCT_ID_PATTERN = re.compile(r"idProduct=(\d+)", re.IGNORECASE)
PRIMARY_NONFOIL_KEYS = ("trend", "avg", "avg7", "avg30", "avg1")
PRIMARY_FOIL_KEYS = ("trend-foil", "avg-foil", "avg7-foil", "avg30-foil", "avg1-foil")
# Some sets (e.g. LTC) list nonfoil and foil as separate product blocks in the guide.
SPLIT_BLOCK_FOIL_OFFSET = 20
# Scroll showcase and other sparse guides can leave gaps between paired products.
MAX_PAIR_SEARCH_DISTANCE = 7
PLAUSIBLE_NONFOIL_TREND_CAP = 150.0

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


def _entry_has_nonfoil_prices(entry: dict | None) -> bool:
    if not entry:
        return False
    return any(
        entry.get(key) not in (None, 0) and entry.get(key) > 0
        for key in PRIMARY_NONFOIL_KEYS
    )


def _entry_has_foil_prices(entry: dict | None) -> bool:
    if not entry:
        return False
    return any(
        entry.get(key) not in (None, 0) and entry.get(key) > 0
        for key in PRIMARY_FOIL_KEYS
    )


def _entry_is_foil_only(entry: dict | None) -> bool:
    return _entry_has_foil_prices(entry) and not _entry_has_nonfoil_prices(entry)


def _find_split_block_foil_product(product_id: int, guide: dict[int, dict]) -> int | None:
    source = guide.get(product_id)
    if not source or _entry_has_foil_prices(source) or not _entry_has_nonfoil_prices(source):
        return None
    candidate_id = product_id + SPLIT_BLOCK_FOIL_OFFSET
    candidate = guide.get(candidate_id)
    if _entry_is_foil_only(candidate):
        return candidate_id
    return None


def _find_split_block_nonfoil_product(product_id: int, guide: dict[int, dict]) -> int | None:
    source = guide.get(product_id)
    if not source or not _entry_is_foil_only(source):
        return None
    candidate_id = product_id - SPLIT_BLOCK_FOIL_OFFSET
    candidate = guide.get(candidate_id)
    if candidate and _entry_has_nonfoil_prices(candidate) and not _entry_is_foil_only(candidate):
        return candidate_id
    return None


def _is_plausible_nonfoil_product(product_id: int | None, guide: dict[int, dict]) -> bool:
    if product_id is None:
        return False
    trend = _guide_primary_trend(guide.get(product_id))
    return trend is not None and 0 < trend <= PLAUSIBLE_NONFOIL_TREND_CAP


def _normalized_nonfoil_product_id(
    cardmarket_url: str | None,
    guide: dict[int, dict],
) -> int | None:
    normalized, _ = normalize_cardmarket_url_columns(cardmarket_url, None, guide)
    return parse_id_product(normalized)


def _should_apply_scryfall_nonfoil_url(
    existing: str | None,
    scryfall: str | None,
    guide: dict[int, dict],
) -> bool:
    if not scryfall:
        return False
    if not existing:
        new_id = _normalized_nonfoil_product_id(scryfall, guide)
        return new_id is None or _is_plausible_nonfoil_product(new_id, guide)
    existing_id = parse_id_product(existing)
    if existing_id is not None and _is_plausible_nonfoil_product(existing_id, guide):
        return False
    new_id = _normalized_nonfoil_product_id(scryfall, guide)
    return new_id is not None and _is_plausible_nonfoil_product(new_id, guide)


def find_paired_product_id(
    product_id: int,
    guide: dict[int, dict],
    target_finish: int,
) -> int | None:
    want = "foil" if normalize_finish(target_finish) == FINISH_FOIL else "nonfoil"
    # Search forward first when resolving foil (+1, +2, …) and backward for nonfoil
    # so sparse guides do not pair with the previous card's opposite finish (LTR scroll).
    if want == "foil":
        delta_order = [
            *range(1, MAX_PAIR_SEARCH_DISTANCE + 1),
            *range(-1, -MAX_PAIR_SEARCH_DISTANCE - 1, -1),
        ]
    else:
        delta_order = [
            *range(-1, -MAX_PAIR_SEARCH_DISTANCE - 1, -1),
            *range(1, MAX_PAIR_SEARCH_DISTANCE + 1),
        ]
    for delta in delta_order:
        neighbor_id = product_id + delta
        entry = guide.get(neighbor_id)
        if not entry:
            continue
        if guide_entry_finish_bias(entry) == want:
            if want == "nonfoil" and not _is_plausible_nonfoil_product(neighbor_id, guide):
                continue
            return neighbor_id
    if want == "foil":
        return _find_split_block_foil_product(product_id, guide)
    paired = _find_split_block_nonfoil_product(product_id, guide)
    if paired is not None and _is_plausible_nonfoil_product(paired, guide):
        return paired
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
                nonfoil_url = (
                    build_product_url(paired)
                    if paired is not None and _is_plausible_nonfoil_product(paired, guide)
                    else None
                )
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
                if paired is not None and _is_plausible_nonfoil_product(paired, guide):
                    nonfoil_url = build_product_url(paired)

    return nonfoil_url, foil_url


def cardmarket_url_for_finish(
    row,
    finish: int,
    guide: dict[int, dict] | None = None,
) -> str | None:
    finish_id = normalize_finish(finish)
    nonfoil_url = coerce_cardmarket_url(_row_value(row, "cardmarket_url"))
    foil_url = coerce_cardmarket_url(_row_value(row, "cardmarket_url_foil"))

    if finish_id == FINISH_ETCHED:
        if foil_url:
            return foil_url
        if is_etched_only_print(row) and nonfoil_url and guide:
            product_id = parse_id_product(nonfoil_url)
            if product_id is not None:
                paired = find_paired_product_id(product_id, guide, FINISH_FOIL)
                if paired is not None:
                    return build_product_url(paired)
        return nonfoil_url

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
                if paired is not None and _is_plausible_nonfoil_product(paired, guide):
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
    *,
    guide: dict[int, dict] | None = None,
) -> tuple[str | None, str | None]:
    nonfoil_url = coerce_cardmarket_url(cardmarket_url)
    foil_url = coerce_cardmarket_url(cardmarket_url_foil)
    if guide is None:
        from util.cardmarket_prices import load_price_guide_index

        guide = load_price_guide_index()
    for finish_id, url in scryfall_url_targets(card).items():
        if finish_id == FINISH_FOIL:
            if not foil_url:
                foil_url = url
        elif _should_apply_scryfall_nonfoil_url(nonfoil_url, url, guide):
            nonfoil_url = url
    has_nonfoil, has_foil, has_etched = card_finish_flags(card)
    if has_nonfoil and not has_foil and not has_etched and foil_url and not nonfoil_url:
        nonfoil_url, foil_url = foil_url, None
    return nonfoil_url, foil_url


def _collector_number_sort_key(value: str) -> int | None:
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    return None


def _nonfoil_product_points(
    rows: list[tuple],
    guide: dict[int, dict],
) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for collector_number, cardmarket_url, cardmarket_url_foil, *_rest in rows:
        collector_key = _collector_number_sort_key(collector_number)
        if collector_key is None:
            continue
        url = coerce_cardmarket_url(cardmarket_url) or coerce_cardmarket_url(cardmarket_url_foil)
        product_id = parse_id_product(url)
        if product_id is None:
            continue
        entry = guide.get(product_id)
        if entry and _entry_has_nonfoil_prices(entry):
            points.append((collector_key, product_id))
    return sorted(points)


MAX_INTERPOLATION_STEP = 50


def _is_viable_anchor_pair(lower: tuple[int, int], upper: tuple[int, int]) -> bool:
    cn_lo, pid_lo = lower
    cn_hi, pid_hi = upper
    if cn_hi == cn_lo:
        return False
    step = abs(pid_hi - pid_lo) / (cn_hi - cn_lo)
    return step <= MAX_INTERPOLATION_STEP


def _infer_product_from_neighbors(
    collector_number: str,
    points: list[tuple[int, int]],
) -> int | None:
    collector_key = _collector_number_sort_key(collector_number)
    if collector_key is None or not points:
        return None
    before = sorted((point for point in points if point[0] < collector_key), key=lambda item: item[0])
    after = sorted((point for point in points if point[0] > collector_key), key=lambda item: item[0])
    if not before or not after:
        return None
    upper = after[0]
    lower = None
    for candidate in reversed(before):
        if _is_viable_anchor_pair(candidate, upper):
            lower = candidate
            break
    if lower is None:
        return None
    cn_lo, pid_lo = lower
    cn_hi, pid_hi = upper
    return round(pid_lo + (pid_hi - pid_lo) * (collector_key - cn_lo) / (cn_hi - cn_lo))


def _guide_primary_trend(entry: dict | None) -> float | None:
    if not entry:
        return None
    for key in PRIMARY_NONFOIL_KEYS:
        value = entry.get(key)
        if value is not None and value > 0:
            return float(value)
    return None


def _filter_price_outlier_anchor_points(
    points: list[tuple[int, int]],
    guide: dict[int, dict],
    *,
    ratio: float = 12.0,
    minimum: float = 15.0,
) -> list[tuple[int, int]]:
    trends = [
        trend
        for _, product_id in points
        if (trend := _guide_primary_trend(guide.get(product_id))) is not None
    ]
    if len(trends) < 3:
        return points
    median = sorted(trends)[len(trends) // 2]
    cap = max(minimum, median * ratio)
    return [
        point
        for point in points
        if (trend := _guide_primary_trend(guide.get(point[1]))) is None or trend <= cap
    ]


def _linked_nonfoil_trend_is_outlier(
    cardmarket_url: str | None,
    neighbor_points: list[tuple[int, int]],
    guide: dict[int, dict],
) -> bool:
    product_id = parse_id_product(cardmarket_url)
    if product_id is None:
        return False
    trend = _guide_primary_trend(guide.get(product_id))
    if trend is None or trend <= 0:
        return False
    filtered = _filter_price_outlier_anchor_points(neighbor_points, guide)
    neighbor_trends = [
        neighbor_trend
        for _, pid in filtered
        if (neighbor_trend := _guide_primary_trend(guide.get(pid))) is not None
    ]
    if len(neighbor_trends) < 2:
        return False
    median = sorted(neighbor_trends)[len(neighbor_trends) // 2]
    cap = max(15.0, median * 12.0)
    return trend > cap


def _resolve_repair_nonfoil_product_id(
    collector_number: str,
    neighbor_points: list[tuple[int, int]],
    guide: dict[int, dict],
) -> int | None:
    filtered = _filter_price_outlier_anchor_points(neighbor_points, guide)
    inferred = _infer_product_from_neighbors(collector_number, filtered)
    if inferred is not None:
        entry = guide.get(inferred)
        if entry and _entry_has_nonfoil_prices(entry):
            return inferred

    collector_key = _collector_number_sort_key(collector_number)
    if collector_key is None or not filtered:
        return None

    close = sorted(
        filtered,
        key=lambda item: (
            abs(item[0] - collector_key),
            _guide_primary_trend(guide.get(item[1])) or 9999.0,
            item[0],
        ),
    )
    for _, product_id in close[:4]:
        entry = guide.get(product_id)
        if entry and _entry_has_nonfoil_prices(entry):
            return product_id
    return None


def _needs_nonfoil_url_repair(
    *,
    has_nonfoil: int | None,
    has_foil: int | None,
    cardmarket_url: str | None,
    cardmarket_url_foil: str | None,
    guide: dict[int, dict],
    neighbor_points: list[tuple[int, int]] | None = None,
) -> bool:
    if not has_nonfoil or has_foil:
        return False
    nonfoil_url = coerce_cardmarket_url(cardmarket_url)
    foil_url = coerce_cardmarket_url(cardmarket_url_foil)
    if nonfoil_url:
        product_id = parse_id_product(nonfoil_url)
        entry = guide.get(product_id) if product_id is not None else None
        if entry and _entry_has_nonfoil_prices(entry):
            if neighbor_points and _linked_nonfoil_trend_is_outlier(
                nonfoil_url,
                neighbor_points,
                guide,
            ):
                return True
            return False
    if not nonfoil_url and not foil_url:
        return True
    candidate = nonfoil_url or foil_url
    product_id = parse_id_product(candidate)
    if product_id is None:
        return True
    entry = guide.get(product_id)
    if entry and _entry_has_nonfoil_prices(entry):
        return not nonfoil_url
    return True


def repair_mislinked_cardmarket_urls(conn: sqlite3.Connection, guide: dict[int, dict]) -> int:
    card_columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
    if "has_nonfoil" in card_columns:
        finish_select = (
            "COALESCE(has_nonfoil, 1), COALESCE(has_foil, 0), COALESCE(has_etched, 0)"
        )
    else:
        finish_select = "1, 0, 0"
    rows = conn.execute(
        f"""
        SELECT set_code, collector_number, cardmarket_url, cardmarket_url_foil,
               {finish_select}
        FROM cards
        """
    ).fetchall()
    by_set: dict[str, list[tuple]] = {}
    for row in rows:
        by_set.setdefault(row[0], []).append(row[1:])

    updated = 0
    for set_code, set_rows in by_set.items():
        points = _nonfoil_product_points(set_rows, guide)
        for collector_number, cardmarket_url, cardmarket_url_foil, has_nonfoil, has_foil, _has_etched in set_rows:
            if not _needs_nonfoil_url_repair(
                has_nonfoil=has_nonfoil,
                has_foil=has_foil,
                cardmarket_url=cardmarket_url,
                cardmarket_url_foil=cardmarket_url_foil,
                guide=guide,
                neighbor_points=points,
            ):
                continue
            collector_key = _collector_number_sort_key(collector_number)
            neighbor_points = [
                point for point in points
                if point[0] != collector_key
            ]
            inferred = _resolve_repair_nonfoil_product_id(
                collector_number,
                neighbor_points,
                guide,
            )
            if inferred is None:
                continue
            entry = guide.get(inferred)
            if not entry or not _entry_has_nonfoil_prices(entry):
                continue
            repaired = (build_product_url(inferred), None)
            current = (
                (cardmarket_url or "").strip() or None,
                (cardmarket_url_foil or "").strip() or None,
            )
            if current == repaired:
                continue
            conn.execute(
                """
                UPDATE cards
                SET cardmarket_url = ?, cardmarket_url_foil = ?
                WHERE set_code = ? AND collector_number = ?
                """,
                (repaired[0], repaired[1], set_code, collector_number),
            )
            updated += 1
    return updated


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
    updated += repair_mislinked_cardmarket_urls(conn, guide)
    return updated
