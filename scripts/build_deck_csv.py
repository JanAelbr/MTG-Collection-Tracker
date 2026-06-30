"""Generate deck CSV files with Scryfall print columns.

Run from repo root:
    python scripts/build_deck_csv.py
"""

import sqlite3
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.config import DB_PATH, DECKS_DIR
from lib.deck_csv import (
    deck_name_from_slug,
    read_deck_card_rows,
    upsert_deck_manifest_entry,
    write_deck_card_rows,
)
from lib.deck_scryfall import resolve_scryfall_print
from lib.precon_decklists import PRECON_DECK_DEFINITIONS
from lib.run_log import configure_logging, get_logger

log = get_logger(__name__)
DECK_DEFINITIONS = (
    {
        "slug": "dance_of_the_elements",
        "deck_name": "Dance of the Elements",
        "preferred_sets": ("ecc", "ltc", "ltr"),
        "rows": (
            ("Ashling, the Limitless", 1, "commander"),
            ("Mass of Mysteries", 1, "commander"),
            ("Avenger of Zendikar", 1, "main"),
            ("Bane of Progress", 1, "main"),
            ("Belonging", 1, "main"),
            ("Cavalier of Thorns", 1, "main"),
            ("Eclipsed Flamekin", 1, "main"),
            ("Endurance", 1, "main"),
            ("Faeburrow Elder", 1, "main"),
            ("Flamebraider", 1, "main"),
            ("Foundation Breaker", 1, "main"),
            ("Fury", 1, "main"),
            ("Greenwarden of Murasa", 1, "main"),
            ("Horde of Notions", 1, "main"),
            ("Impulsivity", 1, "main"),
            ("Incandescent Soulstoke", 1, "main"),
            ("Ingot Chewer", 1, "main"),
            ("Jegantha, the Wellspring", 1, "main"),
            ("Jubilation", 1, "main"),
            ("Lamentation", 1, "main"),
            ("Maelstrom Wanderer", 1, "main"),
            ("Muldrotha, the Gravetide", 1, "main"),
            ("Mulldrifter", 1, "main"),
            ("Omnath, Locus of Rage", 1, "main"),
            ("Omnath, Locus of the Roil", 1, "main"),
            ("Realmwalker", 1, "main"),
            ("Risen Reef", 1, "main"),
            ("Selvala, Heart of the Wilds", 1, "main"),
            ("Shimmercreep", 1, "main"),
            ("Shriekmaw", 1, "main"),
            ("Slithermuse", 1, "main"),
            ("Smokebraider", 1, "main"),
            ("Subterfuge", 1, "main"),
            ("Titan of Industry", 1, "main"),
            ("Vernal Sovereign", 1, "main"),
            ("Yarok, the Desecrated", 1, "main"),
            ("Arcane Signet", 1, "main"),
            ("Chromatic Lantern", 1, "main"),
            ("Fellwar Stone", 1, "main"),
            ("Sol Ring", 1, "main"),
            ("Timeless Lotus", 1, "main"),
            ("Abundant Growth", 1, "main"),
            ("Cream of the Crop", 1, "main"),
            ("Descendants' Fury", 1, "main"),
            ("Fertile Ground", 1, "main"),
            ("Garruk's Uprising", 1, "main"),
            ("Hoofprints of the Stag", 1, "main"),
            ("Springleaf Parade", 1, "main"),
            ("Crib Swap", 1, "main"),
            ("Kindred Summons", 1, "main"),
            ("Path to Exile", 1, "main"),
            ("Reality Shift", 1, "main"),
            ("Return of the Wildspeaker", 1, "main"),
            ("Blasphemous Act", 1, "main"),
            ("Cultivate", 1, "main"),
            ("Distant Melody", 1, "main"),
            ("Elemental Spectacle", 1, "main"),
            ("Haunting Voyage", 1, "main"),
            ("Kodama's Reach", 1, "main"),
            ("Shatter the Sky", 1, "main"),
            ("Abundant Countryside", 1, "main"),
            ("Ancient Ziggurat", 1, "main"),
            ("Command Tower", 1, "main"),
            ("Exotic Orchard", 1, "main"),
            ("Flamekin Village", 1, "main"),
            ("Forest", 8, "main"),
            ("Frontier Bivouac", 1, "main"),
            ("Island", 2, "main"),
            ("Jungle Shrine", 1, "main"),
            ("Mountain", 2, "main"),
            ("Opal Palace", 1, "main"),
            ("Opulent Palace", 1, "main"),
            ("Path of Ancestry", 1, "main"),
            ("Plains", 2, "main"),
            ("Primal Beyond", 1, "main"),
            ("Raging Ravine", 1, "main"),
            ("Rain-Slicked Copse", 1, "main"),
            ("Sandsteppe Citadel", 1, "main"),
            ("Savage Lands", 1, "main"),
            ("Seaside Citadel", 1, "main"),
            ("Secluded Courtyard", 1, "main"),
            ("Sodden Verdure", 1, "main"),
            ("Swamp", 2, "main"),
            ("Thriving Bluff", 1, "main"),
            ("Thriving Grove", 1, "main"),
            ("Thriving Heath", 1, "main"),
            ("Thriving Isle", 1, "main"),
            ("Thriving Moor", 1, "main"),
            ("Unclaimed Territory", 1, "main"),
        ),
    },
    {
        "slug": "world_shaper",
        "deck_name": "World Shaper",
        "preferred_sets": ("eoc", "ltc", "ltr"),
        "rows": (
            ("Hearthhull, the Worldseed", 1, "commander"),
            ("Szarel, Genesis Shepherd", 1, "commander"),
            ("Aftermath Analyst", 1, "main"),
            ("Augur of Autumn", 1, "main"),
            ("Baloth Prime", 1, "main"),
            ("Braids, Arisen Nightmare", 1, "main"),
            ("Centaur Vinecrasher", 1, "main"),
            ("Eumidian Wastewaker", 1, "main"),
            ("Evendo Brushrazer", 1, "main"),
            ("God-Eternal Bontu", 1, "main"),
            ("Groundskeeper", 1, "main"),
            ("Horizon Explorer", 1, "main"),
            ("Juri, Master of the Revue", 1, "main"),
            ("Korvold, Fae-Cursed King", 1, "main"),
            ("Loamcrafter Faun", 1, "main"),
            ("Mayhem Devil", 1, "main"),
            ("Mazirek, Kraul Death Priest", 1, "main"),
            ("Moraug, Fury of Akoum", 1, "main"),
            ("Multani, Yavimaya's Avatar", 1, "main"),
            ("Omnath, Locus of Rage", 1, "main"),
            ("Oracle of Mul Daya", 1, "main"),
            ("Rampaging Baloths", 1, "main"),
            ("Satyr Wayfinder", 1, "main"),
            ("Scouring Swarm", 1, "main"),
            ("Soul of Windgrace", 1, "main"),
            ("Springbloom Druid", 1, "main"),
            ("Sprouting Goblin", 1, "main"),
            ("The Gitrog Monster", 1, "main"),
            ("Tireless Tracker", 1, "main"),
            ("Titania, Protector of Argoth", 1, "main"),
            ("Uurg, Spawn of Turg", 1, "main"),
            ("World Breaker", 1, "main"),
            ("Arcane Signet", 1, "main"),
            ("Exploration Broodship", 1, "main"),
            ("Hammer of Purphoros", 1, "main"),
            ("Sol Ring", 1, "main"),
            ("Binding the Old Gods", 1, "main"),
            ("Beast Within", 1, "main"),
            ("Harrow", 1, "main"),
            ("Infernal Grasp", 1, "main"),
            ("Putrefy", 1, "main"),
            ("Rakdos Charm", 1, "main"),
            ("Roiling Regrowth", 1, "main"),
            ("Tear Asunder", 1, "main"),
            ("Windgrace's Judgment", 1, "main"),
            ("Blasphemous Act", 1, "main"),
            ("Cultivate", 1, "main"),
            ("Escape to the Wilds", 1, "main"),
            ("Farseek", 1, "main"),
            ("Formless Genesis", 1, "main"),
            ("Gaze of Granite", 1, "main"),
            ("Nature's Lore", 1, "main"),
            ("Night's Whisper", 1, "main"),
            ("Pest Infestation", 1, "main"),
            ("Planetary Annihilation", 1, "main"),
            ("Skyshroud Claim", 1, "main"),
            ("Splendid Reclamation", 1, "main"),
            ("Worldsoul's Rage", 1, "main"),
            ("Bojuka Bog", 1, "main"),
            ("Cabaretti Courtyard", 1, "main"),
            ("Canyon Slough", 1, "main"),
            ("Cinder Glade", 1, "main"),
            ("Command Tower", 1, "main"),
            ("Dakmor Salvage", 1, "main"),
            ("Escape Tunnel", 1, "main"),
            ("Eumidian Hatchery", 1, "main"),
            ("Evolving Wilds", 1, "main"),
            ("Fabled Passage", 1, "main"),
            ("Festering Thicket", 1, "main"),
            ("Forest", 8, "main"),
            ("Karplusan Forest", 1, "main"),
            ("Llanowar Wastes", 1, "main"),
            ("Maestros Theater", 1, "main"),
            ("Mountain", 3, "main"),
            ("Mountain Valley", 1, "main"),
            ("Myriad Landscape", 1, "main"),
            ("Riveteers Overlook", 1, "main"),
            ("Rocky Tar Pit", 1, "main"),
            ("Sheltered Thicket", 1, "main"),
            ("Smoldering Marsh", 1, "main"),
            ("Sulfurous Springs", 1, "main"),
            ("Swamp", 5, "main"),
            ("Terramorphic Expanse", 1, "main"),
            ("Twilight Mire", 1, "main"),
            ("Vernal Fen", 1, "main"),
            ("Viridescent Bog", 1, "main"),
            ("Wastes", 1, "main"),
        ),
    },
)

