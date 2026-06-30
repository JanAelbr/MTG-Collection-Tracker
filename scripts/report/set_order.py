from lib.config import EXCLUDED_SET_CODES

SET_SORT_ALPHABETICAL = "alphabetical"
SET_SORT_OWNED = "owned"
SET_SORT_MODES = frozenset({SET_SORT_ALPHABETICAL, SET_SORT_OWNED})

SET_PICKER_DROPDOWN = "dropdown"
SET_PICKER_BROWSER = "browser"
SET_PICKER_MODES = frozenset({SET_PICKER_DROPDOWN, SET_PICKER_BROWSER})


def normalize_set_sort_mode(value) -> str:
    mode = str(value or SET_SORT_ALPHABETICAL).strip().lower()
    if mode in SET_SORT_MODES:
        return mode
    return SET_SORT_ALPHABETICAL


def normalize_set_picker_mode(value) -> str:
    mode = str(value or SET_PICKER_DROPDOWN).strip().lower()
    if mode in SET_PICKER_MODES:
        return mode
    return SET_PICKER_DROPDOWN


def normalize_favorite_sets(
    values: list[str] | None,
    *,
    valid_codes: set[str] | None = None,
) -> list[str]:
    if not values:
        return []

    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        code = str(raw).strip().upper()
        if not code or code in EXCLUDED_SET_CODES or not code.isalnum():
            continue
        if valid_codes is not None and code not in valid_codes:
            continue
        if code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    return ordered


def sort_set_codes(
    set_codes: list[str],
    favorite_sets: list[str] | None = None,
    *,
    sort_mode: str = SET_SORT_ALPHABETICAL,
    owned_counts: dict[str, int] | None = None,
) -> list[str]:
    if not set_codes:
        return []

    mode = normalize_set_sort_mode(sort_mode)

    def remaining_sort_key(code: str):
        if mode == SET_SORT_OWNED and owned_counts is not None:
            return (-owned_counts.get(code.upper(), 0), code.upper())
        return (code.upper(),)

    if not favorite_sets:
        return sorted(set_codes, key=remaining_sort_key)

    by_upper = {code.upper(): code for code in set_codes}
    ordered: list[str] = []
    seen: set[str] = set()
    for favorite in favorite_sets:
        code = by_upper.get(str(favorite).strip().upper())
        if code is None or code.upper() in seen:
            continue
        ordered.append(code)
        seen.add(code.upper())

    remaining = [code for code in set_codes if code.upper() not in seen]
    ordered.extend(sorted(remaining, key=remaining_sort_key))
    return ordered
