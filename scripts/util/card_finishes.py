"""Card finish identifiers aligned with Scryfall ``finishes`` values."""

from __future__ import annotations

FINISH_NONFOIL = 0
FINISH_FOIL = 1
FINISH_ETCHED = 2

FINISH_IDS = frozenset({FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED})

FINISH_LABELS = {
    FINISH_NONFOIL: "Non-foil",
    FINISH_FOIL: "Foil",
    FINISH_ETCHED: "Etched",
}

FINISH_SCRYFALL = {
    FINISH_NONFOIL: "nonfoil",
    FINISH_FOIL: "foil",
    FINISH_ETCHED: "etched",
}

SCRYFALL_TO_FINISH = {value: key for key, value in FINISH_SCRYFALL.items()}

HAS_FINISH_COLUMNS = {
    FINISH_NONFOIL: "has_nonfoil",
    FINISH_FOIL: "has_foil",
    FINISH_ETCHED: "has_etched",
}

MARKET_VALUE_COLUMNS = {
    FINISH_NONFOIL: "market_value",
    FINISH_FOIL: "market_value_foil",
    FINISH_ETCHED: "market_value_etched",
}

GUIDE_PRICE_GROUPS = {
    FINISH_NONFOIL: "nonfoil",
    FINISH_FOIL: "foil",
    FINISH_ETCHED: "etched",
}


def finish_label(finish: int | str | None) -> str:
    try:
        finish_id = int(finish)
    except (TypeError, ValueError):
        return "Unknown"
    return FINISH_LABELS.get(finish_id, "Unknown")


def normalize_finish(value, *, default: int = FINISH_NONFOIL) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return FINISH_FOIL if value else FINISH_NONFOIL
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        finish_id = int(value)
        if finish_id in FINISH_IDS:
            return finish_id
    text = str(value).strip().lower()
    if not text:
        return default
    if text in SCRYFALL_TO_FINISH:
        return SCRYFALL_TO_FINISH[text]
    if text in {"0", "false", "no", "n", "nonfoil", "non-foil"}:
        return FINISH_NONFOIL
    if text in {"1", "true", "yes", "y", "foil"}:
        return FINISH_FOIL
    if text in {"2", "etched", "etchedfoil", "etched-foil"}:
        return FINISH_ETCHED
    return default


def parse_finish_from_row(row: dict, *, default: int = FINISH_NONFOIL) -> int:
    raw_finish = row.get("finish")
    if raw_finish not in (None, ""):
        return normalize_finish(raw_finish, default=default)
    if "foil" in row:
        return normalize_finish(row.get("foil"), default=default)
    return default


def card_finish_flags(card: dict) -> tuple[int, int, int]:
    finishes = card.get("finishes") or []
    return (
        1 if "nonfoil" in finishes else 0,
        1 if "foil" in finishes else 0,
        1 if "etched" in finishes else 0,
    )


def scryfall_finishes(card: dict) -> list[int]:
    finishes = card.get("finishes") or []
    return [
        SCRYFALL_TO_FINISH[name]
        for name in ("nonfoil", "foil", "etched")
        if name in finishes
    ]


def has_finish_flag(row, finish: int) -> bool:
    column = HAS_FINISH_COLUMNS[finish]
    raw = row[column] if isinstance(row, dict) else row[column]
    if raw is None:
        return False
    try:
        return bool(int(raw))
    except (TypeError, ValueError):
        return False


def finish_available(row, finish: int, *, owned: bool = False) -> bool:
    if owned:
        return True
    finish_id = normalize_finish(finish)
    column = HAS_FINISH_COLUMNS[finish_id]
    raw = row[column] if isinstance(row, dict) else row[column]
    if raw is not None and raw != "":
        try:
            return bool(int(raw))
        except (TypeError, ValueError):
            return False
    value = market_value_for_finish(row, finish_id)
    if value is None or value == "":
        return False
    try:
        return not (isinstance(value, float) and value != value)
    except TypeError:
        return True


def market_value_for_finish(row, finish: int):
    column = MARKET_VALUE_COLUMNS[finish]
    return row[column] if isinstance(row, dict) else row[column]


def infer_finish_for_print(
    finish: int,
    *,
    has_nonfoil: int | None,
    has_foil: int | None,
    has_etched: int | None,
) -> int:
    finish_id = normalize_finish(finish)
    flags = {
        FINISH_NONFOIL: bool(has_nonfoil),
        FINISH_FOIL: bool(has_foil),
        FINISH_ETCHED: bool(has_etched),
    }
    if flags.get(finish_id):
        return finish_id
    available = [candidate for candidate, enabled in flags.items() if enabled]
    if len(available) == 1:
        return available[0]
    if finish_id == FINISH_FOIL and flags[FINISH_ETCHED] and not flags[FINISH_FOIL]:
        return FINISH_ETCHED
    if finish_id == FINISH_NONFOIL and flags[FINISH_ETCHED] and not flags[FINISH_NONFOIL]:
        return FINISH_ETCHED
    return finish_id


def card_price_key(set_code: str, collector_number: str, finish) -> str:
    finish_id = normalize_finish(finish)
    return f"{set_code.upper()}|{collector_number}|{finish_id}"


def guide_uses_foil_keys(finish: int) -> bool:
    return normalize_finish(finish) == FINISH_FOIL