NAME_ONLY_DECKS = (
    {
        "slug": "wise_mothman",
        "preferred_sets": ("pip", "ltc", "ltr"),
    },
)


# Look up a card name from the local catalog when a deck CSV only stores prints.
def card_name_from_print(set_code: str, collector_number: str) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT name FROM cards
            WHERE set_code = ? AND collector_number = ?
            """,
            (set_code.upper(), collector_number),
        ).fetchone()
    return row[0] if row else None


# Read card rows from an existing deck CSV for Scryfall re-resolution.
def load_name_only_deck_rows(deck_file: Path) -> tuple[str, list[tuple[str, int, str]]]:
    deck_name = deck_name_from_slug(deck_file.stem)
    rows: list[tuple[str, int, str]] = []
    for row in read_deck_card_rows(deck_file):
        card_name = row.get("card_name")
        if not card_name and row.get("set_code") and row.get("collector_number"):
            card_name = card_name_from_print(row["set_code"], row["collector_number"])
        if not card_name:
            continue
        rows.append((card_name, row["qty"], row["section"]))
    return deck_name, rows


# Write one deck CSV with resolved Scryfall print columns.
def write_deck_csv(deck: dict) -> tuple[Path, list[str]]:
    deck_file = DECKS_DIR / f"{deck['slug']}.csv"
    preferred_sets = tuple(code.lower() for code in deck["preferred_sets"])
    missing: list[str] = []
    total = len(deck["rows"])
    log.info(
        "Resolving %s (%s cards, preferred sets: %s)",
        deck["deck_name"],
        total,
        ", ".join(code.upper() for code in preferred_sets),
    )

    resolved_rows: list[dict] = []
    for index, (card_name, qty, section) in enumerate(deck["rows"], start=1):
        resolved = resolve_scryfall_print(card_name, preferred_sets)
        time.sleep(0.12)
        if resolved is None:
            missing.append(card_name)
            set_code = ""
            collector_number = ""
            log.warning("  [%s/%s] No print found: %s", index, total, card_name)
        else:
            set_code, collector_number = resolved
            log.debug(
                "  [%s/%s] %s -> %s-%s",
                index,
                total,
                card_name,
                set_code,
                collector_number,
            )
        resolved_rows.append({
            "set_code": set_code,
            "collector_number": collector_number,
            "finish": 0,
            "qty": qty,
            "owned_qty": min(qty, 1),
            "section": section,
        })

    write_deck_card_rows(deck_file, resolved_rows)

    upsert_deck_manifest_entry(
        deck["slug"],
        deck["deck_name"],
        deck_file.name,
    )

    if missing:
        log.warning(
            "Wrote %s with %s unresolved card(s)",
            deck_file.name,
            len(missing),
        )
    else:
        log.info("Wrote %s (%s rows)", deck_file.name, total)
    return deck_file, missing


# Generate all configured deck CSV files.
def main(selected_slugs: set[str] | None = None, *, verbose: bool = False) -> None:
    configure_logging(verbose=verbose)
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    if selected_slugs:
        log.info("Building deck CSV(s): %s", ", ".join(sorted(selected_slugs)))
    else:
        log.info("Building all configured deck CSV files")

    for deck in (*DECK_DEFINITIONS, *PRECON_DECK_DEFINITIONS):
        if selected_slugs and deck["slug"] not in selected_slugs:
            continue
        deck_file, missing = write_deck_csv(deck)
        if missing:
            log.warning("  Missing prints: %s", ", ".join(missing))

    for deck in NAME_ONLY_DECKS:
        if selected_slugs and deck["slug"] not in selected_slugs:
            continue
        source = DECKS_DIR / f"{deck['slug']}.csv"
        if not source.is_file():
            log.warning("Skipping missing deck file: %s", source.name)
            continue
        deck_name, rows = load_name_only_deck_rows(source)
        deck_file, missing = write_deck_csv(
            {
                "slug": deck["slug"],
                "deck_name": deck_name,
                "preferred_sets": deck["preferred_sets"],
                "rows": rows,
            }
        )
        if missing:
            log.warning("  Missing prints: %s", ", ".join(missing))

    log.info("Deck CSV generation complete")


if __name__ == "__main__":
    slugs = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    verbose = "--verbose" in slugs or "-v" in slugs
    if slugs:
        slugs.discard("--verbose")
        slugs.discard("-v")
        if not slugs:
            slugs = None
    main(slugs, verbose=verbose)
