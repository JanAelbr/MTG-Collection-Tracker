"""Generate scripts/lib/precon_decklists.py from official deck list sources."""

from __future__ import annotations

import re
from pathlib import Path

from lib.config import REPO_ROOT, SCRIPTS_DIR
from lib.run_log import configure_logging, get_logger

OUTPUT = SCRIPTS_DIR / "lib" / "precon_decklists.py"
log = get_logger(__name__)

WARHAMMER_WIKI = REPO_ROOT / "data" / "decks" / "sources" / "warhammer_40k_wiki.txt"
NCC_WIKI = REPO_ROOT / "data" / "decks" / "sources" / "new_capenna_commander_wiki.txt"
CLB_WIKI = REPO_ROOT / "data" / "decks" / "sources" / "clb_commander_wiki.txt"

WIKI_BACKUP_COMMANDERS = {
    "tyranid_swarm": "Magus Lucea Kane",
    "the_ruinous_powers": "Be'lakor, the Dark Master",
    "necron_dynasties": "Imotekh the Stormlord",
    "forces_of_the_imperium": "Marneus Calgar",
    "obscura_operation": "Tivit, Seller of Secrets",
    "maestros_massacre": "Syrix, Carrier of the Flame",
    "mind_flayarrrs": "Zellix, Sanity Flayer",
}

WIKI_DECK_GROUPS = (
    {
        "source": WARHAMMER_WIKI,
        "preferred_sets": ("40k",),
        "decks": (
            ("tyranid_swarm", "Tyranid Swarm", "Tyranid Swarm"),
            ("the_ruinous_powers", "The Ruinous Powers", "The Ruinous Powers"),
            ("necron_dynasties", "Necron Dynasties", "Necron Dynasties"),
            ("forces_of_the_imperium", "Forces of the Imperium", "Forces of the Imperium"),
        ),
    },
    {
        "source": NCC_WIKI,
        "preferred_sets": ("ncc", "snc"),
        "boundary_titles": (
            "Obscura Operation",
            "Maestros Massacre",
            "Riveteers Rampage",
            "Cabaretti Cacophony",
            "Bedecked Brokers",
        ),
        "decks": (
            ("obscura_operation", "Obscura Operation", "Obscura Operation"),
            ("maestros_massacre", "Maestros Massacre", "Maestros Massacre"),
        ),
    },
    {
        "source": CLB_WIKI,
        "preferred_sets": ("clb",),
        "boundary_titles": (
            "Mind Flayarrrs",
            "Draconic Dissent",
            "Party Time",
            "Exit from Exile",
        ),
        "decks": (
            ("mind_flayarrrs", "Mind Flayarrrs", "Mind Flayarrrs"),
        ),
    },
)

