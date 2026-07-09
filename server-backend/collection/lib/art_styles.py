import json

from lib.config import ART_STYLES_DIR, art_style_rules_path
from lib.run_log import get_logger
from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql

log = get_logger(__name__)

DEFAULT_ART_STYLE_NAME = "All"
DEFAULT_ART_STYLE_RULES = [{"name": DEFAULT_ART_STYLE_NAME, "all": True}]


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


def save_art_style_rules(set_code: str, rules: list) -> list[dict]:
    normalized_set = str(set_code).strip().lower()
    if not normalized_set:
        raise ValueError("Set code is required")
    normalized_rules = normalize_art_style_rules(rules)
    ART_STYLES_DIR.mkdir(parents=True, exist_ok=True)
    rules_path = art_style_rules_path(normalized_set)
    rules_path.write_text(
        json.dumps(normalized_rules, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log.info("Saved art style rules for %s", normalized_set.upper())
    return normalized_rules


# Extract the numeric part of a collector number for art-style lookup.
def normalize_collector_number(collector_number) -> int | None:
    try:
        return int("".join(char for char in str(collector_number) if char.isdigit()))
    except ValueError:
        return None


# Create the default art-style rules file for one set when it is missing.
def ensure_art_style_rules_file(set_code: str) -> None:
    rules_path = art_style_rules_path(set_code)
    if rules_path.is_file():
        return
    ART_STYLES_DIR.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(
        json.dumps(DEFAULT_ART_STYLE_RULES, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log.info("Created default art style rules for %s", set_code.upper())


# Load art-style range rules for one set from data/art_styles/{set}.json.
def load_art_style_rules(set_code: str) -> list:
    ensure_art_style_rules_file(set_code)
    rules_path = art_style_rules_path(set_code)
    try:
        with rules_path.open("r", encoding="utf-8") as rules_file:
            rules = json.load(rules_file)
    except (json.JSONDecodeError, OSError):
        return list(DEFAULT_ART_STYLE_RULES)
    if not isinstance(rules, list) or not rules:
        return list(DEFAULT_ART_STYLE_RULES)
    return rules


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
        art_style = get_art_style(normalized, collector_number)
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
def get_art_style(set_code: str, collector_number: str) -> str:
    collector_str = str(collector_number)
    collector_upper = collector_str.upper()
    is_serialized = collector_upper.endswith("Z")
    has_alchemy_prefix = collector_upper.startswith("A-")
    number = normalize_collector_number(collector_number)

    for rule in load_art_style_rules(set_code):
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
