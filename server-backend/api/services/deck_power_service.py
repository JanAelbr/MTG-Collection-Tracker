import sqlite3
from datetime import date

import pandas as pd

from report.deck_queries import deck_scope, load_deck_cards_df
from report.serialize_helpers import is_missing, str_or_empty
from util.card_metadata import _nullable_int_flag, card_row_needs_power_metadata, resolve_card_cmc
from util.card_role_seed import card_bracket_weight, card_roles_for
from util.commander_rules import validate_commander_deck

COMPONENT_TARGETS = {
    "ramp": (8, 12),
    "draw": (6, 10),
    "interaction": (6, 10),
}

# Count at or above this value maps to a 100 power-intensity score.
POWER_INTENSITY_SCALES = {
    "tutors": 4,
    "fastMana": 6,
    "gameChangers": 4,
    "comboDensity": 3,
}

BRACKET_THRESHOLDS = [
    (0, 1),
    (6, 2),
    (14, 3),
    (26, 4),
    (42, 5),
]

POWER_SIGNAL_ROLES = frozenset({
    "tutor",
    "fast_mana",
    "game_changer",
    "combo_piece",
    "extra_turn",
})


def _deckbuilding_score(count: int, low: int, high: int) -> int:
    """How well the deck hits recommended construction ranges."""
    if count < low:
        return max(0, int(100 * count / max(1, low)))
    if count <= high:
        return 100
    excess = count - high
    return max(0, 100 - excess * 12)


def _power_intensity_score(count: int, scale: int) -> int:
    """How many high-power staples are present; zero means no contribution."""
    if count <= 0:
        return 0
    return min(100, int(100 * count / max(1, scale)))


CATEGORY_ROLE_MAP = {
    "ramp": {"ramp"},
    "draw": {"draw"},
    "interaction": {"removal", "interaction", "protection"},
    "tutors": {"tutor"},
    "fastMana": {"fast_mana"},
    "gameChangers": {"game_changer"},
    "comboDensity": {"combo_piece"},
}


def _serialize_power_card(card: dict) -> dict:
    return {
        "cardName": str(card.get("card_name") or card.get("name") or card.get("cardName") or ""),
        "setCode": str(card.get("set_code") or card.get("setCode") or ""),
        "collectorNumber": str(card.get("collector_number") or card.get("collectorNumber") or ""),
        "finish": int(card.get("finish") or card.get("foil") or 0),
        "qty": int(card.get("qty") or 1),
        "imageUri": str(card.get("image_uri") or card.get("imageUri") or ""),
        "imageUriBack": str(card.get("image_uri_back") or card.get("imageUriBack") or ""),
        "cmc": resolve_card_cmc(card),
        "typeLine": str(card.get("type_line") or card.get("typeLine") or ""),
    }


def _is_curve_candidate(card: dict) -> bool:
    if bool(card.get("is_basic_land") or card.get("isBasicLand")):
        return False
    card_type = str(card.get("card_type") or card.get("cardType") or "").lower()
    return card_type != "land"


def _build_category_data(cards: list[dict]) -> tuple[dict[str, int], dict[str, list[dict]]]:
    counts = {
        "ramp": 0,
        "draw": 0,
        "interaction": 0,
        "tutors": 0,
        "fastMana": 0,
        "gameChangers": 0,
        "comboDensity": 0,
    }
    category_cards = {key: [] for key in counts}
    curve_cards: list[dict] = []

    for card in cards:
        qty = int(card.get("qty") or 1)
        roles = set(card_roles_for(card))
        serialized = _serialize_power_card(card)

        for category_id, role_set in CATEGORY_ROLE_MAP.items():
            if not roles & role_set:
                continue
            counts[category_id] += qty
            category_cards[category_id].append(serialized)

        if _is_curve_candidate(card):
            curve_cards.append(serialized)

    curve_cards.sort(key=lambda item: (-item["cmc"], item["cardName"].lower()))
    category_cards["curve"] = curve_cards
    return counts, category_cards