LOTR_DECKS = (
    (
        "riders_of_rohan",
        "Riders of Rohan",
        ("Éowyn, Shieldmaiden", "Aragorn, King of Gondor"),
        "1 Éowyn, Shieldmaiden 1 Aragorn, King of Gondor 1 Beregond of the Guard 1 Champions of Minas Tirith 1 Gilraen, Dúnedain Protector 1 Grey Host Reinforcements 1 Lossarnach Captain 1 Archivist of Gondor 1 Denethor, Stone Seer 1 Fealty to the Realm 1 Call for Aid 1 Gimli of the Glittering Caves 1 Boromir, Gondor's Hope 1 Éomer, King of Rohan 1 Faramir, Steward of Gondor 1 Forth Eorlingas! 1 Oath of Eorl 1 Riders of Rohan 1 Taunt from the Rampart 1 Crown of Gondor 1 Bastion Protector 1 Dearly Departed 1 Frontline Medic 1 Increasing Devotion 1 Marshal's Anthem 1 Selfless Squire 1 Unbreakable Formation 1 Verge Rangers 1 Visions of Glory 1 Weathered Wayfarer 1 Combat Celebrant 1 Court of Ire 1 Earthquake 1 Flamerush Rider 1 Frontier Warmonger 1 Harsh Mentor 1 Shared Animosity 1 Zealous Conscripts 1 Supreme Verdict 1 Door of Destinies 1 Vanquisher's Banner 1 Battlefield Forge 1 Clifftop Retreat 1 Exotic Orchard 1 Furycalm Snarl 1 Glacial Fortress 1 Port Town 1 Prairie Stream 1 Sulfur Falls 1 Throne of the High City 1 Windbrisk Heights 1 Lost to Legend 1 Erkenbrand, Lord of Westfold 1 Banishing Light 1 Fiend Hunter 1 Palace Jailer 1 Path to Exile 1 Sunset Revelry 1 Swords to Plowshares 1 Village Bell-Ringer 1 Prince Imrahil the Fair 1 Humble Defector 1 Théoden, King of Rohan 1 Arcane Signet 1 Commander's Sphere 1 Heirloom Blade 1 Herald's Horn 1 Sol Ring 1 Talisman of Conviction 1 Talisman of Progress 1 Thought Vessel 1 Wayfarer's Bauble 1 Command Tower 1 Evolving Wilds 1 Field of Ruin 1 Path of Ancestry 1 Rogue's Passage 1 Secluded Courtyard 1 Terramorphic Expanse 1 Tranquil Cove 1 Wind-Scarred Crag 9 Plains 5 Island 5 Mountain",
    ),
    (
        "food_and_fellowship",
        "Food and Fellowship",
        ("Frodo, Adventurous Hobbit", "Sam, Loyal Attendant"),
        "1 Frodo, Adventurous Hobbit 1 Sam, Loyal Attendant 1 Field-Tested Frying Pan 1 The Gaffer 1 Gwaihir, Greatest of the Eagles 1 Of Herbs and Stewed Rabbit 1 Gollum, Obsessed Stalker 1 Lobelia, Defender of Bag End 1 Rapacious Guest 1 Assemble the Entmoot 1 Feasting Hobbit 1 Motivated Pony 1 Prize Pig 1 Banquet Guests 1 Bilbo, Birthday Celebrant 1 Farmer Cotton 1 Merry, Warden of Isengard 1 Pippin, Warden of Isengard 1 Treebeard, Gracious Host 1 Hithlain Rope 1 Call for Unity 1 Dawn of Hope 1 Dusk 1 Fell the Mighty 1 Fumigate 1 Mentor of the Meek 1 Sanguine Bond 1 Toxic Deluge 1 Birds of Paradise 1 Gilded Goose 1 Woodfall Primus 1 Anguished Unmaking 1 Chromatic Lantern 1 Trading Post 1 Well of Lost Dreams 1 Brushland 1 Canopy Vista 1 Exotic Orchard 1 Fortified Village 1 Isolated Chapel 1 Murmuring Bosk 1 Necroblossom Snarl 1 Scattered Groves 1 Shineshadow Snarl 1 Sunpetal Grove 1 Woodland Cemetery 1 Eagles of the North 1 Landroval, Horizon Witness 1 Rosie Cotton of South Lane 1 Shire Shirriff 1 Mirkwood Bats 1 Generous Ent 1 Path to Exile 1 Swords to Plowshares 1 Revive the Shire 1 Butterbur, Bree Innkeeper 1 Crypt Incursion 1 Go for the Throat 1 Night's Whisper 1 Cultivate 1 Essence Warden 1 Farseek 1 Great Oak Guardian 1 Harmonize 1 Orchard Strider 1 Prosperous Innkeeper 1 Shire Terrace 1 Tireless Provisioner 1 Mortify 1 Savvy Hunter 1 Arcane Signet 1 Commander's Sphere 1 Pristine Talisman 1 Sol Ring 1 Access Tunnel 1 Ash Barrens 1 Command Tower 1 Evolving Wilds 1 Ghost Quarter 1 Graypelt Refuge 1 Path of Ancestry 1 Rogue's Passage 1 Sandsteppe Citadel 1 Scoured Barrens 4 Plains 4 Swamp 8 Forest",
    ),
    (
        "elven_council",
        "Elven Council",
        ("Galadriel, Elven-Queen", "Gandalf, Westward Voyager"),
        "1 Galadriel, Elven-Queen 1 Gandalf, Westward Voyager 1 Raise the Palisade 1 Trap the Trespassers 1 Arwen, Weaver of Hope 1 Galadhrim Ambush 1 Haldir, Lórien Lieutenant 1 Legolas Greenleaf 1 Mirkwood Elk 1 Travel Through Caradhras 1 Windswift Slice 1 Círdan the Shipwright 1 Elrond of the White Council 1 Erestor of the Council 1 Mirkwood Trapper 1 Radagast, Wizard of Wilds 1 Sail into the West 1 Song of Eärendil 1 Lothlórien Blade 1 Model of Unity 1 Colossal Whale 1 Devastation Tide 1 Mystic Confluence 1 Plea for Power 1 Swan Song 1 Asceticism 1 Elvish Archdruid 1 Elvish Piper 1 Elvish Warmaster 1 Genesis Wave 1 Heroic Intervention 1 Hornet Queen 1 Inscription of Abundance 1 Overwhelming Stampede 1 Realm Seekers 1 Seeds of Renewal 1 Sylvan Offering 1 Exotic Orchard 1 Flooded Grove 1 Hinterland Harbor 1 Rejuvenating Springs 1 Vineglimmer Snarl 1 Lórien Revealed 1 Celeborn the Wise 1 Elven Farsight 1 Wose Pathfinder 1 Learn from the Past 1 Opt 1 Preordain 1 Arbor Elf 1 Beast Within 1 Cultivate 1 Elvish Mystic 1 Elvish Visionary 1 Farhaven Elf 1 Mirror of Galadriel 1 Lignify 1 Paradise Druid 1 Rampant Growth 1 Reclamation Sage 1 Wood Elves 1 Growth Spiral 1 Arcane Signet 1 Commander's Sphere 1 Lightning Greaves 1 Sol Ring 1 Whispersilk Cloak 1 Ash Barrens 1 Command Tower 1 Field of Ruin 1 Lonely Sandbar 1 Thornwood Falls 1 Tranquil Thicket 1 Woodland Stream 11 Island 15 Forest",
    ),
    (
        "the_hosts_of_mordor",
        "The Hosts of Mordor",
        ("Sauron, Lord of the Rings", "Saruman, the White Hand"),
        "1 Sauron, Lord of the Rings 1 Saruman, the White Hand 1 Corsairs of Umbar 1 Monstrosity of the Lake 1 Subjugate the Hobbits 1 Shelob, Dread Weaver 1 Cavern-Hoard Dragon 1 Orcish Siegemaster 1 Rampaging War Mammoth 1 The Balrog of Moria 1 Gríma, Saruman's Footman 1 In the Darkness Bind Them 1 Lidless Gaze 1 Lord of the Nazgûl 1 Moria Scavenger 1 Summons of Saruman 1 Too Greedily, Too Deep 1 Wake the Dragon 1 Relic of Sauron 1 The Black Gate 1 Decree of Pain 1 Languish 1 Living Death 1 Reanimate 1 Blasphemous Act 1 Goblin Dark-Dwellers 1 Inferno Titan 1 Knollspine Dragon 1 Scourge of the Throne 1 Siege-Gang Commander 1 Treasure Nabber 1 Hostage Taker 1 Notion Thief 1 Choked Estuary 1 Desolate Lighthouse 1 Dragonskull Summit 1 Drowned Catacomb 1 Foreboding Ruins 1 Frostboil Snarl 1 Smoldering Marsh 1 Sulfur Falls 1 Sulfurous Springs 1 Sunken Hollow 1 Underground River 1 Treason of Isengard 1 Bitter Downfall 1 Troll of Khazad-dûm 1 Voracious Fell Beast 1 Fiery Inscription 1 Grishnákh, Brash Instigator 1 Arcane Denial 1 Boon of the Wish-Giver 1 Consider 1 Deep Analysis 1 Fact or Fiction 1 Forbidden Alchemy 1 Feed the Swarm 1 Merciless Executioner 1 Revenge of Ravens 1 Anger 1 Faithless Looting 1 The Mouth of Sauron 1 Goblin Cratermaker 1 Guttersnipe 1 Shiny Impetus 1 Thrill of Possibility 1 Extract from Darkness 1 Arcane Signet 1 Basalt Monolith 1 Commander's Sphere 1 Everflowing Chalice 1 Mind Stone 1 Sol Ring 1 Worn Powerstone 1 Command Tower 1 Crumbling Necropolis 1 Evolving Wilds 1 Field of Ruin 1 Path of Ancestry 1 Rogue's Passage 1 Terramorphic Expanse 6 Island 6 Swamp 7 Mountain",
    ),
)


