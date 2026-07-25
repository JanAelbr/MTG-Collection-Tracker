import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db
from api.schemas import (
    SaleListingCreate,
    SaleListingListedUpdate,
    SaleListingSell,
    SaleListingSoldUpdate,
)
from api.services import sale_listings_service
from api.services.sale_listings_service import SaleListingsError

router = APIRouter(prefix="/sales", tags=["sales"])


def _handle_error(exc: SaleListingsError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/listed")
def get_listed(conn: sqlite3.Connection = Depends(get_db)):
    return sale_listings_service.list_listed(conn)


@router.get("/sold")
def get_sold(conn: sqlite3.Connection = Depends(get_db)):
    return sale_listings_service.list_sold(conn)


@router.post("/listed")
def create_listed(body: SaleListingCreate, conn: sqlite3.Connection = Depends(get_db)):
    try:
        listing = sale_listings_service.create_listing(
            conn,
            instance_id=body.instanceId,
            listing_price=body.listingPrice,
            notes=body.notes,
        )
    except SaleListingsError as exc:
        raise _handle_error(exc) from exc
    conn.commit()
    return listing


@router.patch("/listed/{listing_id}")
def patch_listed(
    listing_id: int,
    body: SaleListingListedUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        listing = sale_listings_service.update_listed(
            conn,
            listing_id,
            listing_price=body.listingPrice,
            notes=body.notes,
            sort_order=body.sortOrder,
        )
    except SaleListingsError as exc:
        raise _handle_error(exc) from exc
    conn.commit()
    return listing


@router.post("/listed/{listing_id}/sell")
def sell_listed(
    listing_id: int,
    body: SaleListingSell,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        listing = sale_listings_service.mark_sold(
            conn,
            listing_id,
            sale_price=body.salePrice,
        )
    except SaleListingsError as exc:
        raise _handle_error(exc) from exc
    conn.commit()
    return listing


@router.delete("/listed/{listing_id}")
def delete_listed(listing_id: int, conn: sqlite3.Connection = Depends(get_db)):
    try:
        result = sale_listings_service.unlist(conn, listing_id)
    except SaleListingsError as exc:
        raise _handle_error(exc) from exc
    conn.commit()
    return result


@router.patch("/sold/{listing_id}")
def patch_sold(
    listing_id: int,
    body: SaleListingSoldUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        listing = sale_listings_service.update_sold(
            conn,
            listing_id,
            sale_price=body.salePrice,
            notes=body.notes,
        )
    except SaleListingsError as exc:
        raise _handle_error(exc) from exc
    conn.commit()
    return listing


@router.delete("/sold/{listing_id}")
def remove_sold(listing_id: int, conn: sqlite3.Connection = Depends(get_db)):
    try:
        result = sale_listings_service.delete_sold(conn, listing_id)
    except SaleListingsError as exc:
        raise _handle_error(exc) from exc
    conn.commit()
    return result
