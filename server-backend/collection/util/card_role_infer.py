"""Infer structural card roles from type line and oracle text."""

from __future__ import annotations

import re

_SEARCH_LIBRARY = re.compile(r"search your library for", re.I)
_LAND_FETCH = re.compile(
    r"search your library for .{0,80}?\b(basic\s+)?(land|plains|island|swamp|mountain|forest)\b",
    re.I,
)
_TUTOR_DEST = re.compile(
    r"(put (it|that card|them|those cards) (into your hand|onto the battlefield|"
    r"on (top|the bottom) of your library)|reveal it)",
    re.I,
)
_MANA_ADD = re.compile(
    r"(\{t\}: add\b|add (one|two|three|{[wubrgc0-9]})|add \{[wubrgc0-9/]+\})",
    re.I,
)
_DRAW = re.compile(r"\bdraw (a|one|two|three|x|\d+) cards?\b", re.I)
_COUNTER_SPELL = re.compile(r"\bcounter target (spell|activated ability|triggered ability)\b", re.I)
_REMOVAL_TARGET = re.compile(
    r"\b(destroy|exile) target (creature|permanent|artifact|enchantment|"
    r"planeswalker|vehicle|battle)\b",
    re.I,
)
_LAND_DESTRUCTION = re.compile(r"\b(destroy|exile) target land\b", re.I)
_DAMAGE_REMOVAL = re.compile(
    r"\b(deals?|deal) \d+ damage to (any target|target (creature|planeswalker|player))\b",
    re.I,
)
_BOARD_WIPE = re.compile(
    r"\b(destroy|exile) all (creatures|permanents|artifacts|enchantments|"
    r"planeswalkers|nonland permanents)\b|"
    r"\beach (player|opponent) sacrifices? all (creatures|permanents)\b",
    re.I,
)
_MLD = re.compile(
    r"\b(destroy|exile) all lands\b|"
    r"\beach (player|opponent) sacrifices? (all|a|one|two|\d+) lands?\b",
    re.I,
)
_BOUNCE = re.compile(
    r"\breturn target .{0,40}? to (its owner's|their owner's|their) hand\b",
    re.I,
)
_GRAVEYARD_HATE = re.compile(
    r"\bexile .{0,80}?from .{0,40}?graveyard|"
    r"\bcards? (in|from) .{0,40}?graveyards? (can't|cannot|lose)|"
    r"\bgraveyard (can't|cannot)|"
    r"\bif (a|an|one or more) card[s]? would be put into .{0,40}?graveyard",
    re.I,
)
_RECURSION = re.compile(
    r"\b(return|put) .{0,80}?from (your|a|target) graveyard "
    r"(to (your hand|the battlefield)|onto the battlefield)\b",
    re.I,
)
_REANIMATE = re.compile(
    r"\b(return|put) .{0,80}?from (your|a|target) graveyard "
    r"(to the battlefield|onto the battlefield)\b",
    re.I,
)
_EXTRA_TURN = re.compile(r"\btakes? an extra turn\b", re.I)
_PROTECTION_KEYWORD = re.compile(
    r"\b(hexproof|indestructible|protection from|phasing|phase out|"
    r"can't be the target|prevent all (combat )?damage)\b",
    re.I,
)
_FIGHT = re.compile(r"\bfight\b", re.I)
_MILL = re.compile(
    r"\bmills?\b|"
    r"\bput the top .{0,40}? (card|cards) of .{0,40}? library into .{0,40}?graveyard\b",
    re.I,
)
_DISCARD = re.compile(
    r"\b(target player|each (player|opponent)|that player) discards?\b",
    re.I,
)
_SAC_OUTLET = re.compile(
    r"\bsacrifice (a|another|any number of) (creature|permanent|artifact|enchantment)[s ]*:",
    re.I,
)
_TREASURE = re.compile(r"\bcreate .{0,60}\btreasure\b", re.I)
_FOG = re.compile(r"\bprevent all combat damage\b", re.I)


def _field(card: dict, *keys: str) -> str:
    for key in keys:
        value = card.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _type_line(card: dict) -> str:
    return _field(card, "type_line", "typeLine")


def _oracle(card: dict) -> str:
    return _field(card, "oracle_text", "oracleText")


def _is_land(type_line: str) -> bool:
    return bool(re.search(r"\bland\b", type_line, re.I))


def _is_equipment(type_line: str) -> bool:
    return bool(re.search(r"\bequipment\b", type_line, re.I))


def _is_aura(type_line: str) -> bool:
    return bool(re.search(r"\baura\b", type_line, re.I))


def _is_land_ramp_search(oracle: str) -> bool:
    return bool(_LAND_FETCH.search(oracle))


