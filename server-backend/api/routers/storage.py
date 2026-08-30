import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_db
from api.http_cache import serve_cached_json, with_price_strategy
from api.schemas import StorageBreakdownSnapshotCreate, StorageLocationCreate, StorageLocationUpdate
from api.services import settings_service, storage_service
from api.services.storage_service import StorageError

router = APIRouter(prefix="/storage", tags=["storage"])


def _handle_storage_error(exc: StorageError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/locations")
def list_locations(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return serve_cached_json(
        request,
        namespace="storage.locations",
        params=with_price_strategy(conn),
        ttl=45,
        loader=lambda: _locations_payload(conn),
    )


@router.get("/locations/{slug}/breakdown")
def location_breakdown(
    slug: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return serve_cached_json(
            request,
            namespace="storage.location_breakdown",
            params=with_price_strategy(conn, {"slug": slug}),
            ttl=45,
            loader=lambda: storage_service.get_storage_breakdown(
                conn,
                slug,
                price_strategy=settings_service.get_settings(conn)["priceStrategy"],
            ),
        )
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc


@router.post("/breakdowns")
def save_breakdown_snapshot(
    body: StorageBreakdownSnapshotCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return storage_service.save_daily_breakdown(
            conn,
            price_strategy=settings_service.get_settings(conn)["priceStrategy"],
            note=body.note,
        )
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc


@router.get("/breakdowns")
def list_breakdown_snapshots(conn: sqlite3.Connection = Depends(get_db)):
    return {"snapshots": storage_service.list_breakdown_snapshots(conn)}


@router.get("/breakdowns/history")
def list_breakdown_history(conn: sqlite3.Connection = Depends(get_db)):
    return storage_service.list_breakdown_history(conn)


@router.get("/breakdowns/{snapshot_id}")
def get_breakdown_snapshot(snapshot_id: int, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return storage_service.get_breakdown_snapshot(conn, snapshot_id)
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc


@router.delete("/breakdowns/{snapshot_id}")
def delete_breakdown_snapshot(snapshot_id: int, conn: sqlite3.Connection = Depends(get_db)):
    try:
        storage_service.delete_breakdown_snapshot(conn, snapshot_id)
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc
    return {"ok": True}


@router.post("/locations")
def create_location(body: StorageLocationCreate, conn: sqlite3.Connection = Depends(get_db)):
    try:
        location = storage_service.create_location(
            conn,
            label=body.label,
            description=body.description,
            location_type=body.locationType,
        )
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc
    return location


@router.patch("/locations/{slug}")
def update_location(
    slug: str,
    body: StorageLocationUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return storage_service.update_location(
            conn,
            slug,
            label=body.label,
            description=body.description,
        )
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc


@router.delete("/locations/{slug}")
def delete_location(slug: str, conn: sqlite3.Connection = Depends(get_db)):
    try:
        storage_service.delete_location(conn, slug)
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc
    return {"ok": True}


@router.get("/locations/{slug}/cards")
def location_cards(
    slug: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return serve_cached_json(
            request,
            namespace="storage.location_cards",
            params=with_price_strategy(conn, {"slug": slug}),
            ttl=45,
            loader=lambda: storage_service.list_location_cards(
                conn,
                slug,
                price_strategy=settings_service.get_settings(conn)["priceStrategy"],
            ),
        )
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc


@router.delete("/instances/{instance_id}")
def delete_instance(instance_id: int, conn: sqlite3.Connection = Depends(get_db)):
    try:
        location = storage_service.delete_instance(conn, instance_id)
    except StorageError as exc:
        raise _handle_storage_error(exc) from exc
    return {"ok": True, "location": location}


def _locations_payload(conn: sqlite3.Connection) -> dict:
    settings = settings_service.get_settings(conn)
    locations = storage_service.list_locations(conn)
    return {
        "locations": locations,
        "defaultLocation": _default_location(locations),
        "priceStrategy": settings["priceStrategy"],
    }


def _default_location(locations: list[dict]) -> str:
    for location in locations:
        if location["cardCount"] > 0:
            return location["slug"]
    for location in locations:
        if location["isCustom"]:
            return location["slug"]
    return locations[0]["slug"] if locations else ""
