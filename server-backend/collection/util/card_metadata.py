import json
import re

import pandas as pd

from report.serialize_helpers import str_or_empty

WUBRG_ORDER = "WUBRG"

CARD_TYPES = frozenset({
    "artifact",
    "battle",
    "conspiracy",
    "creature",
    "enchantment",
    "instant",
    "kindred",
    "land",
    "phenomenon",
    "plane",
    "planeswalker",
    "scheme",
    "sorcery",
    "tribal",
    "vanguard",
})

TYPE_PRIORITY = (
    "land",
    "battle",
    "planeswalker",
    "creature",
    "enchantment",
    "artifact",
    "instant",
    "sorcery",
    "kindred",
    "tribal",
    "conspiracy",
    "phenomenon",
    "plane",
    "scheme",
    "vanguard",
)

COLLECTION_FILTER_TYPES = frozenset({
    "creature",
    "planeswalker",
    "enchantment",
    "artifact",
    "instant",
    "sorcery",
    "land",
    "battle",
    "kindred",
    "tribal",
})

COLLECTION_RARITY_FILTERS = frozenset({
    "common",
    "uncommon",
    "rare",
    "mythic",
    "special",
    "bonus",
})

COLLECTION_TYPE_GROUPS = COLLECTION_FILTER_TYPES | {"others"}

COLLECTION_COLOR_FILTERS = frozenset({"W", "U", "B", "R", "G", "C"})


def normalize_card_colors(colors: list[str] | tuple[str, ...]) -> list[str]:
    unique = {str(color).upper() for color in colors if color}
    return sorted(
        unique,
        key=lambda color: WUBRG_ORDER.index(color) if color in WUBRG_ORDER else 99,
    )


def collection_type_group(card_type: str) -> str:
    normalized = str(card_type or "").lower()
    if normalized in COLLECTION_TYPE_GROUPS - {"others"}:
        return normalized
    return "others"


def parse_collection_color_filters(colors: str | None) -> list[str]:
    if not colors:
        return []
    return [
        part
        for part in str(colors).upper().split(",")
        if part in COLLECTION_COLOR_FILTERS
    ]


def card_matches_collection_type_filter(card: dict, type_filter: str) -> bool:
    if not type_filter or type_filter == "all":
        return True
    card_type = str(card.get("cardType") or card.get("card_type") or "").lower()
    return card_type == str(type_filter).strip().lower()


def card_matches_collection_color_filter(card: dict, color_filters: list[str]) -> bool:
    if not color_filters:
        return True
    colors = card.get("colors") or []
    if "C" in color_filters and not colors:
        return True
    return any(color in colors for color in color_filters if color != "C")


def _card_field(card: dict, *keys: str):
    for key in keys:
        if key in card and card.get(key) not in (None, ""):
            return card.get(key)
    return None


def _parse_numeric_stat(value) -> float | None:
    text = str(value or "").strip()
    if not text or text == "*":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def card_matches_collection_rarity_filter(card: dict, rarity_filter: str) -> bool:
    if not rarity_filter or rarity_filter == "all":
        return True
    rarity = str(_card_field(card, "rarity", "Rarity") or "").lower()
    return rarity == str(rarity_filter).strip().lower()


def card_matches_collection_cmc_filter(
    card: dict,
    *,
    cmc_min: float | None = None,
    cmc_max: float | None = None,
) -> bool:
    cmc = resolve_card_cmc(card)
    if cmc_min is not None and cmc < cmc_min:
        return False
    if cmc_max is not None and cmc > cmc_max:
        return False
    return True


def card_matches_collection_price_filter(
    card: dict,
    *,
    price_min: float | None = None,
    price_max: float | None = None,
) -> bool:
    if price_min is None and price_max is None:
        return True
    raw = card.get("currentValue")
    if raw is None:
        raw = card.get("current_value")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return False
    if price_min is not None and value < price_min:
        return False
    if price_max is not None and value > price_max:
        return False
    return True


