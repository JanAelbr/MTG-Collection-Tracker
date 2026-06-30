"""Build precon deck CSV files using Scryfall prints from the correct product sets."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_precon_decklists import parse_wiki_deck
from lib.config import REPO_ROOT
from lib.deck_csv import upsert_deck_manifest_entry, write_deck_card_rows
from lib.deck_scryfall import PrintResolver, build_deck_rows_from_scryfall
from lib.deck_wiki import extract_deck_block, fetch_wikitext, parse_deck_block
from lib.run_log import configure_logging, get_logger

log = get_logger(__name__)

SOURCES = REPO_ROOT / "data" / "decks" / "sources"
CLB_WIKI = SOURCES / "clb_commander_wiki.txt"

DEFAULT_PURCHASE_PRICE = 50.0

# Scryfall set codes for each commander precon product (in search order).
DECK_SPECS = (
    {
        "slug": "sedris_the_traitor_king",
        "name": "Sedris, the Traitor King",
        "source": "wiki",
        "wiki_page": "Commander_2013/Mind_Seize",
        "deck_title": "Mind Seize",
        "commanders": ("Nekusar, the Mindrazer",),
        "precon_sets": ("C13",),
    },
    {
        "slug": "nekusar",
        "name": "Nekusar",
        "source": "wiki",
        "wiki_page": "Commander_2013/Mind_Seize",
        "deck_title": "Mind Seize",
        "commanders": ("Nekusar, the Mindrazer",),
        "precon_sets": ("C13",),
    },
    {
        "slug": "willowdusk",
        "name": "Willowdusk",
        "source": "wiki",
        "wiki_page": "Commander_2021/Witherbloom_Witchcraft",
        "deck_title": "Witherbloom Witchcraft",
        "commanders": ("Willowdusk, Essence Seer",),
        "precon_sets": ("C21", "STX"),
    },
    {
        "slug": "prosper_tome_bound",
        "name": "Prosper, Tome-Bound",
        "source": "clb_wiki",
        "wiki_title": "Exit from Exile",
        "boundary_titles": ("Draconic Dissent", "Party Time", "Mind Flayarrrs"),
        "commanders": ("Prosper, Tome-Bound",),
        "commander_as": "Faldorn, Dread Wolf Herald",
        "precon_sets": ("CLB",),
    },
    {
        "slug": "henzie",
        "name": "Henzie",
        "source": "wiki",
        "wiki_page": "Streets_of_New_Capenna/Commander",
        "deck_title": "Riveteers Rampage",
        "commanders": ('Henzie "Toolbox" Torre',),
        "precon_sets": ("NCC", "SNC"),
    },
    {
        "slug": "arahbo",
        "name": "Arahbo",
        "source": "wiki",
        "wiki_page": "March_of_the_Machine/Commander",
        "deck_title": "Call for Backup",
        "commanders": ("Arahbo, Roar of the World",),
        "precon_sets": ("MOC",),
        "basic_fallback_sets": ("MOM",),
    },
    {
        "slug": "umbris",
        "name": "Umbris",
        "source": "clb_wiki",
        "wiki_title": "Mind Flayarrrs",
        "boundary_titles": ("Draconic Dissent", "Party Time", "Exit from Exile"),
        "commanders": ("Zellix, Sanity Flayer",),
        "precon_sets": ("CLB",),
    },
    {
        "slug": "aminatou",
        "name": "Aminatou",
        "source": "wiki",
        "wiki_page": "Commander_2018/Subjective_Reality",
        "deck_title": "Subjective Reality",
        "commanders": ("Aminatou, the Fateshifter",),
        "precon_sets": ("C18",),
    },
    {
        "slug": "mishra_eminent_one",
        "name": "Mishra, Eminent One",
        "source": "wiki",
        "wiki_page": "The_Brothers'_War/Commander",
        "deck_title": "Mishra's Burnished Banner",
        "commanders": ("Mishra, Eminent One",),
        "precon_sets": ("BRC",),
    },
)


def load_card_rows(spec: dict) -> list[tuple[str, int, str]]:
    if spec["source"] == "clb_wiki":
        wiki_text = CLB_WIKI.read_text(encoding="utf-8")
        return parse_wiki_deck(
            wiki_text,
            spec["wiki_title"],
            spec["slug"],
            spec["boundary_titles"],
        )

    wikitext = fetch_wikitext(spec["wiki_page"])
    block = extract_deck_block(wikitext, spec["deck_title"])
    if not block:
        raise ValueError(f"Deck block not found: {spec['deck_title']} in {spec['wiki_page']}")
    return parse_deck_block(
        block,
        spec["commanders"],
        commander_as=spec.get("commander_as"),
    )


def build_deck(
    spec: dict,
    resolver: PrintResolver,
) -> tuple[Path, int, int, list[str]]:
    rows = load_card_rows(spec)
    built_rows, missing = build_deck_rows_from_scryfall(
        rows,
        spec["precon_sets"],
        resolver,
        basic_fallback_sets=spec.get("basic_fallback_sets", ()),
    )
    deck_file = REPO_ROOT / "data" / "decks" / f"{spec['slug']}.csv"
    write_deck_card_rows(deck_file, built_rows)
    upsert_deck_manifest_entry(
        spec["slug"],
        spec["name"],
        deck_file.name,
        purchase_price=spec.get("purchase_price", DEFAULT_PURCHASE_PRICE),
    )
    card_count = sum(row["qty"] for row in built_rows)
    return deck_file, len(built_rows), card_count, missing


def main() -> None:
    configure_logging(verbose=False)
    resolver = PrintResolver(delay_seconds=0.05, strict_sets=True)
    for spec in DECK_SPECS:
        deck_file, built_count, card_count, missing = build_deck(spec, resolver)
        sets = ", ".join(spec["precon_sets"])
        log.info(
            "Wrote %s (%s rows, %s cards from %s, %s unresolved)",
            deck_file.name,
            built_count,
            card_count,
            sets,
            len(missing),
        )
        if missing:
            log.warning("  Unresolved in %s: %s", spec["slug"], ", ".join(missing[:8]))
            if len(missing) > 8:
                log.warning("  ... and %s more", len(missing) - 8)
    log.info(
        "Built %s precon deck(s); %s Scryfall lookups cached",
        len(DECK_SPECS),
        len(resolver._cache),
    )


if __name__ == "__main__":
    main()