def _is_tutor(oracle: str) -> bool:
    if not _SEARCH_LIBRARY.search(oracle):
        return False
    if _is_land_ramp_search(oracle):
        return False
    return bool(_TUTOR_DEST.search(oracle) or re.search(r"\ba card\b", oracle, re.I))


def _is_ramp(oracle: str, type_line: str) -> bool:
    if _is_land_ramp_search(oracle):
        return True
    if _TREASURE.search(oracle):
        return True
    if _MANA_ADD.search(oracle):
        # Lands that tap for mana are not ramp; rocks/dorks/spells are.
        if _is_land(type_line) and not re.search(r"\b(put|create).{0,40}\bland\b", oracle, re.I):
            return False
        return True
    return bool(re.search(r"\bput .{0,40}\bland .{0,40}\bonto the battlefield\b", oracle, re.I))


def _is_draw(oracle: str) -> bool:
    return bool(_DRAW.search(oracle))


def _is_board_wipe(oracle: str) -> bool:
    if _MLD.search(oracle):
        return False
    return bool(_BOARD_WIPE.search(oracle))


def _is_removal(oracle: str) -> bool:
    if _MLD.search(oracle):
        return False
    return bool(
        _REMOVAL_TARGET.search(oracle)
        or _DAMAGE_REMOVAL.search(oracle)
        or _BOARD_WIPE.search(oracle)
        or _FIGHT.search(oracle)
        or _LAND_DESTRUCTION.search(oracle)
        or re.search(r"\bsacrifice target (creature|permanent)\b", oracle, re.I)
    )


def _is_bounce(oracle: str) -> bool:
    return bool(_BOUNCE.search(oracle))


def _is_counterspell(oracle: str) -> bool:
    return bool(_COUNTER_SPELL.search(oracle))


def _is_protection(oracle: str) -> bool:
    return bool(_PROTECTION_KEYWORD.search(oracle))


def _is_interaction(oracle: str) -> bool:
    return (
        _is_removal(oracle)
        or _is_counterspell(oracle)
        or _is_bounce(oracle)
        or _is_land_destruction(oracle)
        or _is_discard(oracle)
    )


def _is_land_destruction(oracle: str) -> bool:
    return bool(_LAND_DESTRUCTION.search(oracle))


def _is_recursion(oracle: str) -> bool:
    return bool(_RECURSION.search(oracle))


def _is_reanimate(oracle: str) -> bool:
    return bool(_REANIMATE.search(oracle))


def _is_graveyard_hate(oracle: str) -> bool:
    return bool(_GRAVEYARD_HATE.search(oracle))


def _is_extra_turn(oracle: str) -> bool:
    return bool(_EXTRA_TURN.search(oracle))


def _is_mld(oracle: str) -> bool:
    return bool(_MLD.search(oracle))


def _is_mill(oracle: str) -> bool:
    return bool(_MILL.search(oracle))


def _is_discard(oracle: str) -> bool:
    return bool(_DISCARD.search(oracle))


def _is_sac_outlet(oracle: str) -> bool:
    return bool(_SAC_OUTLET.search(oracle))


def _is_fog(oracle: str) -> bool:
    return bool(_FOG.search(oracle))


def _append_oracle_roles(roles: list[str], oracle: str, type_line: str) -> None:
    checks = (
        (_is_ramp(oracle, type_line), "ramp"),
        (_is_tutor(oracle), "tutor"),
        (_is_draw(oracle), "draw"),
        (_is_removal(oracle), "removal"),
        (_is_board_wipe(oracle), "board_wipe"),
        (_is_bounce(oracle), "bounce"),
        (_is_counterspell(oracle), "counterspell"),
        (_is_protection(oracle), "protection"),
        (_is_interaction(oracle), "interaction"),
        (_is_land_destruction(oracle), "land_destruction"),
        (_is_recursion(oracle), "recursion"),
        (_is_reanimate(oracle), "reanimate"),
        (_is_graveyard_hate(oracle), "graveyard_hate"),
        (_is_extra_turn(oracle), "extra_turn"),
        (_is_mld(oracle), "mass_land_destruction"),
        (_is_mill(oracle), "mill"),
        (_is_discard(oracle), "discard"),
        (_is_sac_outlet(oracle), "sac_outlet"),
        (_is_fog(oracle), "fog"),
    )
    for matched, role in checks:
        if matched:
            roles.append(role)


def infer_card_roles(card: dict) -> list[str]:
    """Return structural roles inferred from type line and oracle text."""
    type_line = _type_line(card)
    oracle = _oracle(card)
    if not type_line and not oracle:
        return []

    roles: list[str] = []
    if _is_land(type_line):
        roles.append("land")
    if _is_equipment(type_line):
        roles.append("equipment")
    if _is_aura(type_line):
        roles.append("aura")
    if oracle:
        _append_oracle_roles(roles, oracle, type_line)
    return roles