def parse_wizards_line(line: str, commanders: tuple[str, ...]) -> list[tuple[str, int, str]]:
    tokens = line.strip().split()
    rows: list[tuple[str, int, str]] = []
    index = 0
    commander_names = set(commanders)
    while index < len(tokens):
        qty = int(tokens[index])
        index += 1
        name_parts: list[str] = []
        while index < len(tokens) and not tokens[index].isdigit():
            name_parts.append(tokens[index])
            index += 1
        name = " ".join(name_parts)
        section = "commander" if name in commander_names else "main"
        rows.append((name, qty, section))
    return rows


def parse_wiki_deck(
    text: str,
    title: str,
    slug: str,
    sibling_titles: tuple[str, ...],
) -> list[tuple[str, int, str]]:
    start = text.find(f"### {title}")
    if start < 0:
        start = text.find(f"{title}\nDownload")
    end = len(text)
    for other_title in sibling_titles:
        if other_title != title:
            pos = text.find(f"### {other_title}", start + 1)
            if pos > start:
                end = min(end, pos)
    chunk = text[start:end]
    backup = WIKI_BACKUP_COMMANDERS.get(slug)
    rows: list[tuple[str, int, str]] = []
    section = "main"
    for line in chunk.splitlines():
        if line.startswith("#### Commander"):
            section = "commander"
            continue
        if line.startswith("#### "):
            section = "main"
        match = re.match(r"^(\d+)\[([^\]]+)\]", line.strip())
        if not match:
            continue
        qty = int(match.group(1))
        name = match.group(2).replace("+", " ")
        card_section = section
        if backup and name == backup:
            card_section = "commander"
        rows.append((name, qty, card_section))
    return rows


