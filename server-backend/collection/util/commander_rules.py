from util.card_metadata import (
    card_matches_color_identity,
    is_commander_format_legal,
    is_legendary_commander_candidate,
    parse_card_colors,
    parse_card_legalities,
)

COMMANDER_BANNED = frozenset({
    "Ancestral Recall",
    "Balance",
    "Biorhythm",
    "Black Lotus",
    "Channel",
    "Chaos Orb",
    "Coalition Victory",
    "Emrakul, the Aeons Torn",
    "Erayo, Soratami Ascendant",
    "Falling Star",
    "Fastbond",
    "Golos, Tireless Pilgrim",
    "Griselbrand",
    "Hullbreacher",
    "Iona, Shield of Emeria",
    "Jeweled Lotus",
    "Jin-Gitaxias, Core Augur",
    "Karakas",
    "Leovold, Emissary of Trest",
    "Library of Alexandria",
    "Limited Resources",
    "Lutri, the Spellchaser",
    "Mox Emerald",
    "Mox Jet",
    "Mox Pearl",
    "Mox Ruby",
    "Mox Sapphire",
    "Nadu, Winged Wisdom",
    "Panoptic Mirror",
    "Primeval Titan",
    "Prophet of Kruphix",
    "Recurring Nightmare",
    "Rofellos, Llanowar Emissary",
    "Shahrazad",
    "Sundering Titan",
    "Sway of the Stars",
    "Sylvan Primordial",
    "Time Vault",
    "Time Walk",
    "Tinker",
    "Tolarian Academy",
    "Trade Secrets",
    "Upheaval",
    "Yawgmoth's Bargain",
})


def is_banned_in_commander(card_name: str) -> bool:
    return str(card_name or "").strip() in COMMANDER_BANNED


def commander_color_identity(commander_rows: list[dict]) -> list[str]:
    identity: set[str] = set()
    for row in commander_rows:
        colors = row.get("color_identity") or row.get("colorIdentity") or row.get("colors") or []
        identity.update(parse_card_colors(colors))
    return sorted(identity, key=lambda color: "WUBRG".index(color) if color in "WUBRG" else 99)


def card_is_legal_for_deck(card: dict, allowed_identity: list[str]) -> bool:
    name = str(card.get("name") or card.get("card_name") or "").strip()
    if is_banned_in_commander(name):
        return False
    legalities = card.get("legalities")
    if isinstance(legalities, str):
        legalities = parse_card_legalities(legalities)
    elif not isinstance(legalities, dict):
        legalities = parse_card_legalities(card.get("legalities"))
    if legalities and not is_commander_format_legal(legalities):
        return False
    identity = card.get("color_identity") or card.get("colorIdentity") or []
    if isinstance(identity, str):
        identity = parse_card_colors(identity)
    return card_matches_color_identity(identity, allowed_identity)


def validate_commander_deck(
    cards: list[dict],
    *,
    commanders: list[dict] | None = None,
    min_maindeck: int = 99,
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    allowed_identity = commander_color_identity(commanders or [])
    main_cards = [card for card in cards if str(card.get("section") or "main") == "main"]
    commander_cards = [card for card in cards if str(card.get("section") or "") == "commander"]
    all_relevant = main_cards + commander_cards

    name_counts: dict[str, int] = {}
    for card in main_cards:
        name = str(card.get("name") or card.get("card_name") or "").strip()
        if not name:
            continue
        is_basic = bool(card.get("is_basic_land") or card.get("isBasicLand"))
        if is_basic:
            continue
        name_counts[name] = name_counts.get(name, 0) + int(card.get("qty") or 1)

    for name, count in name_counts.items():
        if count > 1:
            errors.append(f"Singleton violation: {name} appears {count} times.")

    main_qty = sum(int(card.get("qty") or 1) for card in main_cards)
    if main_qty < min_maindeck:
        warnings.append(f"Main deck has {main_qty} cards; Commander expects {min_maindeck}.")

    for commander in commander_cards:
        type_line = str(commander.get("type_line") or commander.get("typeLine") or "")
        if not is_legendary_commander_candidate(type_line):
            errors.append(f"{commander.get('name') or 'Commander'} is not a legendary creature or planeswalker.")

    illegal = []
    for card in all_relevant:
        if not card_is_legal_for_deck(card, allowed_identity):
            illegal.append(str(card.get("name") or card.get("card_name") or "Unknown"))
    if illegal:
        errors.append(f"{len(illegal)} card(s) outside color identity or banned.")

    land_count = sum(
        int(card.get("qty") or 1)
        for card in main_cards
        if str(card.get("card_type") or card.get("cardType") or "").lower() == "land"
        or bool(card.get("is_basic_land") or card.get("isBasicLand"))
    )
    if land_count < 30:
        warnings.append(f"Only {land_count} lands; most Commander decks run 33–40.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "colorIdentity": allowed_identity,
        "mainCount": main_qty,
        "landCount": land_count,
    }
