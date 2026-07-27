from lib.config import EXCLUDED_SET_CODES

SET_SORT_ALPHABETICAL = "alphabetical"
SET_SORT_OWNED = "owned"
SET_SORT_CHRONOLOGICAL = "chronological"
SET_SORT_MODES = frozenset({
    SET_SORT_ALPHABETICAL,
    SET_SORT_OWNED,
    SET_SORT_CHRONOLOGICAL,
})


def normalize_set_sort_mode(value) -> str:
    mode = str(value or SET_SORT_ALPHABETICAL).strip().lower()
    if mode in SET_SORT_MODES:
        return mode
    return SET_SORT_ALPHABETICAL


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


def _sort_remaining_codes(
    set_codes: list[str],
    *,
    sort_mode: str,
    owned_counts: dict[str, int] | None,
    release_dates: dict[str, str] | None,
) -> list[str]:
    mode = normalize_set_sort_mode(sort_mode)
    if mode == SET_SORT_OWNED and owned_counts is not None:
        return sorted(
            set_codes,
            key=lambda code: (-owned_counts.get(code.upper(), 0), code.upper()),
        )
    if mode == SET_SORT_CHRONOLOGICAL and release_dates is not None:
        dated = [
            code for code in set_codes
            if (release_dates.get(code.upper(), "") or "").strip()
        ]
        undated = [
            code for code in set_codes
            if not (release_dates.get(code.upper(), "") or "").strip()
        ]
        # Stable: alpha first, then newest release first.
        dated_sorted = sorted(dated, key=lambda code: code.upper())
        dated_sorted = sorted(
            dated_sorted,
            key=lambda code: release_dates.get(code.upper(), ""),
            reverse=True,
        )
        undated_sorted = sorted(undated, key=lambda code: code.upper())
        return [*dated_sorted, *undated_sorted]
    return sorted(set_codes, key=lambda code: code.upper())


def sort_set_codes(
    set_codes: list[str],
    favorite_sets: list[str] | None = None,
    *,
    sort_mode: str = SET_SORT_ALPHABETICAL,
    owned_counts: dict[str, int] | None = None,
    release_dates: dict[str, str] | None = None,
) -> list[str]:
    if not set_codes:
        return []

    if not favorite_sets:
        return _sort_remaining_codes(
            set_codes,
            sort_mode=sort_mode,
            owned_counts=owned_counts,
            release_dates=release_dates,
        )

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
    ordered.extend(
        _sort_remaining_codes(
            remaining,
            sort_mode=sort_mode,
            owned_counts=owned_counts,
            release_dates=release_dates,
        )
    )
    return ordered
