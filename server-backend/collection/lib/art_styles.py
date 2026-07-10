import json
import sqlite3

from lib.art_style_seed import BUNDLED_ART_STYLE_RULES
from lib.config import ART_STYLES_DIR, canonical_set_code_lower
from lib.run_log import get_logger
from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql

log = get_logger(__name__)

DEFAULT_ART_STYLE_NAME = "All"
DEFAULT_ART_STYLE_RULES = [{"name": DEFAULT_ART_STYLE_NAME, "all": True}]
ART_STYLE_RULES_TABLE = "art_style_rules"


def _clean_rule_name(name) -> str:
    return str(name or "").strip()


def _rule_has_match_fields(rule: dict) -> bool:
    if rule.get("all"):
        return True
    if rule.get("prefix"):
        return True
    if rule.get("suffix"):
        return True
    first = rule.get("firstNumber")
    last = rule.get("lastNumber")
    return first is not None and last is not None


def normalize_art_style_rule(rule: dict) -> dict:
    if not isinstance(rule, dict):
        raise ValueError("Each art style rule must be an object")

    name = _clean_rule_name(rule.get("name"))
    if not name:
        raise ValueError("Art style rules need a name")

    normalized: dict = {"name": name}
    if rule.get("all"):
        normalized["all"] = True
        return normalized

    prefix = rule.get("prefix")
    if prefix is not None and str(prefix).strip():
        normalized["prefix"] = str(prefix).strip()

    suffix = rule.get("suffix")
    if suffix is not None and str(suffix).strip():
        normalized["suffix"] = str(suffix).strip()

    first = rule.get("firstNumber")
    last = rule.get("lastNumber")
    if first is not None or last is not None:
        if first is None or last is None:
            raise ValueError(f'Rule "{name}" needs both firstNumber and lastNumber')
        normalized["firstNumber"] = int(first)
        normalized["lastNumber"] = int(last)
        if normalized["firstNumber"] > normalized["lastNumber"]:
            raise ValueError(
                f'Rule "{name}" has firstNumber greater than lastNumber',
            )

    if not _rule_has_match_fields(normalized):
        raise ValueError(
            f'Rule "{name}" must use all, a number range, prefix, and/or suffix',
        )
    return normalized


def normalize_art_style_rules(rules: list) -> list[dict]:
    if not isinstance(rules, list) or not rules:
        raise ValueError("Art style rules must be a non-empty list")
    return [normalize_art_style_rule(rule) for rule in rules]


def validate_art_style_rules(rules: list) -> list[str]:
    try:
        normalize_art_style_rules(rules)
    except ValueError as exc:
        return [str(exc)]
    return []


