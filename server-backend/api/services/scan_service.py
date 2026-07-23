"""Scan ingest: resolve a print by name+set (preferred) or set+number."""

from __future__ import annotations

import re
import sqlite3

from api.cache import bump_cache_epoch
from api.services.manager_service import ManagerError, adjust_copy_count, get_copy_state
from lib.config import EXCLUDED_SET_CODES, normalize_set_code
from lib.run_log import get_logger
from util.alchemy_cards import (
    exclude_alchemy_art_style_sql,
    exclude_alchemy_sql,
    is_alchemy_collector_number,
)
from util.card_finishes import FINISH_FOIL, FINISH_NONFOIL, infer_finish_for_print
from util.db_migrate import ensure_card_columns
from util.scryfall_catalog_sync import import_set_catalog_from_scryfall
from util.tracked_sets import add_tracked_set, is_set_tracked, remove_tracked_set

log = get_logger(__name__)

_TITLE_STOP = frozenset({"A", "AN", "THE", "OF", "AND", "OR", "TO", "IN", "ON", "FOR"})
_NON_ALNUM = re.compile(r"[^A-Z0-9'\- ]+")
_EDGE_NOISE = re.compile(r"^[\s.·•\-_:;,\"'`]+|[\s.·•\-_:;,\"'`]+$")
_MANA_COST_TOKEN = re.compile(
    r"^(?:[0-9]{1,2}|[Xx]|[WUBRGCS]{1,5}|[0-9]{1,2}[WUBRGCS]{1,5}|[WUBRGC]P)$",
    re.IGNORECASE,
)
_GLUED_MANA = re.compile(
    r"^([A-Za-z][A-Za-z'-]*[A-Za-z])"
    r"([0-9][0-9XxWUBRGCSwubrgcs]{0,5}|[Xx][0-9WUBRGCSwubrgcs]{0,5}|[Il][WUBRGCSwubrgcs]{1,5})$"
)


class ScanError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _normalize_mana_ocr_token(token: str) -> str:
    text = str(token or "")
    for ch in "{} /·•.":
        text = text.replace(ch, "")
    text = text.replace("I", "1").replace("l", "1").replace("|", "1")
    text = text.replace("O", "0").replace("o", "0")
    return text.strip()


def is_mana_cost_token(token: str | None) -> bool:
    raw = str(token or "").strip()
    if not raw or len(raw) > 6:
        return False
    normalized = _normalize_mana_ocr_token(raw)
    return bool(_MANA_COST_TOKEN.match(normalized) or _MANA_COST_TOKEN.match(raw))


def strip_trailing_mana_cost(raw: str | None) -> str:
    text = " ".join(str(raw or "").split())
    if not text:
        return ""
    text = re.sub(r"(\s*\{[^}]+\})+\s*$", "", text).strip()
    text = _EDGE_NOISE.sub("", text)
    # Also peel leftover edge punctuation from each end token.
    parts = [part for part in text.split(" ") if part]
    while parts and _EDGE_NOISE.sub("", parts[0]) != parts[0]:
        parts[0] = _EDGE_NOISE.sub("", parts[0])
        if not parts[0]:
            parts.pop(0)
    while parts and _EDGE_NOISE.sub("", parts[-1]) != parts[-1]:
        parts[-1] = _EDGE_NOISE.sub("", parts[-1])
        if not parts[-1]:
            parts.pop()
    while len(parts) > 1 and is_mana_cost_token(parts[-1]):
        parts.pop()
    if parts:
        glued = _GLUED_MANA.match(parts[-1])
        if glued and is_mana_cost_token(glued.group(2)):
            parts[-1] = glued.group(1)
    return " ".join(parts).strip()


def normalize_card_title(raw: str | None) -> str:
    text = _NON_ALNUM.sub(" ", strip_trailing_mana_cost(raw).upper())
    return " ".join(text.replace("'", "'").split())


