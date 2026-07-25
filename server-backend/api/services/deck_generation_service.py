"""Multi-phase Commander deck construction engine."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter

from report.builder_queries import (
    dedupe_pool_by_name,
    identity_for_commanders,
    load_catalog_candidates,
    load_owned_pool,
    resolve_commander_rows,
)
from util.card_role_seed import SLOT_ROLES, card_has_excluded_role_for, card_roles_for
from util.commander_rules import validate_commander_deck
from util.commander_themes import (
    OWNED_BONUS,
    build_commander_theme_profile,
    card_theme_hits,
    missing_needs,
    serialize_theme_summary,
    synergy_score_for_slot,
)

DEFAULT_SLOT_COUNTS = {
    "lands": 38,
    "ramp": 10,
    "draw": 8,
    "removal": 8,
    "protection": 4,
    "synergy": 20,
    "flex": 11,
}

SLOT_PRESETS = {
    "balanced": {**DEFAULT_SLOT_COUNTS},
    "theme_first": {
        "lands": 36,
        "ramp": 9,
        "draw": 8,
        "removal": 7,
        "protection": 4,
        "synergy": 26,
        "flex": 9,
    },
    "optimized": {
        "lands": 35,
        "ramp": 11,
        "draw": 10,
        "removal": 9,
        "protection": 5,
        "synergy": 18,
        "flex": 11,
    },
    "budget_casual": {
        "lands": 38,
        "ramp": 10,
        "draw": 8,
        "removal": 8,
        "protection": 3,
        "synergy": 18,
        "flex": 14,
    },
}

BASIC_LAND_NAMES = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
}

PIP_COLORS = ("W", "U", "B", "R", "G")
THEME_DENSITY_FLOOR = 0.38


class DeckBuilderError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _finish_value(card: dict) -> float:
    finish = int(card.get("finish") or 0)
    if finish == 1:
        return float(card.get("marketValueFoil") or 0)
    if finish == 2:
        return float(card.get("marketValueEtched") or 0)
    return float(card.get("marketValue") or 0)


def _is_basic_land_card(card: dict) -> bool:
    return bool(card.get("isBasicLand") or card.get("is_basic_land"))


def _is_land_card(card: dict) -> bool:
    card_type = str(card.get("cardType") or card.get("card_type") or "").lower()
    return card_type == "land" or _is_basic_land_card(card)


def _is_utility_land_card(card: dict) -> bool:
    return _is_land_card(card) and not _is_basic_land_card(card)


def _mana_cost(card: dict) -> str:
    return str(card.get("manaCost") or card.get("mana_cost") or "")


def _pip_demand(cards: list[dict]) -> Counter:
    demand: Counter = Counter()
    for card in cards:
        if _is_land_card(card):
            continue
        qty = int(card.get("qty") or 1)
        for symbol in re.findall(r"\{([WUBRG])\}", _mana_cost(card).upper()):
            demand[symbol] += qty
        # Hybrid {W/U} counts half-ish toward both — count both lightly
        for left, right in re.findall(r"\{([WUBRG])/([WUBRG])\}", _mana_cost(card).upper()):
            demand[left] += qty
            demand[right] += qty
    return demand


def _land_pip_colors(card: dict) -> set[str]:
    text = " ".join(
        [
            str(card.get("oracleText") or card.get("oracle_text") or ""),
            str(card.get("typeLine") or card.get("type_line") or ""),
            _mana_cost(card),
        ]
    ).upper()
    colors = {color for color in PIP_COLORS if f"{{{color}}}" in text or f" {color} " in f" {text} "}
    # Basics by name
    name = str(card.get("name") or "")
    for color, basic_name in BASIC_LAND_NAMES.items():
        if name == basic_name:
            colors.add(color)
    return colors


def _slot_role_score(card: dict, slot: str) -> int:
    roles = set(card_roles_for(card))
    target_roles = SLOT_ROLES.get(slot) or set()
    if not target_roles:
        return 1
    return len(roles & target_roles) * 50


def _cmc_penalty(card: dict, slot: str) -> int:
    if slot not in {"ramp", "draw", "removal", "protection"}:
        return 0
    cmc = float(card.get("cmc") or 0)
    if slot == "ramp" and cmc > 3:
        return int((cmc - 3) * 5)
    if slot in {"removal", "protection"} and cmc > 5:
        return int((cmc - 5) * 3)
    return 0


def _classify_slot(card: dict) -> str:
    if _is_land_card(card):
        return "lands"
    roles = set(card_roles_for(card))
    for slot in ("ramp", "draw", "removal", "protection", "synergy"):
        if roles & (SLOT_ROLES.get(slot) or set()):
            return slot
    return "flex"


def _score_candidate(
    card: dict,
    *,
    slot: str,
    profile: dict | None,
    missing: set[str],
    keep_names: set[str] | None = None,
) -> int:
    score = _slot_role_score(card, slot)
    score += synergy_score_for_slot(card, profile, slot=slot)
    score -= _cmc_penalty(card, slot)
    if card.get("owned"):
        score += OWNED_BONUS
    if keep_names and (card.get("name") or "") in keep_names:
        score += 80
    hits = card_theme_hits(card, profile)
    need_hits = set(hits.get("needs") or []) & missing
    if need_hits:
        score += 25 * len(need_hits)
    if slot == "lands" and _is_utility_land_card(card):
        score += 40
        if hits.get("score"):
            score += min(40, int(hits["score"] // 2))
    return score


def _pick_for_slot(
    candidates: dict[str, dict],
    *,
    slot: str,
    profile: dict | None,
    used_names: set[str],
    excluded_roles: set[str],
    budget_remaining: float | None,
    missing: set[str],
    keep_names: set[str] | None = None,
    lands_only: bool | None = None,
) -> dict | None:
    best_card = None
    best_score = None
    for name, card in candidates.items():
        if name in used_names:
            continue
        if card_has_excluded_role_for(card, excluded_roles):
            continue
        is_land = _is_land_card(card)
        if lands_only is True and not is_land:
            continue
        if lands_only is False and is_land:
            continue
        if slot != "lands" and is_land:
            continue
        if slot == "lands" and not is_land:
            continue
        if budget_remaining is not None and not card.get("owned"):
            value = _finish_value(card)
            if value > budget_remaining:
                continue
        # Prefer cards that fill missing needs when choosing synergy/flex
        score = _score_candidate(
            card,
            slot=slot,
            profile=profile,
            missing=missing,
            keep_names=keep_names,
        )
        if best_score is None or score > best_score or (
            score == best_score and name < (best_card or {}).get("name", "")
        ):
            best_score = score
            best_card = card
    return best_card


def _identity_basic_colors(allowed_identity: list[str]) -> list[str]:
    colors = [color for color in allowed_identity if color in BASIC_LAND_NAMES]
    return colors or ["C"]


def _make_infinite_basic_land(name: str, qty: int) -> dict:
    return {
        "name": name,
        "setCode": "",
        "collectorNumber": "",
        "finish": 0,
        "owned": False,
        "cardType": "land",
        "isBasicLand": True,
        "slot": "lands",
        "suggested": False,
        "infiniteBasic": True,
        "qty": qty,
        "section": "main",
        "themeHits": [],
    }


def _fill_pip_aware_basics(
    chosen: list[dict],
    *,
    allowed_identity: list[str],
    land_target: int,
) -> list[dict]:
    spell_cards = [card for card in chosen if not _is_land_card(card)]
    utility_lands = [card for card in chosen if _is_utility_land_card(card)]
    utility_land_count = sum(int(card.get("qty") or 1) for card in utility_lands)
    needed_basics = max(0, land_target - utility_land_count)
    if needed_basics == 0:
        return spell_cards + utility_lands

    colors = _identity_basic_colors(allowed_identity)
    demand = _pip_demand(spell_cards)
    # Weight colors by pip demand within identity; fall back to even split.
    weights = []
    for color in colors:
        if color == "C":
            continue
        weights.append((color, max(1, int(demand.get(color, 0)) + 1)))
    if not weights:
        weights = [(colors[0], 1)]

    total_weight = sum(weight for _, weight in weights)
    counts_by_name: dict[str, int] = {}
    assigned = 0
    for color, weight in weights:
        share = int(round(needed_basics * (weight / total_weight)))
        basic_name = BASIC_LAND_NAMES.get(color, "Wastes")
        counts_by_name[basic_name] = counts_by_name.get(basic_name, 0) + share
        assigned += share
    # Fix rounding drift
    while assigned < needed_basics:
        color = max(weights, key=lambda row: row[1])[0]
        basic_name = BASIC_LAND_NAMES.get(color, "Wastes")
        counts_by_name[basic_name] = counts_by_name.get(basic_name, 0) + 1
        assigned += 1
    while assigned > needed_basics:
        basic_name = max(counts_by_name, key=counts_by_name.get)
        if counts_by_name[basic_name] <= 0:
            break
        counts_by_name[basic_name] -= 1
        if counts_by_name[basic_name] == 0:
            del counts_by_name[basic_name]
        assigned -= 1

    basic_entries = [
        _make_infinite_basic_land(name, qty)
        for name, qty in sorted(counts_by_name.items())
        if qty > 0
    ]
    return spell_cards + utility_lands + basic_entries


def _annotate_card(card: dict, *, slot: str, profile: dict | None, suggested: bool | None = None) -> dict:
    hits = card_theme_hits(card, profile)
    return {
        **card,
        "slot": slot,
        "suggested": (not bool(card.get("owned"))) if suggested is None else suggested,
        "qty": int(card.get("qty") or 1),
        "section": card.get("section") or "main",
        "themeHits": hits.get("themes") or [],
        "themeNeeds": hits.get("needs") or [],
        "themeScore": hits.get("score") or 0,
        "offTheme": bool(hits.get("offTheme")),
    }


def _resolve_slot_counts(
    *,
    land_count: int,
    slot_counts: dict[str, int] | None,
    preset: str | None,
) -> dict[str, int]:
    base = {**DEFAULT_SLOT_COUNTS}
    if preset and preset in SLOT_PRESETS:
        base = {**SLOT_PRESETS[preset]}
    if slot_counts:
        base.update({key: int(value) for key, value in slot_counts.items() if key in base})
    base["lands"] = max(20, min(45, int(land_count if land_count is not None else base["lands"])))
    # Keep non-land packages summing to 99 - lands
    nonland_keys = ["ramp", "draw", "removal", "protection", "synergy", "flex"]
    nonland_sum = sum(int(base.get(key, 0)) for key in nonland_keys)
    target_nonland = 99 - base["lands"]
    if nonland_sum != target_nonland:
        base["flex"] = max(0, int(base.get("flex", 0)) + (target_nonland - nonland_sum))
    return base


def _build_candidate_pool(
    conn: sqlite3.Connection,
    *,
    commander_rows: list[dict],
    allowed_identity: list[str],
    location_slugs: list[str],
    include_deck_storage: bool,
) -> dict[str, dict]:
    owned_pool = load_owned_pool(
        conn,
        location_slugs,
        include_deck_storage=include_deck_storage,
    )
    owned_by_name = dedupe_pool_by_name(owned_pool, prefer_owned=True)
    commander_names = {row.get("name") for row in commander_rows if row.get("name")}
    catalog = load_catalog_candidates(
        conn,
        allowed_identity=allowed_identity,
        exclude_names=commander_names,
    )
    catalog_by_name = dedupe_pool_by_name(catalog, prefer_owned=False)
    combined = dict(catalog_by_name)
    for name, card in owned_by_name.items():
        combined[name] = {**card, "owned": True}
    return combined


def _pick_utility_lands(
    candidates: dict[str, dict],
    *,
    profile: dict | None,
    used_names: set[str],
    excluded_roles: set[str],
    budget_remaining: float | None,
    target: int,
    keep_names: set[str] | None = None,
) -> tuple[list[dict], float | None]:
    picked: list[dict] = []
    remaining = budget_remaining
    missing = set(missing_needs([], profile))
    # Prefer owned utility lands first via scoring
    for _ in range(max(0, target)):
        card = _pick_for_slot(
            candidates,
            slot="lands",
            profile=profile,
            used_names=used_names,
            excluded_roles=excluded_roles,
            budget_remaining=remaining,
            missing=missing,
            keep_names=keep_names,
            lands_only=True,
        )
        if card is None or not _is_utility_land_card(card):
            break
        entry = _annotate_card(card, slot="lands", profile=profile)
        picked.append(entry)
        used_names.add(card.get("name") or "")
        if entry["suggested"] and remaining is not None:
            remaining -= _finish_value(card)
    return picked, remaining


def _fill_package(
    candidates: dict[str, dict],
    *,
    slot: str,
    target: int,
    profile: dict | None,
    used_names: set[str],
    excluded_roles: set[str],
    budget_remaining: float | None,
    chosen: list[dict],
    keep_names: set[str] | None = None,
) -> tuple[list[dict], float | None, list[str]]:
    warnings: list[str] = []
    remaining = budget_remaining
    for _ in range(max(0, target)):
        missing = set(missing_needs(chosen, profile))
        card = _pick_for_slot(
            candidates,
            slot=slot,
            profile=profile,
            used_names=used_names,
            excluded_roles=excluded_roles,
            budget_remaining=remaining,
            missing=missing,
            keep_names=keep_names,
            lands_only=False,
        )
        if card is None:
            warnings.append(f"Could not fill {slot} slot.")
            break
        entry = _annotate_card(card, slot=slot, profile=profile)
        chosen.append(entry)
        used_names.add(card.get("name") or "")
        if entry["suggested"] and remaining is not None:
            remaining -= _finish_value(card)
    return chosen, remaining, warnings


def _theme_trim_flex(chosen: list[dict], profile: dict | None) -> list[dict]:
    """If theme density is low, mark weakest off-theme flex for later improve cuts."""
    return chosen


def construct_deck_proposal(
    conn: sqlite3.Connection,
    *,
    commanders: list[dict],
    location_slugs: list[str],
    include_deck_storage: bool = False,
    land_count: int = 38,
    budget_cap: float | None = None,
    exclude_categories: list[str] | None = None,
    slot_counts: dict[str, int] | None = None,
    preset: str | None = None,
    existing_cards: list[dict] | None = None,
    mode: str = "generate",
) -> dict:
    commander_rows = resolve_commander_rows(conn, commanders)
    if not commander_rows:
        raise DeckBuilderError("Commander not found in catalog", status_code=400)

    allowed_identity = identity_for_commanders(commander_rows)
    profile = build_commander_theme_profile(commander_rows)
    excluded_roles = set(exclude_categories or [])
    counts = _resolve_slot_counts(
        land_count=land_count,
        slot_counts=slot_counts,
        preset=preset,
    )

    combined_candidates = _build_candidate_pool(
        conn,
        commander_rows=commander_rows,
        allowed_identity=allowed_identity,
        location_slugs=location_slugs,
        include_deck_storage=include_deck_storage,
    )

    commander_names = {row.get("name") for row in commander_rows if row.get("name")}
    used_names: set[str] = set(commander_names)
    warnings: list[str] = []
    budget_remaining = budget_cap
    chosen: list[dict] = []
    keep_names: set[str] = set()
    existing_by_name: dict[str, dict] = {}

    if existing_cards and mode in {"improve", "rebuild"}:
        for card in existing_cards:
            name = card.get("name") or card.get("cardName")
            if not name or name in commander_names:
                continue
            existing_by_name[name] = card
            # Prefer existing prints when present in pool
            if name in combined_candidates:
                combined_candidates[name] = {
                    **combined_candidates[name],
                    **{k: v for k, v in card.items() if k in {"setCode", "collectorNumber", "finish"}},
                    "owned": bool(combined_candidates[name].get("owned") or card.get("owned")),
                }

    if mode == "improve" and existing_by_name:
        # Seed keepers: lands, on-theme cards, and package staples already in deck.
        for name, card in existing_by_name.items():
            pool_card = combined_candidates.get(name) or card
            hits = card_theme_hits(pool_card, profile)
            slot = _classify_slot(pool_card)
            keep = False
            if slot == "lands":
                keep = True
            elif not hits.get("offTheme") and (hits.get("score") or 0) > 0:
                keep = True
            elif slot in {"ramp", "draw", "removal", "protection"}:
                keep = True
            if keep:
                keep_names.add(name)
                entry = _annotate_card(
                    {**pool_card, "owned": bool(pool_card.get("owned") or card.get("owned"))},
                    slot=slot,
                    profile=profile,
                    suggested=False,
                )
                chosen.append(entry)
                used_names.add(name)

    # Mana base: utility lands (owned preferred via score), then pip-aware basics later.
    land_target = counts["lands"]
    existing_utility = [card for card in chosen if _is_utility_land_card(card)]
    utility_needed = max(0, min(12, land_target // 3) - len(existing_utility))
    utility_picks, budget_remaining = _pick_utility_lands(
        combined_candidates,
        profile=profile,
        used_names=used_names,
        excluded_roles=excluded_roles,
        budget_remaining=budget_remaining,
        target=utility_needed,
        keep_names=keep_names,
    )
    chosen.extend(utility_picks)

    # Count how many of each package already kept (improve).
    kept_counts = Counter(card.get("slot") for card in chosen if not _is_land_card(card))

    package_order = ["ramp", "draw", "removal", "protection", "synergy", "flex"]
    for slot in package_order:
        target = int(counts.get(slot, 0)) - int(kept_counts.get(slot, 0))
        if target <= 0:
            continue
        chosen, budget_remaining, slot_warnings = _fill_package(
            combined_candidates,
            slot=slot,
            target=target,
            profile=profile,
            used_names=used_names,
            excluded_roles=excluded_roles,
            budget_remaining=budget_remaining,
            chosen=chosen,
            keep_names=keep_names,
        )
        warnings.extend(slot_warnings)

    spell_target = 99 - land_target
    while sum(int(card.get("qty") or 1) for card in chosen if not _is_land_card(card)) < spell_target:
        missing = set(missing_needs(chosen, profile))
        # Prefer synergy-shaped flex when density is low
        density = serialize_theme_summary(profile, chosen)["density"]
        slot = "synergy" if density < THEME_DENSITY_FLOOR else "flex"
        card = _pick_for_slot(
            combined_candidates,
            slot=slot,
            profile=profile,
            used_names=used_names,
            excluded_roles=excluded_roles,
            budget_remaining=budget_remaining,
            missing=missing,
            keep_names=keep_names,
            lands_only=False,
        )
        if card is None and slot != "flex":
            card = _pick_for_slot(
                combined_candidates,
                slot="flex",
                profile=profile,
                used_names=used_names,
                excluded_roles=excluded_roles,
                budget_remaining=budget_remaining,
                missing=missing,
                keep_names=keep_names,
                lands_only=False,
            )
        if card is None:
            warnings.append("Could not reach target spell count from catalog.")
            break
        entry = _annotate_card(card, slot=slot if slot == "synergy" else "flex", profile=profile)
        chosen.append(entry)
        used_names.add(card.get("name") or "")
        if entry["suggested"] and budget_remaining is not None:
            budget_remaining -= _finish_value(card)

    chosen = _fill_pip_aware_basics(
        chosen,
        allowed_identity=allowed_identity,
        land_target=land_target,
    )
    chosen = _theme_trim_flex(chosen, profile)

    tracked_cards = [card for card in chosen if not card.get("infiniteBasic")]
    owned_count = sum(
        int(card.get("qty") or 1)
        for card in tracked_cards
        if not card.get("suggested")
    )
    suggested_count = sum(
        int(card.get("qty") or 1)
        for card in tracked_cards
        if card.get("suggested")
    )
    estimated_cost = round(
        sum(
            _finish_value(card) * int(card.get("qty") or 1)
            for card in tracked_cards
            if card.get("suggested")
        ),
        2,
    )
    total_cards = sum(int(card.get("qty") or 1) for card in chosen)

    validation = validate_commander_deck(
        chosen,
        commanders=commander_rows,
        min_maindeck=99,
    )
    warnings.extend(validation.get("warnings") or [])

    from api.services.deck_power_service import assess_deck_power

    power = assess_deck_power(chosen, commanders=commander_rows)
    theme = serialize_theme_summary(profile, chosen)

    diff = None
    if mode in {"improve", "rebuild"} and existing_by_name:
        new_names = {
            card.get("name")
            for card in chosen
            if card.get("name") and not card.get("infiniteBasic")
        }
        old_names = set(existing_by_name)
        add_names = sorted(new_names - old_names)
        cut_names = sorted(old_names - new_names)
        keep = sorted(new_names & old_names)
        diff = {
            "keep": [
                {"name": name, "reason": "kept"}
                for name in keep
            ],
            "add": [
                {
                    "name": name,
                    "reason": _diff_add_reason(next(c for c in chosen if c.get("name") == name), profile),
                    "card": next(c for c in chosen if c.get("name") == name),
                }
                for name in add_names
            ],
            "cut": [
                {
                    "name": name,
                    "reason": _diff_cut_reason(existing_by_name[name], profile),
                    "card": existing_by_name[name],
                }
                for name in cut_names
            ],
            "swap": [],
        }

    return {
        "mode": mode,
        "commanders": commander_rows,
        "cards": chosen,
        "colorIdentity": allowed_identity,
        "slotCounts": counts,
        "preset": preset,
        "theme": theme,
        "diff": diff,
        "stats": {
            "ownedCount": owned_count,
            "suggestedCount": suggested_count,
            "totalCards": total_cards,
            "basicLandCount": sum(
                int(card.get("qty") or 1)
                for card in chosen
                if card.get("infiniteBasic")
            ),
            "utilityLandCount": sum(
                int(card.get("qty") or 1)
                for card in chosen
                if _is_utility_land_card(card)
            ),
            "estimatedCost": estimated_cost,
            "themeDensity": theme["density"],
        },
        "warnings": warnings,
        "validation": validation,
        "power": power,
    }


def _diff_add_reason(card: dict, profile: dict | None) -> str:
    slot = card.get("slot") or "flex"
    if card.get("themeNeeds"):
        return "enabler_gap" if slot == "synergy" else "theme_deficit"
    if slot == "ramp":
        return "ramp_deficit"
    if slot == "draw":
        return "draw_deficit"
    if slot in {"removal", "protection"}:
        return "interaction_deficit"
    if not card.get("offTheme"):
        return "theme_deficit"
    return f"{slot}_fill"


def _diff_cut_reason(card: dict, profile: dict | None) -> str:
    hits = card_theme_hits(card, profile)
    if hits.get("offTheme"):
        return "off_theme"
    return "package_trim"


def generate_deck_proposal(
    conn: sqlite3.Connection,
    *,
    commanders: list[dict],
    location_slugs: list[str],
    include_deck_storage: bool = False,
    land_count: int = 38,
    budget_cap: float | None = None,
    exclude_categories: list[str] | None = None,
    slot_counts: dict[str, int] | None = None,
    preset: str | None = None,
) -> dict:
    return construct_deck_proposal(
        conn,
        commanders=commanders,
        location_slugs=location_slugs,
        include_deck_storage=include_deck_storage,
        land_count=land_count,
        budget_cap=budget_cap,
        exclude_categories=exclude_categories,
        slot_counts=slot_counts,
        preset=preset,
        mode="generate",
    )


def improve_deck_proposal(
    conn: sqlite3.Connection,
    *,
    commanders: list[dict],
    existing_cards: list[dict],
    location_slugs: list[str],
    include_deck_storage: bool = False,
    land_count: int = 38,
    budget_cap: float | None = None,
    exclude_categories: list[str] | None = None,
    slot_counts: dict[str, int] | None = None,
    preset: str | None = None,
    rebuild: bool = False,
) -> dict:
    return construct_deck_proposal(
        conn,
        commanders=commanders,
        location_slugs=location_slugs,
        include_deck_storage=include_deck_storage,
        land_count=land_count,
        budget_cap=budget_cap,
        exclude_categories=exclude_categories,
        slot_counts=slot_counts,
        preset=preset,
        existing_cards=existing_cards,
        mode="rebuild" if rebuild else "improve",
    )
