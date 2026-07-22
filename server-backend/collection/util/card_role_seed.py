import json
from functools import lru_cache
from pathlib import Path

from lib.config import COLLECTION_DIR
from util.card_role_infer import infer_card_roles

SEED_PATH = COLLECTION_DIR / "data" / "card_role_seed.json"

SLOT_ROLES = {
    "lands": {"land"},
    "ramp": {"ramp", "fast_mana"},
    "draw": {"draw"},
    "removal": {"removal", "interaction", "board_wipe", "bounce", "land_destruction"},
    "protection": {"protection", "interaction", "counterspell", "fog"},
    "synergy": {
        "synergy",
        "recursion",
        "reanimate",
        "equipment",
        "aura",
        "combo_piece",
        "sac_outlet",
        "mill",
    },
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


def _card_name(card: dict | None = None, *, name: str = "") -> str:
    if name:
        return str(name).strip()
    if not card:
        return ""
    return str(
        card.get("card_name")
        or card.get("name")
        or card.get("cardName")
        or ""
    ).strip()


def _seed_entry(name: str) -> dict:
    if not name:
        return {}
    entry = load_card_role_seed().get(name, {})
    return entry if isinstance(entry, dict) else {}


def card_roles_for(card: dict | None = None, *, name: str = "") -> list[str]:
    """Merge inferred structural roles with seed roles, applying suppress."""
    resolved_name = _card_name(card, name=name)
    roles: set[str] = set()
    if card:
        roles.update(infer_card_roles(card))
    entry = _seed_entry(resolved_name)
    for role in entry.get("roles") or []:
        roles.add(str(role))
    for role in entry.get("suppress") or []:
        roles.discard(str(role))
    return sorted(roles)


def card_roles(name: str) -> list[str]:
    """Name-only lookup: seed roles when present; empty without oracle/type."""
    return card_roles_for(name=name)


def card_bracket_weight(name: str) -> int:
    entry = _seed_entry(str(name or "").strip())
    if not entry:
        return 0
    try:
        return int(entry.get("bracketWeight") or 0)
    except (TypeError, ValueError):
        return 0


def card_has_role(name: str, role: str) -> bool:
    return role in card_roles(name)


def card_has_role_for(card: dict, role: str) -> bool:
    return role in card_roles_for(card)


def card_has_excluded_role(name: str, excluded_roles: set[str]) -> bool:
    if not excluded_roles:
        return False
    return any(role in excluded_roles for role in card_roles(name))


def card_has_excluded_role_for(card: dict, excluded_roles: set[str]) -> bool:
    if not excluded_roles:
        return False
    return any(role in excluded_roles for role in card_roles_for(card))