def title_tokens(raw: str | None) -> list[str]:
    tokens = []
    for token in normalize_card_title(raw).split(" "):
        token = token.strip("'")
        if len(token) >= 2 and token not in _TITLE_STOP:
            tokens.append(token)
    return tokens


def _edit_distance(left: str, right: str, *, max_dist: int = 2) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > max_dist:
        return max_dist + 1
    if not left or not right:
        return max(len(left), len(right))
    prev = list(range(len(right) + 1))
    for i, ch_l in enumerate(left, start=1):
        curr = [i]
        min_row = i
        for j, ch_r in enumerate(right, start=1):
            cost = 0 if ch_l == ch_r else 1
            best = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            curr.append(best)
            if best < min_row:
                min_row = best
        if min_row > max_dist:
            return max_dist + 1
        prev = curr
    return prev[-1]


def tokens_fuzzy_equal(left: str | None, right: str | None) -> bool:
    a = str(left or "")
    b = str(right or "")
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 5 and longer.startswith(shorter) and len(longer) - len(shorter) <= 2:
        return True
    max_dist = 2 if min(len(a), len(b)) >= 7 else 1
    if min(len(a), len(b)) < 4:
        return False
    return _edit_distance(a, b, max_dist=max_dist) <= max_dist


def _shared_token_count(left_tokens: list[str], right_tokens: list[str]) -> int:
    unused = list(right_tokens)
    shared = 0
    for token in left_tokens:
        match_at = next((i for i, other in enumerate(unused) if tokens_fuzzy_equal(token, other)), -1)
        if match_at >= 0:
            shared += 1
            unused.pop(match_at)
    return shared


def title_hint_is_usable(raw: str | None) -> bool:
    normalized = normalize_card_title(raw)
    return len(title_tokens(normalized)) >= 1 and len(normalized) >= 3


def titles_likely_match(ocr_title: str | None, catalog_name: str | None) -> bool:
    """Return True when hint is weak/absent or loosely matches the catalog name."""
    if not title_hint_is_usable(ocr_title):
        return True
    left = normalize_card_title(ocr_title)
    right = normalize_card_title(catalog_name)
    if not right:
        return True
    if left == right or left in right or right in left:
        return True
    a = title_tokens(left)
    b = title_tokens(right)
    if not a or not b:
        return True
    shared = _shared_token_count(a, b)
    needed = min(2, min(len(a), len(b)))
    return shared >= needed


def name_match_score(ocr_title: str | None, catalog_name: str | None) -> float:
    """Higher is better. 0 means no usable match."""
    if not title_hint_is_usable(ocr_title) or not catalog_name:
        return 0.0
    left = normalize_card_title(ocr_title)
    right = normalize_card_title(catalog_name)
    if not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.92
    a = title_tokens(left)
    b = title_tokens(right)
    if not a or not b:
        return 0.0
    shared = _shared_token_count(a, b)
    if shared == 0:
        return 0.0
    coverage = shared / max(len(a), len(b))
    overlap = shared / min(len(a), len(b))
    score = max(coverage, overlap * 0.85)
    # Soft boost when every OCR token fuzzy-matches something in the catalog name.
    if shared == len(a):
        score = max(score, 0.78)
    return min(1.0, score)


def _clamp_finish(
    requested: int,
    *,
    has_nonfoil: int,
    has_foil: int,
    has_etched: int,
) -> int:
    return infer_finish_for_print(
        requested,
        has_nonfoil=has_nonfoil,
        has_foil=has_foil,
        has_etched=has_etched,
    )


def _lookup_print(conn: sqlite3.Connection, set_code: str, collector_number: str):
    return conn.execute(
        """
        SELECT
            name,
            image_uri,
            collector_number,
            COALESCE(has_nonfoil, 0),
            COALESCE(has_foil, 0),
            COALESCE(has_etched, 0)
        FROM cards
        WHERE set_code = ? AND lower(collector_number) = lower(?)
        """,
        (set_code, collector_number),
    ).fetchone()


