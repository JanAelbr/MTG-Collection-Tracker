import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db
from api.services import price_sync_service
from api.services.price_sync_service import PriceSyncError

router = APIRouter(prefix="/prices", tags=["prices"])


@router.post("/sync")
def trigger_price_sync():
    try:
        return price_sync_service.start_price_sync()
    except PriceSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/sync/status")
def price_sync_status(conn: sqlite3.Connection = Depends(get_db)):
    return price_sync_service.get_price_sync_status(conn)
