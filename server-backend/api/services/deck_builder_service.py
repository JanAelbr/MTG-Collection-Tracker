import sqlite3

from api.services.deck_generation_service import DeckBuilderError, generate_deck_proposal
from report.builder_queries import load_owned_commanders, preview_storage_pool

__all__ = [
    "DeckBuilderError",
    "generate_deck_proposal",
    "list_owned_commanders",
    "preview_pool",
]


def list_owned_commanders(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    return load_owned_commanders(conn, search=search, page=page, page_size=page_size)


def preview_pool(
    conn: sqlite3.Connection,
    *,
    location_slugs: list[str],
    include_deck_storage: bool = False,
) -> dict:
    return preview_storage_pool(
        conn,
        location_slugs,
        include_deck_storage=include_deck_storage,
    )


def assess_builder_proposal(
    conn: sqlite3.Connection,
    *,
    commanders: list[dict],
    cards: list[dict],
) -> dict:
    from api.services.deck_power_service import assess_deck_power
    from report.builder_queries import resolve_commander_rows

    commander_rows = resolve_commander_rows(conn, commanders)
    if not commander_rows:
        raise DeckBuilderError("Commander not found in catalog", status_code=400)
    return assess_deck_power(cards, commanders=commander_rows)