def _list_set_prints(conn: sqlite3.Connection, set_code: str) -> list:
    return conn.execute(
        """
        SELECT
            name,
            image_uri,
            collector_number,
            COALESCE(has_nonfoil, 0),
            COALESCE(has_foil, 0),
            COALESCE(has_etched, 0)
        FROM cards
        WHERE set_code = ?
        """,
        (set_code,),
    ).fetchall()


def _find_best_name_matches(
    rows: list,
    name_hint: str,
    *,
    min_score: float = 0.55,
) -> list[tuple[float, tuple]]:
    scored: list[tuple[float, tuple]] = []
    for row in rows:
        score = name_match_score(name_hint, row[0])
        if score >= min_score:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], str(item[1][2])))
    return scored


def _ensure_set_catalog(conn: sqlite3.Connection, set_code: str) -> bool:
    """Track + import the set from Scryfall if needed. Returns True when a sync ran."""
    normalized = normalize_set_code(set_code)
    if not normalized:
        raise ScanError("Set code is required")
    if normalized in EXCLUDED_SET_CODES or not normalized.isalnum():
        raise ScanError(f"Set code {normalized} is not allowed", 400)

    newly_tracked = False
    if not is_set_tracked(conn, normalized):
        add_tracked_set(conn, normalized)
        newly_tracked = True
        log.info("Scan auto-tracking set %s", normalized)

    try:
        catalog_count = import_set_catalog_from_scryfall(conn, normalized)
    except ValueError as exc:
        if newly_tracked:
            remove_tracked_set(conn, normalized)
        raise ScanError(str(exc), 404) from exc
    except Exception as exc:
        if newly_tracked:
            remove_tracked_set(conn, normalized)
        log.exception("Scan failed importing set %s", normalized)
        raise ScanError(f"Could not sync set {normalized}", 502) from exc

    conn.commit()
    bump_cache_epoch()
    log.info(
        "Scan synced set %s (%s catalog card(s), newly_tracked=%s)",
        normalized,
        catalog_count,
        newly_tracked,
    )
    return True


def _resolve_print_row(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str | None,
    name_hint: str | None,
) -> tuple[tuple, bool, str]:
    """Return (row, set_imported, resolve_method)."""
    normalized_set = normalize_set_code(set_code)
    if not normalized_set:
        raise ScanError("Set code is required")

    number = str(collector_number or "").strip() or None
    if number and is_alchemy_collector_number(number):
        raise ScanError("Alchemy cards are not supported", 400)

    has_name = title_hint_is_usable(name_hint)
    if not has_name and not number:
        raise ScanError("Need a card name or collector number to resolve the print", 400)

    set_imported = False
    prints = _list_set_prints(conn, normalized_set)
    if not prints:
        set_imported = _ensure_set_catalog(conn, normalized_set)
        prints = _list_set_prints(conn, normalized_set)
    if not prints:
        raise ScanError(f"Set {normalized_set} has no catalog cards", 404)

    by_number = _lookup_print(conn, normalized_set, number) if number else None
    name_matches = _find_best_name_matches(prints, name_hint) if has_name else []

    # Preferred path: unique strong name match within the set.
    if name_matches:
        best_score, best_row = name_matches[0]
        strong_unique = best_score >= 0.72 and (
            len(name_matches) == 1 or best_score - name_matches[1][0] >= 0.12
        )
        if by_number is not None:
            number_key = str(by_number[2]).lower()
            for score, row in name_matches:
                if str(row[2]).lower() == number_key:
                    return row, set_imported, "name+number"
            if strong_unique and not titles_likely_match(name_hint, by_number[0]):
                # Number OCR likely wrong; trust unique name.
                return best_row, set_imported, "name"
            if titles_likely_match(name_hint, by_number[0]):
                return by_number, set_imported, "number"
        if strong_unique:
            return best_row, set_imported, "name"
        if len(name_matches) > 1 and not number:
            top = ", ".join(f"{row[0]} #{row[2]}" for _, row in name_matches[:3])
            raise ScanError(
                f"Multiple matches for “{name_hint}” in {normalized_set}: {top}",
                409,
            )

    if by_number is not None:
        if has_name and not titles_likely_match(name_hint, by_number[0]):
            raise ScanError(
                f"Title doesn't match {by_number[0]} — check framing and try again",
                409,
            )
        return by_number, set_imported, "number"

    if has_name:
        raise ScanError(
            f"Could not find “{name_hint}” in set {normalized_set}",
            404,
        )
    raise ScanError(
        f"Card {normalized_set} #{number} was not found after syncing the set",
        404,
    )


