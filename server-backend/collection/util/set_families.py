"""Build set families from Scryfall parent_set_code among known set codes."""

from __future__ import annotations

import sqlite3

from lib.config import normalize_set_code
from util.set_catalog import ensure_sets_columns, ensure_sets_table

CHILD_TYPE_PRIORITY = {
    "commander": 0,
    "token": 1,
    "promo": 2,
    "memorabilia": 3,
    "minigame": 4,
    "alchemy": 5,
}


def load_set_relations(conn: sqlite3.Connection) -> dict[str, dict]:
    """Return {SET_CODE: {set_type, parent_set_code}} for all catalog rows."""
    ensure_sets_table(conn)
    ensure_sets_columns(conn)
    rows = conn.execute(
        """
        SELECT set_code, set_type, parent_set_code
        FROM sets
        ORDER BY set_code
        """
    ).fetchall()
    relations: dict[str, dict] = {}
    for set_code, set_type, parent_set_code in rows:
        code = normalize_set_code(set_code)
        if not code:
            continue
        parent = normalize_set_code(parent_set_code) if parent_set_code else None
        relations[code] = {
            "set_type": (str(set_type).strip().lower() or None) if set_type else None,
            "parent_set_code": parent,
        }
    return relations


def effective_family_root(set_code: str, relations: dict[str, dict], known: set[str]) -> str:
    """
    Root used for grouping among known codes.

    If the Scryfall parent is itself known, use it; otherwise the set stands alone
    (orphan child whose parent is not tracked).
    """
    code = normalize_set_code(set_code)
    if not code:
        return ""
    parent = (relations.get(code) or {}).get("parent_set_code")
    if parent and parent in known:
        return parent
    return code


def family_members_for_root(
    root_code: str,
    known_codes: list[str] | set[str],
    relations: dict[str, dict],
) -> list[str]:
    known = {normalize_set_code(code) for code in known_codes if normalize_set_code(code)}
    root = normalize_set_code(root_code)
    if not root or root not in known:
        return []
    members = [
        code
        for code in known
        if effective_family_root(code, relations, known) == root
    ]
    return sort_family_members(members, relations, root=root)


def sort_family_members(
    members: list[str],
    relations: dict[str, dict],
    *,
    root: str,
) -> list[str]:
    root_upper = normalize_set_code(root)

    def sort_key(code: str) -> tuple:
        if code == root_upper:
            return (0, -1, code)
        set_type = (relations.get(code) or {}).get("set_type") or ""
        priority = CHILD_TYPE_PRIORITY.get(set_type, 99)
        return (1, priority, code)

    return sorted(members, key=sort_key)


def build_family_index(
    known_codes: list[str] | set[str],
    relations: dict[str, dict],
) -> dict[str, list[str]]:
    """Map each effective root to its sorted member list (only multi-member families needed by callers)."""
    known = sorted(
        {normalize_set_code(code) for code in known_codes if normalize_set_code(code)}
    )
    by_root: dict[str, list[str]] = {}
    for code in known:
        root = effective_family_root(code, relations, set(known))
        by_root.setdefault(root, []).append(code)
    return {
        root: sort_family_members(members, relations, root=root)
        for root, members in by_root.items()
    }


def resolve_set_codes_for_scope(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    family: bool = False,
    known_codes: list[str] | set[str] | None = None,
) -> list[str]:
    """
    Resolve a set scope to concrete set codes.

    When family is True, expand to all known family members under the effective root
    of set_code. When family is False, return the single normalized code.
    """
    normalized = (set_code or "All").strip()
    if normalized.upper() == "ALL":
        return []

    code = normalize_set_code(normalized)
    if not code:
        return []
    if not family:
        return [code]

    relations = load_set_relations(conn)
    if known_codes is None:
        known_codes = _known_set_codes_from_db(conn)
    known = {normalize_set_code(item) for item in known_codes if normalize_set_code(item)}
    if code not in known:
        known.add(code)
    root = effective_family_root(code, relations, known)
    members = family_members_for_root(root, known, relations)
    return members or [code]


def _known_set_codes_from_db(conn: sqlite3.Connection) -> list[str]:
    from util.deck_tables import list_deck_sync_set_codes
    from util.tracked_sets import list_tracked_set_codes

    codes: set[str] = set()
    for raw in list_tracked_set_codes(conn):
        code = normalize_set_code(raw)
        if code:
            codes.add(code)
    for raw in list_deck_sync_set_codes(conn):
        code = normalize_set_code(raw)
        if code:
            codes.add(code)
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cards' LIMIT 1"
    ).fetchone():
        for (raw,) in conn.execute("SELECT DISTINCT set_code FROM cards"):
            code = normalize_set_code(raw)
            if code:
                codes.add(code)
    return sorted(codes)


def ordered_set_codes_by_family(
    set_codes: list[str],
    relations: dict[str, dict],
    *,
    sorted_roots: list[str],
) -> list[str]:
    """Flatten sorted roots with nested children for picker order."""
    known = {normalize_set_code(code) for code in set_codes if normalize_set_code(code)}
    families = build_family_index(known, relations)
    ordered: list[str] = []
    seen: set[str] = set()
    for root in sorted_roots:
        root_code = normalize_set_code(root)
        if not root_code or root_code in seen:
            continue
        members = families.get(root_code) or [root_code]
        for member in members:
            if member in seen:
                continue
            ordered.append(member)
            seen.add(member)
    for code in sorted(known):
        if code not in seen:
            ordered.append(code)
            seen.add(code)
    return ordered


def relations_from_scryfall_sets(scryfall_sets: list[dict]) -> dict[str, dict]:
    """Build {CODE: {set_type, parent_set_code}} from Scryfall /sets payloads."""
    relations: dict[str, dict] = {}
    for item in scryfall_sets or []:
        code = normalize_set_code(item.get("code"))
        if not code:
            continue
        parent = normalize_set_code(item.get("parent_set_code")) if item.get("parent_set_code") else None
        relations[code] = {
            "set_type": (str(item.get("set_type") or "").strip().lower() or None),
            "parent_set_code": parent,
        }
    return relations


def scryfall_family_root(set_code: str, relations: dict[str, dict]) -> str:
    """Absolute Scryfall parent chain root (parent need not be in a local known set)."""
    code = normalize_set_code(set_code)
    if not code:
        return ""
    seen: set[str] = set()
    current = code
    while current and current not in seen:
        seen.add(current)
        parent = (relations.get(current) or {}).get("parent_set_code")
        if not parent:
            return current
        current = parent
    return code


def scryfall_family_members(
    set_code: str,
    scryfall_sets: list[dict] | None = None,
    *,
    relations: dict[str, dict] | None = None,
) -> list[str]:
    """
    All Scryfall set codes in the same family as set_code (root + children).

    Uses full Scryfall parent links, not only locally tracked codes.
    """
    code = normalize_set_code(set_code)
    if not code:
        return []
    rel = relations if relations is not None else relations_from_scryfall_sets(scryfall_sets or [])
    if code not in rel and scryfall_sets is None:
        return [code]
    if code not in rel:
        rel = {**rel, code: {"set_type": None, "parent_set_code": None}}
    root = scryfall_family_root(code, rel)
    all_codes = set(rel.keys()) | {code, root}
    members = [
        member
        for member in all_codes
        if scryfall_family_root(member, rel) == root
    ]
    return sort_family_members(members, rel, root=root)
