"""Collector-number rules for set completion counts."""

from collections.abc import Iterable

from lib.art_styles import normalize_collector_number


def is_serialized_collector_number(collector_number: str) -> bool:
    return str(collector_number).strip().upper().endswith("Z")


def completion_collector_key(collector_number: str) -> str | None:
    """Return the base collector slot for completion, or None when excluded."""
    if is_serialized_collector_number(collector_number):
        return None
    number = normalize_collector_number(collector_number)
    if number is None:
        return None
    return str(number)


def count_completion_keys(
    rows: Iterable[tuple[str, str]],
    *,
    set_code: str | None = None,
) -> int:
    keys: set[str] | set[tuple[str, str]] = set()
    normalized_set = str(set_code).upper() if set_code else None
    for raw_set_code, collector_number in rows:
        set_key = str(raw_set_code).upper()
        if normalized_set and set_key != normalized_set:
            continue
        slot = completion_collector_key(collector_number)
        if slot is None:
            continue
        if normalized_set:
            keys.add(slot)
        else:
            keys.add((set_key, slot))
    return len(keys)


def count_completion_keys_by_set(rows: Iterable[tuple[str, str]]) -> dict[str, int]:
    keys_by_set: dict[str, set[str]] = {}
    for raw_set_code, collector_number in rows:
        set_key = str(raw_set_code).upper()
        slot = completion_collector_key(collector_number)
        if slot is None:
            continue
        keys_by_set.setdefault(set_key, set()).add(slot)
    return {set_code: len(slots) for set_code, slots in keys_by_set.items()}


def count_completion_keys_by_art_style(
    rows: Iterable[tuple[str, str]],
    *,
    set_code: str | None = None,
) -> dict[str, int]:
    keys_by_style: dict[str, set[str]] = {}
    normalized_set = str(set_code).upper() if set_code else None
    for raw_set_code, collector_number, art_style in rows:
        if normalized_set and str(raw_set_code).upper() != normalized_set:
            continue
        slot = completion_collector_key(collector_number)
        if slot is None:
            continue
        style = str(art_style or "").strip() or "Unknown"
        keys_by_style.setdefault(style, set()).add(slot)
    return {style: len(slots) for style, slots in keys_by_style.items()}
