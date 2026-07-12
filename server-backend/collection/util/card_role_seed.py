import json
from functools import lru_cache
from pathlib import Path

from lib.config import COLLECTION_DIR

SEED_PATH = COLLECTION_DIR / "data" / "card_role_seed.json"

SLOT_ROLES = {
    "lands": {"land"},
    "ramp": {"ramp", "fast_mana"},
    "draw": {"draw"},
    "removal": {"removal", "interaction"},
    "protection": {"protection", "interaction"},
    "synergy": {"synergy", "recursion", "equipment", "combo_piece"},
    "flex": set(),
}


@lru_cache(maxsize=1)
def load_card_role_seed() -> dict[str, dict]:
    if not SEED_PATH.is_file():
        return {}
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return payload


def card_roles(name: str) -> list[str]:
    entry = load_card_role_seed().get(str(name or "").strip(), {})
    roles = entry.get("roles") or []
    return [str(role) for role in roles]


def card_bracket_weight(name: str) -> int:
    entry = load_card_role_seed().get(str(name or "").strip())
    if not entry:
        return 0
    try:
        return int(entry.get("bracketWeight") or 0)
    except (TypeError, ValueError):
        return 0


def card_has_role(name: str, role: str) -> bool:
    return role in card_roles(name)


def card_has_excluded_role(name: str, excluded_roles: set[str]) -> bool:
    if not excluded_roles:
        return False
    return any(role in excluded_roles for role in card_roles(name))
