import json

from lib.config import ART_STYLES_DIR, art_style_rules_path
from lib.run_log import get_logger

log = get_logger(__name__)

DEFAULT_ART_STYLE_NAME = "All"
DEFAULT_ART_STYLE_RULES = [{"name": DEFAULT_ART_STYLE_NAME, "all": True}]


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