def format_rows(rows: list[tuple[str, int, str]]) -> str:
    lines = ["        \"rows\": ("]
    for name, qty, section in rows:
        lines.append(f"            ({name!r}, {qty}, {section!r}),")
    lines.append("        ),")
    return "\n".join(lines)


def build_definitions() -> list[dict]:
    definitions: list[dict] = []

    for group in WIKI_DECK_GROUPS:
        wiki_text = group["source"].read_text(encoding="utf-8")
        boundary_titles = group.get(
            "boundary_titles",
            tuple(title for _, _, title in group["decks"]),
        )
        for slug, deck_name, wiki_title in group["decks"]:
            rows = parse_wiki_deck(wiki_text, wiki_title, slug, boundary_titles)
            total = sum(qty for _, qty, _ in rows)
            if total != 100:
                raise ValueError(f"{deck_name} has {total} cards, expected 100")
            definitions.append({
                "slug": slug,
                "deck_name": deck_name,
                "preferred_sets": group["preferred_sets"],
                "rows": rows,
            })

    for slug, deck_name, commanders, line in LOTR_DECKS:
        rows = parse_wizards_line(line, commanders)
        total = sum(qty for _, qty, _ in rows)
        if total != 100:
            raise ValueError(f"{deck_name} has {total} cards, expected 100")
        definitions.append({
            "slug": slug,
            "deck_name": deck_name,
            "preferred_sets": ("ltc", "ltr"),
            "rows": rows,
        })

    return definitions


def write_module(definitions: list[dict]) -> None:
    parts = [
        '"""Official preconstructed Commander deck lists. Generated by generate_precon_decklists.py."""',
        "",
        "PRECON_DECK_DEFINITIONS = (",
    ]
    for deck in definitions:
        parts.extend([
            "    {",
            f"        \"slug\": {deck['slug']!r},",
            f"        \"deck_name\": {deck['deck_name']!r},",
            f"        \"preferred_sets\": {deck['preferred_sets']!r},",
            format_rows(deck["rows"]),
            "    },",
        ])
    parts.append(")")
    parts.append("")
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    configure_logging(verbose=False)
    log.info("Generating precon deck list definitions")
    definitions = build_definitions()
    write_module(definitions)
    log.info("Wrote %s (%s decks)", OUTPUT, len(definitions))


if __name__ == "__main__":
    main()
