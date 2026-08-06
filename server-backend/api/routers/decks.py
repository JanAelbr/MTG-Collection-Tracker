import sqlite3



from fastapi import APIRouter, Depends, HTTPException, Query, Request



from api.deps import get_db

from api.http_cache import serve_cached_json, with_price_strategy

from api.schemas import (
    DeckApplyProposal,
    DeckBulkCardsAdd,
    DeckCardAdd,
    DeckCardOwnedUpdate,
    DeckCardQtyAdjust,
    DeckCardRemove,
    DeckCardSwap,
    DeckCreate,
    DeckCsvImport,
    DeckRename,
)

from api.services import decks_service

from api.services.decks_service import DeckError



router = APIRouter(prefix="/decks", tags=["decks"])





def _deck_error(exc: DeckError) -> HTTPException:

    return HTTPException(status_code=exc.status_code, detail=exc.message)





@router.get("")

def list_decks(request: Request, conn: sqlite3.Connection = Depends(get_db)):

    return serve_cached_json(

        request,

        namespace="decks.list",

        params={},

        ttl=120,

        loader=lambda: decks_service.list_decks(conn),

    )


@router.post("")
def create_deck(
    body: DeckCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.create_deck(
            conn,
            deck_format=body.format,
            name=body.name,
            commanders=[
                {
                    "set_code": commander.setCode,
                    "collector_number": commander.collectorNumber,
                    "finish": commander.finish,
                }
                for commander in body.commanders
            ],
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc





@router.get("/browse-index")

def deck_browse_index(request: Request, conn: sqlite3.Connection = Depends(get_db)):

    return serve_cached_json(
        request,
        namespace="decks.browse_index",
        params=with_price_strategy(conn),
        ttl=120,
        loader=lambda: decks_service.load_deck_browse_index(conn),
    )





@router.get("/stats")

def deck_stats(

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

    deckId: str = Query(default="All"),

):

    try:

        return serve_cached_json(
            request,
            namespace="decks.stats",
            params=with_price_strategy(conn, {"deckId": deckId}),
            ttl=120,
            loader=lambda: decks_service.load_deck_stats(conn, deck_id=deckId),
        )

    except DeckError as exc:

        raise _deck_error(exc) from exc





@router.get("/{deck_id}/browse")

def deck_browse(

    deck_id: str,

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return serve_cached_json(
            request,
            namespace="decks.browse",
            params=with_price_strategy(conn, {"deckId": deck_id}),
            ttl=120,
            loader=lambda: decks_service.load_deck_browse(conn, deck_id=deck_id),
        )

    except DeckError as exc:

        raise _deck_error(exc) from exc





@router.get("/{deck_id}/power")
def deck_power(
    deck_id: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return serve_cached_json(
            request,
            namespace="decks.power",
            params={"deckId": deck_id},
            ttl=60,
            loader=lambda: decks_service.load_deck_power(conn, deck_id),
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/cards/bulk")
def bulk_add_deck_cards(
    deck_id: str,
    body: DeckBulkCardsAdd,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.bulk_add_cards_to_deck(
            conn,
            deck_id=deck_id,
            cards=[
                {
                    "setCode": card.setCode,
                    "collectorNumber": card.collectorNumber,
                    "finish": card.finish,
                    "section": card.section,
                    "qty": card.qty,
                    "owned": card.owned,
                    "cardName": card.cardName,
                    "suggested": not card.owned if card.owned is not None else None,
                }
                for card in body.cards
            ],
            replace_main=body.replaceMain,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/apply-proposal")
def apply_deck_proposal(
    deck_id: str,
    body: DeckApplyProposal,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.apply_deck_proposal(
            conn,
            deck_id=deck_id,
            cards=[
                {
                    "setCode": card.setCode,
                    "collectorNumber": card.collectorNumber,
                    "finish": card.finish,
                    "section": card.section,
                    "qty": card.qty,
                    "owned": card.owned,
                    "cardName": card.cardName,
                    "suggested": not card.owned if card.owned is not None else None,
                    "name": card.cardName,
                }
                for card in body.cards
            ],
            mode=body.mode,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/metadata/refresh-unpriced")
def refresh_deck_unpriced_metadata(
    deck_id: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.refresh_deck_unpriced_metadata(
            conn,
            deck_id=deck_id,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/cards/csv/preview")
def preview_deck_csv_import(
    deck_id: str,
    body: DeckCsvImport,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.preview_deck_csv_import(
            conn,
            deck_id=deck_id,
            csv=body.csv,
            mode=body.mode,
            section=body.section,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/cards/csv/apply")
def apply_deck_csv_import(
    deck_id: str,
    body: DeckCsvImport,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.apply_deck_csv_import(
            conn,
            deck_id=deck_id,
            csv=body.csv,
            mode=body.mode,
            section=body.section,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/cards")

def add_deck_card(

    deck_id: str,

    body: DeckCardAdd,

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return decks_service.add_card_to_deck(

            conn,

            deck_id=deck_id,

            set_code=body.setCode,

            collector_number=body.collectorNumber,

            finish=body.finish,

            section=body.section,

            qty=body.qty,

        )

    except DeckError as exc:

        raise _deck_error(exc) from exc


@router.delete("/{deck_id}/cards")
def remove_deck_card(
    deck_id: str,
    body: DeckCardRemove,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.remove_card_from_deck(
            conn,
            deck_id=deck_id,
            set_code=body.setCode,
            collector_number=body.collectorNumber,
            finish=body.finish,
            section=body.section,
            qty=body.qty,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/cards/qty")
def adjust_deck_card_qty(
    deck_id: str,
    body: DeckCardQtyAdjust,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.adjust_deck_card_qty(
            conn,
            deck_id=deck_id,
            set_code=body.setCode,
            collector_number=body.collectorNumber,
            finish=body.finish,
            section=body.section,
            delta=body.delta,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.patch("/{deck_id}/cards/owned")
def set_deck_card_owned(
    deck_id: str,
    body: DeckCardOwnedUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.set_deck_card_owned(
            conn,
            deck_id=deck_id,
            set_code=body.setCode,
            collector_number=body.collectorNumber,
            finish=body.finish,
            section=body.section,
            owned=body.owned,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.post("/{deck_id}/cards/swap")
def swap_deck_card(
    deck_id: str,
    body: DeckCardSwap,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.swap_deck_card(
            conn,
            deck_id=deck_id,
            remove_set_code=body.remove.setCode,
            remove_collector_number=body.remove.collectorNumber,
            remove_finish=body.remove.finish,
            remove_section=body.remove.section,
            remove_qty=body.remove.qty,
            add_set_code=body.add.setCode,
            add_collector_number=body.add.collectorNumber,
            add_finish=body.add.finish,
            destination_storage_location=body.destinationStorageLocation,
        )
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.patch("/{deck_id}")
def rename_deck(
    deck_id: str,
    body: DeckRename,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.rename_deck(conn, deck_id=deck_id, name=body.name)
    except DeckError as exc:
        raise _deck_error(exc) from exc


@router.delete("/{deck_id}")
def delete_deck(
    deck_id: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return decks_service.delete_deck(conn, deck_id=deck_id)
    except DeckError as exc:
        raise _deck_error(exc) from exc

