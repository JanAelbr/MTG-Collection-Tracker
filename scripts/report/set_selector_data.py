import sqlite3
from dataclasses import dataclass

from lib.config import DB_PATH, HTTP_USER_AGENT
from lib.deck_csv import list_deck_sync_set_codes
from lib.run_log import get_logger
from util.set_catalog import (
    ensure_sets_table,
    prune_unowned_sets,
    sync_catalog_set_metadata,
)

SCRYFALL_HEADERS = {"User-Agent": HTTP_USER_AGENT}
DECK_SETS_SEPARATOR_LABEL = "────────── Deck sets ──────────"

log = get_logger(__name__)
@dataclass(frozen=True)
class SetSelectorEntry:
    value: str
    label: str
    disabled: bool = False
    separator: bool = False


_set_selector_entries_cache: dict[bool, list[SetSelectorEntry]] | None = None


# Count owned finishes grouped by set code.
def load_owned_count_by_set(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT set_code, COUNT(*) AS owned_count
        FROM purchases
        GROUP BY set_code
        """
    ).fetchall()
    return {set_code.upper(): int(count) for set_code, count in rows}


# Format one set option label, optionally including owned count.
def format_set_selector_label(
    set_code: str,
    name: str,
    owned_count: int | None = None,
) -> str:
    label = f"{name} ({set_code})"
    if owned_count is not None and owned_count > 0:
        return f"{label} · {owned_count}"
    return label


# Build ordered set selector entries for owned and deck-list sets.
def build_set_selector_entries(
    conn: sqlite3.Connection,
    include_all: bool = True,
) -> list[SetSelectorEntry]:
    ensure_sets_table(conn)
    owned_counts = load_owned_count_by_set(conn)
    deck_codes = set(list_deck_sync_set_codes())
    catalog_codes = set(owned_counts.keys()) | deck_codes

    if not catalog_codes:
        return [SetSelectorEntry(value="All", label="All")] if include_all else []

    placeholders = ",".join("?" for _ in catalog_codes)
    rows = conn.execute(
        f"""
        SELECT set_code, name, released_at
        FROM sets
        WHERE set_code IN ({placeholders})
        """,
        tuple(catalog_codes),
    ).fetchall()
    known_names = {set_code.upper(): name for set_code, name, _released_at in rows}

    owned_entries: list[tuple[str, str, str, int]] = []
    deck_only_entries: list[tuple[str, str, str]] = []

    for set_code in catalog_codes:
        name = known_names.get(set_code, set_code)
        released_at = next(
            (released or "" for code, _, released in rows if code.upper() == set_code),
            "",
        )
        owned_count = owned_counts.get(set_code, 0)
        if owned_count > 0:
            owned_entries.append((set_code, name, released_at, owned_count))
        elif set_code in deck_codes:
            deck_only_entries.append((set_code, name, released_at))

    owned_entries.sort(
        key=lambda item: (-item[3], item[2], item[1].casefold(), item[0]),
    )
    deck_only_entries.sort(
        key=lambda item: (item[2], item[1].casefold(), item[0]),
    )

    entries: list[SetSelectorEntry] = []
    if include_all:
        entries.append(SetSelectorEntry(value="All", label="All"))

    for set_code, name, _released_at, owned_count in owned_entries:
        entries.append(
            SetSelectorEntry(
                value=set_code,
                label=format_set_selector_label(set_code, name, owned_count),
            )
        )

    if owned_entries and deck_only_entries:
        entries.append(
            SetSelectorEntry(
                value="",
                label=DECK_SETS_SEPARATOR_LABEL,
                disabled=True,
                separator=True,
            )
        )

    for set_code, name, _released_at in deck_only_entries:
        entries.append(
            SetSelectorEntry(
                value=set_code,
                label=format_set_selector_label(set_code, name),
            )
        )

    return entries


# Refresh catalog metadata from Scryfall and drop unrelated set rows.
def refresh_owned_set_catalog() -> int:
    global _set_selector_entries_cache
    with sqlite3.connect(DB_PATH) as conn:
        synced = sync_catalog_set_metadata(conn, SCRYFALL_HEADERS)
        pruned = prune_unowned_sets(conn)
        conn.commit()
    _set_selector_entries_cache = None
    if synced:
        log.info("Synced %s catalog set(s) from Scryfall", synced)
    if pruned:
        log.info("Removed %s untracked set(s) from catalog", pruned)
    if not synced and not pruned:
        log.info("Set catalog already up to date")
    return synced


# Load ordered set selector entries for owned and deck-list sets.
def get_set_selector_entries(
    include_all: bool = True,
    refresh_catalog: bool = False,
) -> list[SetSelectorEntry]:
    global _set_selector_entries_cache
    if refresh_catalog:
        refresh_owned_set_catalog()

    if _set_selector_entries_cache is not None and include_all in _set_selector_entries_cache:
        return _set_selector_entries_cache[include_all]

    with sqlite3.connect(DB_PATH) as conn:
        entries = build_set_selector_entries(conn, include_all=include_all)

    if _set_selector_entries_cache is None:
        _set_selector_entries_cache = {}
    _set_selector_entries_cache[include_all] = entries
    return entries


# Return selectable set codes from ordered selector entries.
def get_set_selector_codes(include_all: bool = True) -> list[str]:
    codes = []
    for entry in get_set_selector_entries(include_all=include_all):
        if entry.separator or entry.disabled or not entry.value:
            continue
        codes.append(entry.value)
    return codes
