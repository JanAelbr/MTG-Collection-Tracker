import sqlite3

from report.builder_queries import (
    commander_keywords,
    dedupe_pool_by_name,
    identity_for_commanders,
    load_catalog_candidates,
    load_owned_pool,
    resolve_commander_rows,
)
from util.card_role_seed import SLOT_ROLES, card_has_excluded_role_for, card_roles_for
from util.commander_rules import validate_commander_deck

DEFAULT_SLOT_COUNTS = {
    "lands": 38,
    "ramp": 10,
    "draw": 8,
    "removal": 8,
    "protection": 4,
    "synergy": 20,
    "flex": 11,
}

BASIC_LAND_NAMES = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
}


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


def _slot_role_score(card: dict, slot: str) -> int:
    roles = set(card_roles_for(card))
    target_roles = SLOT_ROLES.get(slot) or set()
    if not target_roles:
        return 1
    return len(roles & target_roles) * 50


def _keyword_score(card: dict, keywords: set[str]) -> int:
    oracle = str(card.get("oracleText") or "").lower()
    if not oracle or not keywords:
        return 0
    return sum(5 for keyword in keywords if keyword in oracle)


def _cmc_penalty(card: dict, slot: str) -> int:
    if slot not in {"ramp", "draw", "removal", "protection"}:
        return 0
    cmc = float(card.get("cmc") or 0)
    if slot == "ramp" and cmc > 3:
        return int((cmc - 3) * 5)
    if slot in {"removal", "protection"} and cmc > 5:
        return int((cmc - 5) * 3)
    return 0


def _score_candidate(card: dict, *, slot: str, keywords: set[str]) -> int:
    score = _slot_role_score(card, slot)
    score += _keyword_score(card, keywords)
    score -= _cmc_penalty(card, slot)
    if card.get("owned"):
        score += 1000
    if slot == "lands" and (card.get("isBasicLand") or card.get("cardType") == "land"):
        score += 25
    return score


def _pick_for_slot(
    candidates: dict[str, dict],
    *,
    slot: str,
    keywords: set[str],
    used_names: set[str],
    excluded_roles: set[str],
    budget_remaining: float | None,
) -> dict | None:
    best_card = None
    best_score = None
    for name, card in candidates.items():
        if name in used_names:
            continue
        if card_has_excluded_role_for(card, excluded_roles):
            continue
        if slot != "lands" and (card.get("isBasicLand") or card.get("cardType") == "land"):
            continue
        if slot == "lands" and card.get("cardType") != "land" and not card.get("isBasicLand"):
            continue
        if budget_remaining is not None and not card.get("owned"):
            value = _finish_value(card)
            if value > budget_remaining:
                continue
        score = _score_candidate(card, slot=slot, keywords=keywords)
        if best_score is None or score > best_score or (score == best_score and name < (best_card or {}).get("name", "")):
            best_score = score
            best_card = card
    return best_card


def _is_basic_land_card(card: dict) -> bool:
    return bool(card.get("isBasicLand") or card.get("is_basic_land"))


def _is_utility_land_card(card: dict) -> bool:
    card_type = str(card.get("cardType") or card.get("card_type") or "").lower()
    return card_type == "land" and not _is_basic_land_card(card)


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
    }


def _fill_basic_lands(
    chosen: list[dict],
    *,
    allowed_identity: list[str],
    land_target: int,
) -> list[dict]:
    spell_cards = [
        card for card in chosen
        if not _is_basic_land_card(card) and not _is_utility_land_card(card)
    ]
    utility_lands = [card for card in chosen if _is_utility_land_card(card)]
    utility_land_count = sum(int(card.get("qty") or 1) for card in utility_lands)
    needed_basics = max(0, land_target - utility_land_count)
    if needed_basics == 0:
        return spell_cards + utility_lands

    colors = _identity_basic_colors(allowed_identity)
    counts_by_name: dict[str, int] = {}
    for index in range(needed_basics):
        color = colors[index % len(colors)]
        basic_name = BASIC_LAND_NAMES.get(color, "Wastes")
        counts_by_name[basic_name] = counts_by_name.get(basic_name, 0) + 1

    basic_entries = [
        _make_infinite_basic_land(name, qty)
        for name, qty in sorted(counts_by_name.items())
    ]
    return spell_cards + utility_lands + basic_entries


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
) -> dict:
    commander_rows = resolve_commander_rows(conn, commanders)
    if not commander_rows:
        raise DeckBuilderError("Commander not found in catalog", status_code=400)

    allowed_identity = identity_for_commanders(commander_rows)
    keywords = commander_keywords(commander_rows)
    excluded_roles = set(exclude_categories or [])

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
    combined_candidates = dict(catalog_by_name)
    for name, card in owned_by_name.items():
        combined_candidates[name] = {**card, "owned": True}

    counts = {**DEFAULT_SLOT_COUNTS, **(slot_counts or {})}
    counts["lands"] = max(20, min(45, int(land_count)))
    flex_total = 99 - sum(counts.values())
    counts["flex"] = max(0, counts.get("flex", 0) + flex_total)

    chosen: list[dict] = []
    used_names: set[str] = set(commander_names)
    warnings: list[str] = []
    budget_remaining = budget_cap

    slot_order = ["ramp", "draw", "removal", "protection", "synergy", "flex"]
    for slot in slot_order:
        target = int(counts.get(slot, 0))
        for _ in range(target):
            card = _pick_for_slot(
                combined_candidates,
                slot=slot,
                keywords=keywords,
                used_names=used_names,
                excluded_roles=excluded_roles,
                budget_remaining=budget_remaining,
            )
            if card is None:
                warnings.append(f"Could not fill {slot} slot.")
                break
            entry = {
                **card,
                "slot": slot,
                "suggested": not bool(card.get("owned")),
                "qty": 1,
                "section": "main",
            }
            chosen.append(entry)
            used_names.add(card.get("name") or "")
            if entry["suggested"] and budget_remaining is not None:
                budget_remaining -= _finish_value(card)

    spell_target = 99 - counts["lands"]
    while sum(int(card.get("qty") or 1) for card in chosen) < spell_target:
        card = _pick_for_slot(
            combined_candidates,
            slot="flex",
            keywords=keywords,
            used_names=used_names,
            excluded_roles=excluded_roles,
            budget_remaining=budget_remaining,
        )
        if card is None:
            warnings.append("Could not reach target spell count from catalog.")
            break
        entry = {
            **card,
            "slot": "flex",
            "suggested": not bool(card.get("owned")),
            "qty": 1,
            "section": "main",
        }
        chosen.append(entry)
        used_names.add(card.get("name") or "")
        if entry["suggested"] and budget_remaining is not None:
            budget_remaining -= _finish_value(card)

    chosen = _fill_basic_lands(
        chosen,
        allowed_identity=allowed_identity,
        land_target=counts["lands"],
    )

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

    return {
        "commanders": commander_rows,
        "cards": chosen,
        "colorIdentity": allowed_identity,
        "stats": {
            "ownedCount": owned_count,
            "suggestedCount": suggested_count,
            "totalCards": total_cards,
            "basicLandCount": sum(
                int(card.get("qty") or 1)
                for card in chosen
                if card.get("infiniteBasic")
            ),
            "estimatedCost": estimated_cost,
        },
        "warnings": warnings,
        "validation": validation,
        "power": power,
    }
