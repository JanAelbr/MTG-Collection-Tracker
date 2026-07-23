import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_db
from api.http_cache import serve_cached_json, with_price_strategy
from api.schemas import (
    FavoriteArtStyleToggle,
    FavoriteArtStylesReorder,
    FavoriteCardToggle,
    FavoriteCardsReorder,
)
from api.services import favorites_service

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("")
def read_favorites(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return serve_cached_json(
        request,
        namespace="favorites",
        params=with_price_strategy(conn),
        ttl=30,
        loader=lambda: favorites_service.list_favorites(conn),
    )


@router.post("/cards")
def toggle_favorite_card(body: FavoriteCardToggle, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return favorites_service.toggle_favorite_card(
            conn,
            set_code=body.setCode,
            collector_number=body.collectorNumber,
            finish=body.finish,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/cards")
def reorder_favorite_cards(body: FavoriteCardsReorder, conn: sqlite3.Connection = Depends(get_db)):
    saved = favorites_service.reorder_favorite_cards(
        conn,
        [item.model_dump() for item in body.cards],
    )
    return {"favoriteCards": saved}


@router.post("/art-styles")
def toggle_favorite_art_style(
    body: FavoriteArtStyleToggle,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return favorites_service.toggle_favorite_art_style(
            conn,
            set_code=body.setCode,
            art_style=body.artStyle,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/art-styles")
def reorder_favorite_art_styles(
    body: FavoriteArtStylesReorder,
    conn: sqlite3.Connection = Depends(get_db),
):
    saved = favorites_service.reorder_favorite_art_styles(
        conn,
        [item.model_dump() for item in body.artStyles],
    )
    return {"favoriteArtStyles": saved}