def _role_counts(cards: list[dict]) -> dict[str, int]:
    counts, _ = _build_category_data(cards)
    return counts


def _nonland_cmc_values(cards: list[dict]) -> list[float]:
    values: list[float] = []
    for card in cards:
        if str(card.get("card_type") or card.get("cardType") or "").lower() == "land":
            continue
        if bool(card.get("is_basic_land") or card.get("isBasicLand")):
            continue
        cmc = resolve_card_cmc(card)
        if cmc > 0:
            values.append(cmc)
    return values


def _curve_health(cards: list[dict]) -> int:
    nonlands = _nonland_cmc_values(cards)
    if not nonlands:
        return 50
    average = sum(nonlands) / len(nonlands)
    if 2.5 <= average <= 3.8:
        return 100
    return max(0, 100 - int(abs(average - 3.15) * 25))


def _power_signal(cards: list[dict]) -> float:
    signal = 0.0
    for card in cards:
        qty = int(card.get("qty") or 1)
        name = str(card.get("card_name") or card.get("name") or card.get("cardName") or "")
        roles = set(card_roles_for(card))
        if not roles & POWER_SIGNAL_ROLES:
            continue
        weight = card_bracket_weight(name)
        if weight <= 0:
            continue
        signal += weight * qty
    return signal


def _bracket_from_signal(signal: float) -> int:
    bracket = 1
    for threshold, value in BRACKET_THRESHOLDS:
        if signal >= threshold:
            bracket = value
    return bracket


def _confidence(signal: float, card_count: int) -> str:
    if card_count < 40:
        return "low"
    if signal >= 20 or card_count >= 90:
        return "high"
    return "medium"


def _highlights(counts: dict[str, int], cards: list[dict]) -> list[str]:
    highlights = []
    if counts["gameChangers"]:
        highlights.append(f"{counts['gameChangers']} game changer(s)")
    if counts["tutors"]:
        highlights.append(f"{counts['tutors']} tutor(s)")
    if counts["fastMana"]:
        highlights.append(f"{counts['fastMana']} fast mana source(s)")
    nonlands = _nonland_cmc_values(cards)
    if nonlands:
        avg = round(sum(nonlands) / len(nonlands), 1)
        highlights.append(f"avg cmc {avg}")
    return highlights


def _warnings_from_counts(counts: dict[str, int]) -> list[str]:
    warnings = []
    if counts["interaction"] < 4:
        warnings.append("Low interaction/removal density.")
    if counts["draw"] < 4:
        warnings.append("Limited card advantage.")
    if counts["ramp"] < 6:
        warnings.append("Light on ramp.")
    graveyard_hate = counts.get("graveyardHate", 0)
    if graveyard_hate == 0:
        warnings.append("No graveyard hate.")
    return warnings


def assess_deck_power(cards: list[dict], *, commanders: list[dict] | None = None) -> dict:
    main_cards = [
        card for card in cards
        if str(card.get("section") or "main") == "main"
    ]
    counts, category_cards = _build_category_data(main_cards)
    counts["graveyardHate"] = sum(
        int(card.get("qty") or 1)
        for card in main_cards
        if "graveyard_hate" in card_roles_for(card)
    )

    components = {
        "ramp": _deckbuilding_score(counts["ramp"], *COMPONENT_TARGETS["ramp"]),
        "draw": _deckbuilding_score(counts["draw"], *COMPONENT_TARGETS["draw"]),
        "interaction": _deckbuilding_score(counts["interaction"], *COMPONENT_TARGETS["interaction"]),
        "tutors": _power_intensity_score(counts["tutors"], POWER_INTENSITY_SCALES["tutors"]),
        "fastMana": _power_intensity_score(counts["fastMana"], POWER_INTENSITY_SCALES["fastMana"]),
        "gameChangers": _power_intensity_score(
            counts["gameChangers"],
            POWER_INTENSITY_SCALES["gameChangers"],
        ),
        "comboDensity": _power_intensity_score(
            counts["comboDensity"],
            POWER_INTENSITY_SCALES["comboDensity"],
        ),
        "curve": _curve_health(main_cards),
    }

    signal = _power_signal(main_cards)
    bracket = _bracket_from_signal(signal)
    validation = validate_commander_deck(cards, commanders=commanders or [])
    warnings = _warnings_from_counts(counts)
    warnings.extend(validation.get("warnings") or [])

    return {
        "bracket": bracket,
        "confidence": _confidence(signal, len(main_cards)),
        "components": components,
        "counts": counts,
        "categoryCards": category_cards,
        "highlights": _highlights(counts, main_cards),
        "warnings": warnings,
        "powerSignal": round(signal, 1),
        "validation": validation,
    }