def _prints_for_exact_name(conn: sqlite3.Connection, name: str) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT
            set_code,
            collector_number,
            name,
            COALESCE(art_style, ''),
            COALESCE(image_uri, ''),
            COALESCE(has_nonfoil, 0),
            COALESCE(has_foil, 0),
            COALESCE(has_etched, 0)
        FROM cards
        WHERE name = ?
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        ORDER BY set_code, CAST(collector_number AS INTEGER), collector_number
        """,
        (name,),
    ).fetchall()
    return [
        {
            "setCode": row[0],
            "collectorNumber": str(row[1]),
            "name": row[2],
            "artStyle": row[3] or "",
            "imageUri": row[4] or "",
            "hasNonfoil": bool(row[5]),
            "hasFoil": bool(row[6]),
            "hasEtched": bool(row[7]),
        }
        for row in rows
    ]


def _candidate_names_for_ocr(conn: sqlite3.Connection, query: str, *, fetch_limit: int = 300) -> list[str]:
    cleaned = strip_trailing_mana_cost(query)
    normalized = normalize_card_title(cleaned)
    tokens = title_tokens(normalized)
    if not tokens and not normalized:
        return []

    seen: set[str] = set()
    ordered: list[str] = []

    def _add_rows(rows: list) -> None:
        for row in rows:
            name = str(row[0] or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            ordered.append(name)

    # Exact / prefix hits first (fast path for clean OCR).
    if normalized:
        exact = conn.execute(
            f"""
            SELECT DISTINCT name
            FROM cards
            WHERE upper(name) = ?
              AND {exclude_alchemy_sql()}
              AND {exclude_alchemy_art_style_sql()}
            LIMIT 20
            """,
            (normalized,),
        ).fetchall()
        _add_rows(exact)

        prefix = conn.execute(
            f"""
            SELECT DISTINCT name
            FROM cards
            WHERE upper(name) LIKE ? || '%'
              AND {exclude_alchemy_sql()}
              AND {exclude_alchemy_art_style_sql()}
            ORDER BY length(name)
            LIMIT 80
            """,
            (normalized,),
        ).fetchall()
        _add_rows(prefix)

    # Anchor on the longest significant token to keep the LIKE selective.
    anchors = sorted({token.lower() for token in tokens}, key=len, reverse=True)
    search_terms: list[str] = []
    for anchor in anchors[:3]:
        if len(anchor) < 3:
            continue
        search_terms.append(anchor)
        # Truncated OCR endings ("aerialis" → "aeriali") still hit the real word.
        if len(anchor) >= 6:
            search_terms.append(anchor[:-1])
    seen_terms: set[str] = set()
    for term in search_terms:
        if term in seen_terms:
            continue
        seen_terms.add(term)
        rows = conn.execute(
            f"""
            SELECT DISTINCT name
            FROM cards
            WHERE lower(name) LIKE '%' || ? || '%'
              AND {exclude_alchemy_sql()}
              AND {exclude_alchemy_art_style_sql()}
            ORDER BY length(name)
            LIMIT ?
            """,
            (term, fetch_limit),
        ).fetchall()
        _add_rows(rows)
        if len(ordered) >= fetch_limit:
            break

    return ordered


def search_card_names_for_ocr(
    conn: sqlite3.Connection,
    *,
    query: str = "",
    name: str | None = None,
    limit: int = 8,
) -> dict:
    """Fast name lookup tuned for OCR titles (no report/price pool)."""
    ensure_card_columns(conn)
    cleaned_query = strip_trailing_mana_cost(query)
    requested_name = str(name or "").strip()
    safe_limit = max(1, min(int(limit or 8), 20))

    if not cleaned_query and not requested_name:
        raise ScanError("Card name query is required", 400)

    scored: list[tuple[float, str]] = []
    if cleaned_query:
        for candidate in _candidate_names_for_ocr(conn, cleaned_query):
            score = name_match_score(cleaned_query, candidate)
            if score <= 0:
                # Keep weak substring fallbacks when OCR is partial.
                left = normalize_card_title(cleaned_query)
                right = normalize_card_title(candidate)
                if left and right and (left in right or right in left):
                    score = 0.4
                else:
                    continue
            scored.append((score, candidate))
        scored.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    elif requested_name:
        scored = [(1.0, requested_name)]

    # Deduplicate while preserving score order.
    names: list[dict] = []
    seen_names: set[str] = set()
    for score, candidate in scored:
        if candidate in seen_names:
            continue
        seen_names.add(candidate)
        names.append({"name": candidate, "score": round(float(score), 4)})
        if len(names) >= safe_limit:
            break

    resolved = requested_name
    if resolved and resolved not in seen_names:
        # Honor an explicit chip selection even if it wasn't in the top scored list.
        names.insert(0, {"name": resolved, "score": 1.0})
        seen_names.add(resolved)
    if not resolved:
        resolved = names[0]["name"] if names else ""

    prints = _prints_for_exact_name(conn, resolved) if resolved else []

    return {
        "query": cleaned_query,
        "resolvedName": resolved,
        "names": names,
        "prints": prints,
        "totalNames": len(names),
        "totalPrints": len(prints),
    }


def ingest_scan(
    conn: sqlite3.Connection,
    *,
    set_code: str,
    collector_number: str | None = None,
    finish: int = 0,
    name_hint: str | None = None,
) -> dict:
    ensure_card_columns(conn)
    normalized_set = normalize_set_code(set_code)
    if not normalized_set:
        raise ScanError("Set code is required")

    row, set_imported, resolve_method = _resolve_print_row(
        conn,
        set_code=normalized_set,
        collector_number=collector_number,
        name_hint=name_hint,
    )

    name, image_uri, catalog_number, has_nonfoil, has_foil, has_etched = row
    normalized_number = str(catalog_number).strip()
    if not has_nonfoil and not has_foil and not has_etched:
        raise ScanError("Card has no available finishes", 400)

    requested = int(finish)
    if requested not in (FINISH_NONFOIL, FINISH_FOIL, 2):
        requested = FINISH_NONFOIL
    clamped = _clamp_finish(
        requested,
        has_nonfoil=int(has_nonfoil),
        has_foil=int(has_foil),
        has_etched=int(has_etched),
    )

    try:
        state = adjust_copy_count(
            conn,
            set_code=normalized_set,
            collector_number=normalized_number,
            finish=clamped,
            delta=1,
        )
    except ManagerError as exc:
        raise ScanError(exc.message, exc.status_code) from exc

    copies = state.get("copies") or []
    instance_id = max((int(copy["instanceId"]) for copy in copies), default=None)

    return {
        "name": name or f"{normalized_set} #{normalized_number}",
        "setCode": normalized_set,
        "collectorNumber": normalized_number,
        "finish": clamped,
        "imageUri": image_uri or "",
        "ownedCount": int(state.get("ownedCount") or 0),
        "instanceId": instance_id,
        "hasNonfoil": bool(has_nonfoil),
        "hasFoil": bool(has_foil),
        "hasEtched": bool(has_etched),
        "setImported": set_imported,
        "resolveMethod": resolve_method,
        "copyState": get_copy_state(conn, normalized_set, normalized_number, clamped),
    }
