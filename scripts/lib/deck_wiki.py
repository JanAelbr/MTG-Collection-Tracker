import json
import re

from lib.config import HTTP_USER_AGENT
from lib.run_log import get_logger
from util.http_client import http_get

WIKI_API = "https://mtg.wiki/api.php"
USER_AGENT = HTTP_USER_AGENT
log = get_logger(__name__)


def fetch_wikitext(page: str) -> str:
    page = page.split("#", 1)[0]
    params = {
        "action": "parse",
        "page": page,
        "prop": "wikitext",
        "format": "json",
    }
    response = http_get(
        WIKI_API,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=60,
        logger=log,
        label="MTG Wiki wikitext",
    )
    response.raise_for_status()
    data = json.loads(response.text)
    return data["parse"]["wikitext"]["*"]


def extract_deck_block(wikitext: str, title: str) -> str | None:
    pattern = rf'<d title="{re.escape(title)}">(.*?)</d>'
    match = re.search(pattern, wikitext, re.DOTALL)
    return match.group(1).strip() if match else None


def parse_deck_block(
    block: str,
    commanders: tuple[str, ...],
    *,
    commander_as: str | None = None,
) -> list[tuple[str, int, str]]:
    commander_names = {name.casefold() for name in commanders}
    substitute = commander_as.casefold() if commander_as else None
    rows: list[tuple[str, int, str]] = []
    section = "main"

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {
            "Commander",
            "Creatures",
            "Creature",
            "Planeswalkers",
            "Instants",
            "Sorceries",
            "Artifacts",
            "Enchantments",
            "Lands",
            "Other spells",
        }:
            section = "commander" if line == "Commander" else "main"
            continue
        match = re.match(r"^(\d+)\s+(?:<c>)?(.+?)(?:</c>)?$", line)
        if not match:
            continue
        qty = int(match.group(1))
        name = match.group(2).strip()
        if section == "commander" and substitute and name.casefold() == substitute:
            card_section = "commander"
        elif name.casefold() in commander_names:
            card_section = "commander"
        elif section == "commander":
            card_section = "commander"
        else:
            card_section = "main"
        rows.append((name, qty, card_section))

    return rows