def card_matches_collection_stat_filter(
    card: dict,
    *,
    power_min: float | None = None,
    toughness_min: float | None = None,
) -> bool:
    if power_min is None and toughness_min is None:
        return True
    power = _parse_numeric_stat(_card_field(card, "power", "Power"))
    toughness = _parse_numeric_stat(_card_field(card, "toughness", "Toughness"))
    if power_min is not None and (power is None or power < power_min):
        return False
    if toughness_min is not None and (toughness is None or toughness < toughness_min):
        return False
    return True


def card_matches_collection_storage_filter(card: dict, storage_filters: list[str]) -> bool:
    if not storage_filters:
        return True
    locations = card.get("locations") or []
    card_slugs = {
        str(location.get("slug") or "").strip()
        for location in locations
        if location.get("slug")
    }
    if not card_slugs:
        return False
    return any(slug in card_slugs for slug in storage_filters)


def encode_card_colors(colors: list[str]) -> str:
    return json.dumps(normalize_card_colors(colors), separators=(",", ":"))


def parse_card_colors(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return normalize_card_colors(raw)
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return normalize_card_colors(parsed)
    except json.JSONDecodeError:
        pass
    return normalize_card_colors(part.strip() for part in text.split(",") if part.strip())


def parse_card_legalities(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def card_matches_color_identity(card_identity: list[str], allowed_identity: list[str]) -> bool:
    if not card_identity:
        return True
    allowed = set(allowed_identity or [])
    return all(color in allowed for color in card_identity)


def is_commander_format_legal(legalities: dict) -> bool:
    status = str((legalities or {}).get("commander") or "").lower()
    return status in {"legal", "restricted"}


def is_legendary_commander_candidate(type_line: str) -> bool:
    normalized = str(type_line or "").lower()
    if "legendary" not in normalized:
        return False
    return "creature" in normalized or "planeswalker" in normalized


def cmc_from_mana_cost(mana_cost: str) -> float:
    if not str(mana_cost or "").strip():
        return 0.0
    total = 0.0
    for face in str(mana_cost).split("//"):
        for symbol in re.findall(r"\{([^}]+)\}", face):
            token = symbol.strip().upper()
            if token in {"X", "Y", "Z"}:
                continue
            if token.isdigit():
                total += float(token)
                continue
            if "/" in token:
                total += 1.0
                continue
            try:
                total += float(token)
            except ValueError:
                total += 1.0
    return total


def card_row_needs_power_metadata(
    row,
    *,
    section_key: str = "section",
    in_catalog_key: str = "in_catalog",
) -> bool:
    """True when a main-deck catalog card still lacks CMC/mana data worth fetching from Scryfall."""
    if str(row.get(section_key) or "main") != "main":
        return False
    if not int(row.get(in_catalog_key) or 0):
        return False
    is_basic_land = row.get("is_basic_land")
    if is_basic_land is not None and not (isinstance(is_basic_land, float) and pd.isna(is_basic_land)):
        if int(is_basic_land):
            return False
    card_type = row.get("card_type")
    if card_type is None or (isinstance(card_type, float) and pd.isna(card_type)):
        card_type = ""
    else:
        card_type = str(card_type).lower()
    if card_type == "land":
        return False
    type_line = row.get("type_line")
    if type_line is None or (isinstance(type_line, float) and pd.isna(type_line)):
        type_line = ""
    else:
        type_line = str(type_line)
    if not card_type and type_line and primary_card_type(type_line) == "land":
        return False
    cmc = row.get("cmc")
    if cmc is not None and not pd.isna(cmc):
        try:
            if float(cmc) > 0:
                return False
        except (TypeError, ValueError):
            pass
    mana_cost = row.get("mana_cost")
    if mana_cost is None or (isinstance(mana_cost, float) and pd.isna(mana_cost)):
        return True
    return not str(mana_cost).strip()


def resolve_card_cmc(card: dict) -> float:
    raw = card.get("cmc")
    if raw is not None and str(raw).strip():
        try:
            value = float(raw)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    mana_cost = card.get("mana_cost") or card.get("manaCost") or ""
    parsed = cmc_from_mana_cost(str(mana_cost))
    if parsed > 0:
        return parsed
    card_type = str(card.get("card_type") or card.get("cardType") or "").lower()
    if card_type == "land" or bool(card.get("is_basic_land") or card.get("isBasicLand")):
        return 0.0
    return 0.0


def card_types_from_type_line(type_line: str) -> list[str]:
    if not type_line:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for face in str(type_line).split("//"):
        segment = face.split("—", 1)[0]
        for token in segment.split():
            lower = token.lower().rstrip(",")
            if lower in CARD_TYPES and lower not in seen:
                seen.add(lower)
                found.append(lower)
    return found


def primary_card_type(type_line: str) -> str:
    types = set(card_types_from_type_line(type_line))
    if not types:
        return ""
    for candidate in TYPE_PRIORITY:
        if candidate in types:
            return candidate
    return sorted(types)[0]


def _read_metadata_field(row, field: str):
    if isinstance(row, dict):
        return row.get(field)
    if isinstance(row, pd.Series):
        return row[field] if field in row.index else None
    # sqlite3.Row and similar mapping rows support key access, not attribute access.
    try:
        return row[field]
    except (KeyError, IndexError, TypeError):
        pass
    return getattr(row, field, None)


def _nullable_int_flag(value) -> int:
    if value is None:
        return 0
    if isinstance(value, float) and pd.isna(value):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _nullable_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def card_metadata_snake(row) -> dict:
    colors_raw = _read_metadata_field(row, "colors")
    identity_raw = _read_metadata_field(row, "color_identity")
    type_raw = _read_metadata_field(row, "type_line")
    card_type_raw = _read_metadata_field(row, "card_type")
    oracle_raw = _read_metadata_field(row, "oracle_text")
    mana_cost_raw = _read_metadata_field(row, "mana_cost")
    cmc_raw = _read_metadata_field(row, "cmc")
    legalities_raw = _read_metadata_field(row, "legalities")
    basic_land_raw = _read_metadata_field(row, "is_basic_land")
    power_raw = _read_metadata_field(row, "power")
    toughness_raw = _read_metadata_field(row, "toughness")
    rarity_raw = _read_metadata_field(row, "rarity")
    type_line = str_or_empty(type_raw)
    card_types = card_types_from_type_line(type_line)
    card_type = str_or_empty(card_type_raw) or primary_card_type(type_line)
    cmc = _nullable_float(cmc_raw)
    return {
        "colors": parse_card_colors(colors_raw),
        "color_identity": parse_card_colors(identity_raw),
        "type_line": type_line,
        "card_type": card_type,
        "card_types": card_types,
        "oracle_text": str_or_empty(oracle_raw),
        "mana_cost": str_or_empty(mana_cost_raw),
        "cmc": cmc,
        "legalities": parse_card_legalities(legalities_raw),
        "is_basic_land": bool(_nullable_int_flag(basic_land_raw)),
        "power": str_or_empty(power_raw) or None,
        "toughness": str_or_empty(toughness_raw) or None,
        "rarity": str_or_empty(rarity_raw).lower() or None,
    }


def card_metadata_api(row) -> dict:
    meta = card_metadata_snake(row)
    return {
        "colors": meta["colors"],
        "colorIdentity": meta["color_identity"],
        "typeLine": meta["type_line"],
        "cardType": meta["card_type"],
        "cardTypes": meta["card_types"],
        "oracleText": meta["oracle_text"],
        "manaCost": meta["mana_cost"],
        "cmc": meta["cmc"],
        "legalities": meta["legalities"],
        "isBasicLand": meta["is_basic_land"],
        "power": meta["power"],
        "toughness": meta["toughness"],
        "rarity": meta["rarity"],
    }


def card_image_fields(row) -> dict:
    return {
        "imageUri": str_or_empty(_read_metadata_field(row, "image_uri")),
        "imageUriBack": str_or_empty(_read_metadata_field(row, "image_uri_back")),
    }