def _deck_needs_metadata_backfill(deck_df: pd.DataFrame) -> bool:
    if deck_df.empty:
        return False
    return any(card_row_needs_power_metadata(row) for _, row in deck_df.iterrows())


def _set_codes_missing_metadata(deck_df: pd.DataFrame) -> list[str]:
    set_codes: set[str] = set()
    for _, row in deck_df.iterrows():
        if not card_row_needs_power_metadata(row):
            continue
        set_code = str(row.get("set_code") or "").strip().upper()
        if set_code:
            set_codes.add(set_code)
    return sorted(set_codes)


def _backfill_deck_set_metadata(conn: sqlite3.Connection, deck_df: pd.DataFrame) -> None:
    set_codes = _set_codes_missing_metadata(deck_df)
    if not set_codes:
        return

    from util.price_sync import set_catalog_is_complete, sync_set_catalog

    cursor = conn.cursor()
    today = date.today().isoformat()
    for set_code in set_codes:
        if set_catalog_is_complete(cursor, set_code):
            continue
        sync_set_catalog(
            cursor,
            set_code.lower(),
            today,
            force_scryfall=False,
        )
    conn.commit()


def _cards_from_deck_df(deck_df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    cards = []
    commanders = []
    for _, row in deck_df.iterrows():
        payload = row.to_dict()
        is_basic_land = bool(_nullable_int_flag(payload.get("is_basic_land")))
        card_name = str_or_empty(payload.get("card_name")) or str_or_empty(payload.get("catalog_name"))
        card = {
            "name": card_name,
            "card_name": card_name,
            "set_code": str_or_empty(payload.get("set_code")),
            "collector_number": str_or_empty(payload.get("collector_number")),
            "finish": _nullable_int_flag(payload.get("finish")),
            "qty": max(1, _nullable_int_flag(payload.get("qty")) or 1),
            "section": str_or_empty(payload.get("section")) or "main",
            "cmc": resolve_card_cmc({
                "cmc": payload.get("cmc"),
                "mana_cost": payload.get("mana_cost"),
                "card_type": payload.get("card_type"),
                "is_basic_land": is_basic_land,
            }),
            "mana_cost": str_or_empty(payload.get("mana_cost")),
            "card_type": str_or_empty(payload.get("card_type")),
            "is_basic_land": is_basic_land,
            "type_line": str_or_empty(payload.get("type_line")),
            "oracle_text": str_or_empty(payload.get("oracle_text")),
            "image_uri": str_or_empty(payload.get("image_uri")),
            "color_identity": None if is_missing(payload.get("color_identity")) else payload.get("color_identity"),
        }
        cards.append(card)
        if card["section"] == "commander":
            commanders.append(card)
    return cards, commanders


def assess_deck_power_by_id(conn: sqlite3.Connection, deck_id: str) -> dict:
    try:
        deck_key = int(deck_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Deck not found") from exc

    deck_df = deck_scope(load_deck_cards_df(conn), deck_key)
    if deck_df.empty:
        return assess_deck_power([], commanders=[])

    if _deck_needs_metadata_backfill(deck_df):
        _backfill_deck_set_metadata(conn, deck_df)
        deck_df = deck_scope(load_deck_cards_df(conn), deck_key)

    cards, commanders = _cards_from_deck_df(deck_df)
    return assess_deck_power(cards, commanders=commanders)
