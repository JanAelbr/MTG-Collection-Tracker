"""Commander theme profiling and synergy scoring for deck construction."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from lib.config import COLLECTION_DIR

THEME_SEED_PATH = COLLECTION_DIR / "data" / "commander_theme_seed.json"

# Ability words / keyword abilities that often define a strategy.
ABILITY_KEYWORDS = frozenset({
    "landfall",
    "proliferate",
    "cascade",
    "exalted",
    "convoke",
    "affinity",
    "delirium",
    "threshold",
    "metalcraft",
    "revolt",
    "raid",
    "magecraft",
    "celebrate",
    "battalion",
    "bloodthirst",
    "undying",
    "persist",
    "modular",
    "living weapon",
    "equip",
    "flashback",
    "escape",
    "unearth",
    "encore",
    "myriad",
    "populate",
    "investigate",
    "venture",
    "dungeon",
    "amass",
    "party",
    "changeling",
    "partner",
    "friends forever",
})

# Oracle / type patterns → strategy theme id + default weight.
STRATEGY_PATTERNS: list[tuple[str, str, float]] = [
    (r"create\s+(?:a|one|two|three|x|\d+)\s+.*\btoken", "tokens", 1.0),
    (r"\btoken(?:s)?\b", "tokens", 0.55),
    (r"\+1/\+1 counter", "counters", 1.0),
    (r"proliferate", "counters", 0.9),
    (r"sacrifice (?:a|another) creature", "aristocrats", 0.95),
    (r"whenever .+ (?:dies|is put into .* graveyard)", "aristocrats", 0.7),
    (r"return .+ from (?:your )?graveyard", "graveyard", 0.9),
    (r"\breanimate\b|\bmill\b", "graveyard", 0.75),
    (r"artifact(?:s)? you control", "artifacts", 0.9),
    (r"enchantment(?:s)? you control", "enchantments", 0.9),
    (r"whenever you cast (?:an? )?(?:instant|sorcery)", "spellslinger", 0.95),
    (r"copy (?:target )?(?:instant|sorcery)", "spellslinger", 0.8),
    (r"exile .+ then return (?:it|that card) to the battlefield", "blink", 0.9),
    (r"equipped creature|equipment you control", "voltron", 0.85),
    (r"aura(?:s)? you control|enchanted creature", "auras", 0.85),
    (r"treasure token|create .*\btreasure\b", "treasures", 0.95),
    (r"\bcascade\b", "cascade", 0.9),
    (r"landfall", "landfall", 1.0),
    (r"lands? you control", "lands_matter", 0.55),
    (r"draw (?:a|one|two|three|x|\d+) cards?", "draw_matters", 0.35),
    (r"goad", "goad", 0.8),
    (r"the monarch", "monarch", 0.85),
    (r"infect|poison counter", "infect", 0.9),
    (r"energy counter", "energy", 0.9),
    (r"vehicle|crew ", "vehicles", 0.8),
    (r"historic", "historic", 0.7),
]

# Theme id → construction "needs" buckets to balance enablers vs payoffs.
THEME_NEEDS: dict[str, list[str]] = {
    "tokens": ["token_makers", "anthems", "sac_outlets"],
    "aristocrats": ["sac_outlets", "token_makers", "drain_payoffs"],
    "counters": ["counter_makers", "proliferate", "counter_payoffs"],
    "graveyard": ["self_mill", "reanimation", "discard_enablers"],
    "artifacts": ["artifact_makers", "artifact_payoffs"],
    "enchantments": ["enchantment_makers", "enchantment_payoffs"],
    "spellslinger": ["cantrips", "copy_spells", "storm_payoffs"],
    "blink": ["blink_effects", "etb_creatures"],
    "voltron": ["equipment", "protection", "evasion"],
    "auras": ["auras", "enchantress_draw"],
    "treasures": ["treasure_makers", "artifact_payoffs"],
    "landfall": ["land_ramp", "landfall_payoffs"],
    "lands_matter": ["land_ramp", "land_synergy"],
    "cascade": ["cascade_enablers", "cheap_cascade_targets"],
    "tribal": ["tribal_lords", "tribal_payoffs", "tribal_tutors"],
}

NEED_PATTERNS: list[tuple[str, str]] = [
    (r"create\s+(?:a|one|two|three|x|\d+)\s+.*\btoken", "token_makers"),
    (r"creatures? you control get|\banthem\b|other .+ creatures? you control", "anthems"),
    (r"sacrifice (?:a|another) creature:|sac outlet", "sac_outlets"),
    (r"loses? \d+ life|drain|extort", "drain_payoffs"),
    (r"\+1/\+1 counter", "counter_makers"),
    (r"proliferate", "proliferate"),
    (r"for each \+1/\+1 counter|counters on .+ get", "counter_payoffs"),
    (r"\bmill\b|put the top .+ cards? of", "self_mill"),
    (r"return .+ from (?:your )?graveyard to the battlefield", "reanimation"),
    (r"discard .+ card|rummage|loot", "discard_enablers"),
    (r"create .*\bartifact\b|artifact token", "artifact_makers"),
    (r"artifacts? you control get|affinity for artifacts", "artifact_payoffs"),
    (r"create .*\benchantment\b|enchantment token", "enchantment_makers"),
    (r"enchantments? you control get|enchantress", "enchantment_payoffs"),
    (r"draw a card.*instant|cantrip|scry 1.*draw", "cantrips"),
    (r"copy (?:target )?(?:instant|sorcery)", "copy_spells"),
    (r"exile .+ then return .+ to the battlefield", "blink_effects"),
    (r"enters? the battlefield.*when|whenever .+ enters", "etb_creatures"),
    (r"\bequipment\b|equip ", "equipment"),
    (r"hexproof|indestructible|protection from", "protection"),
    (r"flying|unblockable|can't be blocked", "evasion"),
    (r"\baura\b", "auras"),
    (r"treasure token|create .*\btreasure\b", "treasure_makers"),
    (r"search your library for (?:a|up to .+ )?land", "land_ramp"),
    (r"landfall", "landfall_payoffs"),
    (r"cascade", "cascade_enablers"),
]

OWNED_BONUS = 120  # Capped so theme can still win.
SYNERGY_SLOT_WEIGHT = {
    "synergy": 1.0,
    "flex": 0.75,
    "ramp": 0.35,
    "draw": 0.4,
    "removal": 0.2,
    "protection": 0.25,
    "lands": 0.45,
}


@lru_cache(maxsize=1)
def load_commander_theme_seed() -> dict[str, dict]:
    if not THEME_SEED_PATH.is_file():
        return {}
    try:
        payload = json.loads(THEME_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _text(card: dict, *keys: str) -> str:
    for key in keys:
        value = card.get(key)
        if value:
            return str(value)
    return ""


def _type_line(card: dict) -> str:
    return _text(card, "typeLine", "type_line")


def _oracle(card: dict) -> str:
    return _text(card, "oracleText", "oracle_text")


def _creature_subtypes(type_line: str) -> list[str]:
    match = re.split(r"\s*[—–]\s*|\s+-\s+", type_line, maxsplit=1)
    if len(match) < 2:
        return []
    left, right = match[0].lower(), match[1]
    if "creature" not in left and "tribal" not in left and "kindred" not in left:
        if "creature" not in type_line.lower():
            return []
    subtypes = []
    for token in re.split(r"[\s/]+", right):
        word = "".join(ch for ch in token if ch.isalpha())
        if len(word) >= 3:
            subtypes.append(word.lower())
    return subtypes


def _merge_theme(bucket: dict[str, float], theme_id: str, weight: float) -> None:
    if not theme_id:
        return
    bucket[theme_id] = max(bucket.get(theme_id, 0.0), float(weight))


def _sorted_themes(bucket: dict[str, float]) -> list[dict]:
    return [
        {"id": theme_id, "weight": round(weight, 3)}
        for theme_id, weight in sorted(bucket.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_commander_theme_profile(commander_rows: list[dict]) -> dict:
    """Build a theme profile from one or more commanders."""
    primary: dict[str, float] = {}
    tribal: dict[str, float] = {}
    keywords: dict[str, float] = {}
    needs: set[str] = set()
    avoid: set[str] = set()
    seed = load_commander_theme_seed()

    for commander in commander_rows or []:
        name = str(commander.get("name") or "").strip()
        type_line = _type_line(commander)
        oracle = _oracle(commander)
        blob = f"{type_line}\n{oracle}".lower()

        for subtype in _creature_subtypes(type_line):
            _merge_theme(tribal, subtype, 1.0)
            needs.update(THEME_NEEDS.get("tribal", []))

        for ability in ABILITY_KEYWORDS:
            if ability in blob:
                _merge_theme(keywords, ability.replace(" ", "_"), 0.85)
                if ability in {"landfall", "proliferate", "cascade", "equip"}:
                    mapped = {
                        "landfall": "landfall",
                        "proliferate": "counters",
                        "cascade": "cascade",
                        "equip": "voltron",
                    }[ability]
                    _merge_theme(primary, mapped, 0.8)
                    needs.update(THEME_NEEDS.get(mapped, []))

        for pattern, theme_id, weight in STRATEGY_PATTERNS:
            if re.search(pattern, blob, flags=re.IGNORECASE):
                _merge_theme(primary, theme_id, weight)
                needs.update(THEME_NEEDS.get(theme_id, []))

        override = seed.get(name) if name else None
        if isinstance(override, dict):
            for theme_id, weight in (override.get("primary") or {}).items():
                _merge_theme(primary, str(theme_id), float(weight))
            for theme_id, weight in (override.get("tribal") or {}).items():
                _merge_theme(tribal, str(theme_id), float(weight))
            for theme_id, weight in (override.get("keywords") or {}).items():
                _merge_theme(keywords, str(theme_id), float(weight))
            for need in override.get("needs") or []:
                needs.add(str(need))
            for anti in override.get("avoid") or []:
                avoid.add(str(anti))

    # Promote strongest tribal type into primary as tribal theme.
    if tribal:
        top_tribe, top_weight = max(tribal.items(), key=lambda item: item[1])
        _merge_theme(primary, f"tribal:{top_tribe}", top_weight)

    if primary.get("tokens") and primary.get("voltron", 0) < 0.6:
        avoid.add("solo_voltron")
    if primary.get("voltron") and not primary.get("tokens"):
        avoid.add("go_wide")

    return {
        "primary": _sorted_themes(primary),
        "tribal": _sorted_themes(tribal),
        "keywords": _sorted_themes(keywords),
        "needs": sorted(needs),
        "avoid": sorted(avoid),
    }


def profile_theme_ids(profile: dict | None) -> set[str]:
    if not profile:
        return set()
    ids: set[str] = set()
    for key in ("primary", "tribal", "keywords"):
        for row in profile.get(key) or []:
            theme_id = str(row.get("id") or "")
            if theme_id:
                ids.add(theme_id)
                if theme_id.startswith("tribal:"):
                    ids.add(theme_id.split(":", 1)[1])
    return ids


def card_theme_hits(card: dict, profile: dict | None) -> dict:
    """Return which profile themes a card hits and which needs it supplies."""
    if not profile:
        return {"themes": [], "needs": [], "score": 0, "offTheme": True}

    type_line = _type_line(card).lower()
    oracle = _oracle(card).lower()
    blob = f"{type_line}\n{oracle}"
    subtypes = set(_creature_subtypes(_type_line(card)))
    hits: dict[str, float] = {}
    supplied: set[str] = set()

    for row in profile.get("tribal") or []:
        tribe = str(row.get("id") or "")
        if tribe and tribe in subtypes:
            hits[f"tribal:{tribe}"] = max(hits.get(f"tribal:{tribe}", 0), float(row.get("weight") or 1))
            hits[tribe] = hits[f"tribal:{tribe}"]

    for row in profile.get("keywords") or []:
        kid = str(row.get("id") or "").replace("_", " ")
        if kid and kid in blob:
            key = str(row.get("id") or "")
            hits[key] = max(hits.get(key, 0), float(row.get("weight") or 0.8))

    for row in profile.get("primary") or []:
        theme_id = str(row.get("id") or "")
        weight = float(row.get("weight") or 0)
        if not theme_id:
            continue
        if theme_id.startswith("tribal:"):
            tribe = theme_id.split(":", 1)[1]
            if tribe in subtypes:
                hits[theme_id] = max(hits.get(theme_id, 0), weight)
            continue
        # Map strategy themes via patterns
        matched = False
        for pattern, pattern_theme, _ in STRATEGY_PATTERNS:
            if pattern_theme == theme_id and re.search(pattern, blob, flags=re.IGNORECASE):
                matched = True
                break
        if matched or theme_id.replace("_", " ") in blob:
            hits[theme_id] = max(hits.get(theme_id, 0), weight)

    for pattern, need_id in NEED_PATTERNS:
        if need_id in (profile.get("needs") or []) and re.search(pattern, blob, flags=re.IGNORECASE):
            supplied.add(need_id)

    # Tribal lords / payoffs heuristics
    for tribe_row in profile.get("tribal") or []:
        tribe = str(tribe_row.get("id") or "")
        if not tribe:
            continue
        if tribe in blob and ("you control get" in blob or "other" in blob):
            supplied.add("tribal_lords")
        if tribe in subtypes:
            supplied.add("tribal_payoffs")

    primary_ids = {str(row.get("id")) for row in (profile.get("primary") or [])}
    primary_hits = sum(weight for theme_id, weight in hits.items() if theme_id in primary_ids)
    secondary_hits = sum(weight for theme_id, weight in hits.items() if theme_id not in primary_ids)
    score = int(primary_hits * 40 + secondary_hits * 18 + len(supplied) * 12)
    off_theme = score <= 0 and not any(t.startswith("tribal:") for t in hits)

    avoid = set(profile.get("avoid") or [])
    if "solo_voltron" in avoid and ("equip " in blob or "equipped creature" in blob) and "token" not in blob:
        score -= 25
    if "go_wide" in avoid and re.search(r"create\s+(?:a|one|two).*\btoken", blob):
        score -= 20

    return {
        "themes": sorted(hits.keys()),
        "needs": sorted(supplied),
        "score": score,
        "offTheme": off_theme,
        "primaryScore": int(primary_hits * 40),
    }


def synergy_score_for_slot(card: dict, profile: dict | None, *, slot: str) -> int:
    hits = card_theme_hits(card, profile)
    base = int(hits.get("score") or 0)
    weight = SYNERGY_SLOT_WEIGHT.get(slot, 0.3)
    score = int(base * weight)
    if slot in {"synergy", "flex"} and hits.get("offTheme"):
        score -= 30
    return score


def theme_density(cards: list[dict], profile: dict | None) -> float:
    if not profile:
        return 0.0
    nonlands = [
        card for card in cards
        if str(card.get("cardType") or card.get("card_type") or "").lower() != "land"
        and not card.get("isBasicLand")
        and not card.get("infiniteBasic")
    ]
    if not nonlands:
        return 0.0
    on_theme = 0
    for card in nonlands:
        hits = card_theme_hits(card, profile)
        if not hits.get("offTheme") and (hits.get("score") or 0) > 0:
            on_theme += int(card.get("qty") or 1)
    total = sum(int(card.get("qty") or 1) for card in nonlands)
    return round(on_theme / total, 3) if total else 0.0


def covered_needs(cards: list[dict], profile: dict | None) -> list[str]:
    if not profile:
        return []
    found: set[str] = set()
    for card in cards:
        hits = card_theme_hits(card, profile)
        found.update(hits.get("needs") or [])
    return sorted(found & set(profile.get("needs") or []))


def missing_needs(cards: list[dict], profile: dict | None) -> list[str]:
    if not profile:
        return []
    wanted = set(profile.get("needs") or [])
    return sorted(wanted - set(covered_needs(cards, profile)))


def serialize_theme_summary(profile: dict | None, cards: list[dict] | None = None) -> dict:
    profile = profile or {"primary": [], "tribal": [], "keywords": [], "needs": [], "avoid": []}
    cards = cards or []
    return {
        "profile": profile,
        "density": theme_density(cards, profile),
        "coveredNeeds": covered_needs(cards, profile),
        "missingNeeds": missing_needs(cards, profile),
    }
