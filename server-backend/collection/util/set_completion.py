"""Collector-number rules for set completion counts."""

from collections.abc import Iterable

from lib.art_styles import normalize_collector_number
from util.alchemy_cards import is_alchemy_art_style, is_alchemy_collector_number


def is_serialized_collector_number(collector_number: str) -> bool:
    return str(collector_number).strip().upper().endswith("Z")


def completion_collector_key(collector_number: str) -> str | None:
    """Return the base collector slot for completion, or None when excluded."""
    if is_alchemy_collector_number(collector_number):
        return None
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
    rows: Iterable[tuple[str, str, str]],
    *,
    set_code: str | None = None,
) -> dict[str, int]:
    keys_by_style: dict[str, set[str]] = {}
    normalized_set = str(set_code).upper() if set_code else None
    for raw_set_code, collector_number, art_style in rows:
        if is_alchemy_art_style(art_style):
            continue
        if normalized_set and str(raw_set_code).upper() != normalized_set:
            continue
        slot = completion_collector_key(collector_number)
        if slot is None:
            continue
        style = str(art_style or "").strip() or "Unknown"
        keys_by_style.setdefault(style, set()).add(slot)
    return {style: len(slots) for style, slots in keys_by_style.items()}


def count_completion_keys_by_rarity(
    rows: Iterable[tuple[str, str, str | None]],
    *,
    set_code: str | None = None,
) -> dict[str, int]:
    """Count unique completion slots per rarity (first-seen rarity wins per slot)."""
    slot_rarity: dict[str | tuple[str, str], str] = {}
    normalized_set = str(set_code).upper() if set_code else None
    for raw_set_code, collector_number, rarity in rows:
        set_key = str(raw_set_code).upper()
        if normalized_set and set_key != normalized_set:
            continue
        slot = completion_collector_key(collector_number)
        if slot is None:
            continue
        rarity_key = str(rarity or "").strip().lower() or "unknown"
        key = slot if normalized_set else (set_key, slot)
        if key in slot_rarity:
            continue
        slot_rarity[key] = rarity_key

    counts: dict[str, int] = {}
    for rarity_key in slot_rarity.values():
        counts[rarity_key] = counts.get(rarity_key, 0) + 1
    return counts