def _ensure_art_style_rules_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ART_STYLE_RULES_TABLE} (
            set_code TEXT PRIMARY KEY,
            rules_json TEXT NOT NULL
        )
        """
    )


def ensure_art_style_rules_table(conn: sqlite3.Connection) -> None:
    _ensure_art_style_rules_table(conn)
    _migrate_art_style_rules_from_files(conn)
    _seed_bundled_art_style_rules(conn)


def _set_has_art_style_rules(conn: sqlite3.Connection, set_code: str) -> bool:
    row = conn.execute(
        f"SELECT 1 FROM {ART_STYLE_RULES_TABLE} WHERE set_code = ? LIMIT 1",
        (canonical_set_code_lower(set_code),),
    ).fetchone()
    return row is not None


def _migrate_art_style_rules_from_files(conn: sqlite3.Connection) -> None:
    if not ART_STYLES_DIR.is_dir():
        return
    for path in sorted(ART_STYLES_DIR.glob("*.json")):
        set_code = path.stem.lower()
        if _set_has_art_style_rules(conn, set_code):
            continue
        try:
            rules = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rules, list) or not rules:
            continue
        try:
            normalized_rules = normalize_art_style_rules(rules)
        except ValueError:
            continue
        _upsert_art_style_rules(conn, set_code, normalized_rules)


def _seed_bundled_art_style_rules(conn: sqlite3.Connection) -> None:
    for set_code, rules in BUNDLED_ART_STYLE_RULES.items():
        normalized_set = canonical_set_code_lower(set_code)
        if _set_has_art_style_rules(conn, normalized_set):
            continue
        _upsert_art_style_rules(conn, normalized_set, normalize_art_style_rules(rules))


def _upsert_art_style_rules(
    conn: sqlite3.Connection,
    set_code: str,
    rules: list[dict],
) -> None:
    normalized_set = canonical_set_code_lower(set_code)
    conn.execute(
        f"""
        INSERT INTO {ART_STYLE_RULES_TABLE} (set_code, rules_json)
        VALUES (?, ?)
        ON CONFLICT(set_code) DO UPDATE SET rules_json = excluded.rules_json
        """,
        (normalized_set, json.dumps(rules, ensure_ascii=False)),
    )


def _delete_art_style_rules(conn: sqlite3.Connection, set_code: str) -> None:
    conn.execute(
        f"DELETE FROM {ART_STYLE_RULES_TABLE} WHERE set_code = ?",
        (canonical_set_code_lower(set_code),),
    )


def _load_art_style_rules_from_db(conn: sqlite3.Connection, set_code: str) -> list[dict] | None:
    try:
        row = conn.execute(
            f"SELECT rules_json FROM {ART_STYLE_RULES_TABLE} WHERE set_code = ?",
            (canonical_set_code_lower(set_code),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    try:
        rules = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(rules, list) or not rules:
        return None
    return rules


def load_art_style_rules(conn: sqlite3.Connection, set_code: str) -> list:
    rules = _load_art_style_rules_from_db(conn, set_code)
    if rules is None:
        return list(DEFAULT_ART_STYLE_RULES)
    return rules


def save_art_style_rules(
    conn: sqlite3.Connection,
    set_code: str,
    rules: list,
) -> list[dict]:
    normalized_set = str(set_code).strip().lower()
    if not normalized_set:
        raise ValueError("Set code is required")
    normalized_rules = normalize_art_style_rules(rules)
    _ensure_art_style_rules_table(conn)
    if normalized_rules == normalize_art_style_rules(DEFAULT_ART_STYLE_RULES):
        _delete_art_style_rules(conn, normalized_set)
    else:
        _upsert_art_style_rules(conn, normalized_set, normalized_rules)
    log.info("Saved art style rules for %s", normalized_set.upper())
    return normalized_rules


def load_art_style_rules_for_sets(
    conn: sqlite3.Connection,
    set_codes: list[str],
) -> dict[str, list]:
    art_styles: dict[str, list] = {}
    for set_code in set_codes:
        normalized_set = canonical_set_code_lower(set_code)
        rules = _load_art_style_rules_from_db(conn, normalized_set)
        if rules:
            art_styles[normalized_set] = rules
    return art_styles


def import_art_style_rules(
    conn: sqlite3.Connection,
    art_styles: dict[str, list],
    *,
    merge: bool,
) -> None:
    _ensure_art_style_rules_table(conn)
    for set_code, rules in art_styles.items():
        normalized_set = canonical_set_code_lower(set_code)
        normalized_rules = normalize_art_style_rules(rules)
        if merge:
            existing = _load_art_style_rules_from_db(conn, normalized_set)
            if existing is not None and normalize_art_style_rules(existing) == normalized_rules:
                continue
        save_art_style_rules(conn, normalized_set, normalized_rules)


# Extract the numeric part of a collector number for art-style lookup.
def normalize_collector_number(collector_number) -> int | None:
    try:
        return int("".join(char for char in str(collector_number) if char.isdigit()))
    except ValueError:
        return None


def refresh_art_styles_for_set(conn, set_code: str) -> int:
    normalized = str(set_code).strip().lower()
    rows = conn.execute(
        f"""
        SELECT collector_number
        FROM cards
        WHERE set_code = ?
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        """,
        (normalized.upper(),),
    ).fetchall()
    updated = 0
    for (collector_number,) in rows:
        art_style = get_art_style(conn, normalized, collector_number)
        conn.execute(
            """
            UPDATE cards
            SET art_style = ?
            WHERE set_code = ? AND collector_number = ?
            """,
            (art_style, normalized.upper(), collector_number),
        )
        updated += 1
    return updated


# Resolve the art style name for one card from collector-number ranges.
def get_art_style(conn: sqlite3.Connection, set_code: str, collector_number: str) -> str:
    collector_str = str(collector_number)
    collector_upper = collector_str.upper()
    is_serialized = collector_upper.endswith("Z")
    has_alchemy_prefix = collector_upper.startswith("A-")
    number = normalize_collector_number(collector_number)

    for rule in load_art_style_rules(conn, set_code):
        if rule.get("all"):
            return rule.get("name", DEFAULT_ART_STYLE_NAME)

        rule_prefix = rule.get("prefix")
        if rule_prefix:
            if not collector_upper.startswith(str(rule_prefix).upper()):
                continue
        elif has_alchemy_prefix:
            continue

        rule_suffix = rule.get("suffix")
        if rule_suffix:
            if not collector_upper.endswith(str(rule_suffix).upper()):
                continue
        elif is_serialized:
            continue

        first = rule.get("firstNumber")
        last = rule.get("lastNumber")
        if first is not None and last is not None:
            if number is None:
                continue
            if first <= number <= last:
                return rule.get("name", "Unknown")
            continue

        if rule_prefix:
            return rule.get("name", "Unknown")

    return "Unknown"
