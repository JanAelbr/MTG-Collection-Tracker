import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.services import price_sync_service
from api.services.price_sync_service import PriceSyncError

router = APIRouter(prefix="/prices", tags=["prices"])


@router.post("/sync")
def trigger_price_sync(
    conn: sqlite3.Connection = Depends(get_db),
    setCode: str | None = Query(default=None),
    force: bool = Query(default=False),
):
    try:
        return price_sync_service.start_price_sync(conn, set_code=setCode, force=force)
    except PriceSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/sync/status")
def price_sync_status(conn: sqlite3.Connection = Depends(get_db)):
    return price_sync_service.get_price_sync_status(conn)


@router.get("/sync/cards")
def price_sync_art_style_cards(
    conn: sqlite3.Connection = Depends(get_db),
    setCode: str | None = Query(default=None),
    artStyle: str | None = Query(default=None),
):
    try:
        return {
            "cards": price_sync_service.list_art_style_card_movers(
                conn,
                set_code=setCode,
                art_style=artStyle,
            ),
        }
    except PriceSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
