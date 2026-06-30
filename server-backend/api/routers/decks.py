import sqlite3



from fastapi import APIRouter, Depends, HTTPException, Query, Request



from api.deps import get_db

from api.http_cache import serve_cached_json

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





@router.get("/browse-index")

def deck_browse_index(request: Request, conn: sqlite3.Connection = Depends(get_db)):

    return serve_cached_json(

        request,

        namespace="decks.browse_index",

        params={},

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

            params={"deckId": deckId},

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

            params={"deckId": deck_id},

            ttl=120,

            loader=lambda: decks_service.load_deck_browse(conn, deck_id=deck_id),

        )

    except DeckError as exc:

        raise _deck_error(exc) from exc


