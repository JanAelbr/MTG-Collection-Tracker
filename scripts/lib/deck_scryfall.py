import re
import time

from lib.config import HTTP_USER_AGENT
from lib.deck_csv import CARD_NAME_ALIASES
from lib.run_log import get_logger
from util.scryfall_client import scryfall_get

log = get_logger(__name__)
SCRYFALL_HEADERS = {"User-Agent": HTTP_USER_AGENT}
BASIC_LAND_NAMES = frozenset({"plains", "island", "swamp", "mountain", "forest"})


class PrintResolver:
    """Resolve deck card names to prints with in-memory caching."""

    def __init__(self, *, delay_seconds: float = 0.1, strict_sets: bool = True):
        self.delay_seconds = delay_seconds
        self.strict_sets = strict_sets
        self._cache: dict[tuple[str, tuple[str, ...], tuple[str, ...]], tuple[str, str]] = {}

    def resolve(
        self,
        card_name: str,
        preferred_set_codes: tuple[str, ...],
        *,
        basic_fallback_sets: tuple[str, ...] = (),
    ) -> tuple[str, str] | None:
        normalized_preferred = tuple(code.upper() for code in preferred_set_codes)
        normalized_basic = tuple(code.upper() for code in basic_fallback_sets)
        cache_key = (card_name.strip().casefold(), normalized_preferred, normalized_basic)
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = resolve_scryfall_print(
            card_name,
            normalized_preferred,
            strict=self.strict_sets,
            basic_fallback_sets=normalized_basic,
        )
        if result:
            self._cache[cache_key] = result
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return result


# Return alternate Scryfall names to try for one deck card label.
def scryfall_name_candidates(card_name: str) -> list[str]:
    candidates = [card_name.strip()]
    alias = CARD_NAME_ALIASES.get(card_name.strip())
    if alias and alias not in candidates:
        candidates.append(alias)
    return candidates


# Resolve one deck card name to a Scryfall print, preferring listed set codes.
def resolve_scryfall_print(
    card_name: str,
    preferred_set_codes: tuple[str, ...] = (),
    *,
    strict: bool = False,
    basic_fallback_sets: tuple[str, ...] = (),
) -> tuple[str, str] | None:
    for candidate in scryfall_name_candidates(card_name):
        for set_code in preferred_set_codes:
            result = _search_print_in_set(candidate, set_code)
            if result:
                return result

        if candidate.casefold() in BASIC_LAND_NAMES:
            for set_code in basic_fallback_sets:
                result = _search_print_in_set(candidate, set_code)
                if result:
                    return result

        if strict:
            continue

        response = _scryfall_get(
            "https://api.scryfall.com/cards/named",
            params={"exact": candidate},
        )
        if response.status_code != 200:
            continue
        card = response.json()
        set_code = (card.get("set") or "").upper()
        collector_number = str(card.get("collector_number", "")).strip()
        if set_code and collector_number:
            return set_code, collector_number
    return None


def _scryfall_get(url: str, *, params: dict | None = None, max_retries: int = 5):
    response = None
    for attempt in range(max_retries):
        response = scryfall_get(
            url,
            params=params,
            headers=SCRYFALL_HEADERS,
            timeout=30,
            logger=log,
            label="Scryfall deck print lookup",
        )
        if response.status_code == 200:
            return response
        if response.status_code == 404:
            return response
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else 1.0 + attempt
            time.sleep(wait)
            continue
        if response.status_code in {502, 503, 504}:
            time.sleep(0.5 * (attempt + 1))
            continue
        break
    return response


def _build_set_search_queries(card_name: str, set_code: str) -> list[str]:
    name = card_name.strip()
    set_part = f"set:{set_code.lower()}"
    queries: list[str] = []

    escaped = name.replace('"', '\\"')
    queries.append(f'name:"{escaped}" {set_part}')

    if '"' not in name:
        queries.append(f'!"{name}" {set_part}')

    if name.casefold() in BASIC_LAND_NAMES:
        queries.append(f"name:{name.casefold()} type:basic {set_part}")

    if '"' in name:
        token_query = " ".join(re.sub(r"[^\w\s]", " ", name).split())
        if token_query:
            queries.append(f"{token_query} {set_part}")

    seen: set[str] = set()
    unique_queries: list[str] = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique_queries.append(query)
    return unique_queries


# Look up one card in a specific Scryfall set.
def _search_print_in_set(card_name: str, set_code: str) -> tuple[str, str] | None:
    for query in _build_set_search_queries(card_name, set_code):
        response = _scryfall_get(
            "https://api.scryfall.com/cards/search",
            params={"q": query, "unique": "prints"},
        )
        if response.status_code != 200:
            continue
        cards = response.json().get("data", [])
        if not cards:
            continue
        card = min(
            cards,
            key=lambda item: (
                int(str(item.get("collector_number", "0")).split("a")[0])
                if str(item.get("collector_number", "0")).split("a")[0].isdigit()
                else 9999,
                str(item.get("collector_number", "")),
            ),
        )
        return (card.get("set") or set_code).upper(), str(card.get("collector_number", "")).strip()
    return None


# Resolve many deck cards to prints with a short delay between API calls.
def resolve_deck_prints(
    card_names: list[str],
    preferred_set_codes: tuple[str, ...] = (),
    delay_seconds: float = 0.12,
    *,
    strict: bool = False,
    basic_fallback_sets: tuple[str, ...] = (),
) -> dict[str, tuple[str, str] | None]:
    resolver = PrintResolver(delay_seconds=delay_seconds, strict_sets=strict)
    return {
        card_name: resolver.resolve(
            card_name,
            preferred_set_codes,
            basic_fallback_sets=basic_fallback_sets,
        )
        for card_name in card_names
    }


def build_deck_rows_from_scryfall(
    rows: list[tuple[str, int, str]],
    preferred_set_codes: tuple[str, ...],
    resolver: PrintResolver | None = None,
    *,
    basic_fallback_sets: tuple[str, ...] = (),
) -> tuple[list[dict], list[str]]:
    lookup = resolver or PrintResolver(strict_sets=True)
    built: list[dict] = []
    missing: list[str] = []
    for name, qty, section in rows:
        resolved = lookup.resolve(
            name,
            preferred_set_codes,
            basic_fallback_sets=basic_fallback_sets,
        )
        if not resolved:
            missing.append(name)
            continue
        set_code, collector_number = resolved
        built.append({
            "set_code": set_code,
            "collector_number": collector_number,
            "finish": 0,
            "qty": qty,
            "owned_qty": min(qty, 1),
            "section": section,
        })
    return built, missing
