import json

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
    return getattr(row, field, None)


def card_metadata_snake(row) -> dict:
    colors_raw = _read_metadata_field(row, "colors")
    type_raw = _read_metadata_field(row, "type_line")
    card_type_raw = _read_metadata_field(row, "card_type")
    type_line = str_or_empty(type_raw)
    card_types = card_types_from_type_line(type_line)
    card_type = str_or_empty(card_type_raw) or primary_card_type(type_line)
    return {
        "colors": parse_card_colors(colors_raw),
        "type_line": type_line,
        "card_type": card_type,
        "card_types": card_types,
    }


def card_metadata_api(row) -> dict:
    meta = card_metadata_snake(row)
    return {
        "colors": meta["colors"],
        "typeLine": meta["type_line"],
        "cardType": meta["card_type"],
        "cardTypes": meta["card_types"],
    }
