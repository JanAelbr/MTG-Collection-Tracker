import sqlite3



from fastapi import APIRouter, Depends, HTTPException, Query, Request



from api.deps import get_db

from api.http_cache import serve_cached_json

from api.schemas import (

    BulkAssignStorage,

    CopyAdjust,
    CopyStorageUpdate,

    ManagerSetCreate,

    OwnershipBulkUpdate,

    OwnershipUpdate,

)

from api.services import manager_service, settings_service

from api.services.manager_service import ManagerError

from api.services.storage_service import StorageError



router = APIRouter(prefix="/manager", tags=["manager"])





def _manager_error(exc: ManagerError) -> HTTPException:

    return HTTPException(status_code=exc.status_code, detail=exc.message)





def _storage_error(exc: StorageError) -> HTTPException:

    return HTTPException(status_code=exc.status_code, detail=exc.message)





@router.get("/sets")

def list_sets(request: Request, conn: sqlite3.Connection = Depends(get_db)):

    return serve_cached_json(

        request,

        namespace="manager.sets",

        params={},

        ttl=45,

        loader=lambda: _sets_payload(conn),

    )





@router.post("/sets")

def create_set(body: ManagerSetCreate, conn: sqlite3.Connection = Depends(get_db)):

    try:

        result = manager_service.add_set(conn, body.setCode)

        conn.commit()

        return result

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.delete("/sets/{set_code}")

def delete_set(set_code: str, conn: sqlite3.Connection = Depends(get_db)):

    try:

        result = manager_service.remove_set(conn, set_code)

        conn.commit()

        return result

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.post("/catalogs/prune-orphans")

def prune_orphan_catalogs(conn: sqlite3.Connection = Depends(get_db)):

    try:

        result = manager_service.prune_orphan_catalogs(conn)

        conn.commit()

        return result

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.get("/sets/{set_code}/art-styles")

def list_art_styles(

    set_code: str,

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return serve_cached_json(

            request,

            namespace="manager.art_styles",

            params={"setCode": set_code},

            ttl=45,

            loader=lambda: {"artStyles": manager_service.list_art_styles(conn, set_code)},

        )

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.post("/sets/{set_code}/favorite")

def toggle_favorite_set(

    set_code: str,

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return manager_service.toggle_favorite_set(conn, set_code)

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.get("/sets/{set_code}/cards")

def list_set_cards(

    set_code: str,

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

    artStyle: str = Query(default=""),

    search: str = Query(default=""),

    finishFilter: str = Query(default="all"),
    foilFilter: str | None = Query(default=None),

    page: int = Query(default=1, ge=1),

    pageSize: int = Query(default=100, ge=1, le=500),

):

    params = {

        "setCode": set_code,

        "artStyle": artStyle,

        "search": search,

        "finishFilter": finishFilter,
        "foilFilter": foilFilter,

        "page": page,

        "pageSize": pageSize,

    }

    try:

        return serve_cached_json(

            request,

            namespace="manager.set_cards",

            params=params,

            ttl=45,

            loader=lambda: manager_service.list_set_cards(

                conn,

                set_code,

                art_style=artStyle,

                search=search,

                finish_filter=foilFilter or finishFilter,

                page=page,

                page_size=pageSize,

            ),

        )

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.patch("/ownership")

def update_ownership(body: OwnershipUpdate, conn: sqlite3.Connection = Depends(get_db)):

    try:

        return manager_service.set_ownership(

            conn,

            set_code=body.setCode,

            collector_number=body.collectorNumber,

            finish=body.finish,

            owned=body.owned,

            purchase_value=body.purchaseValue,

        )

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.post("/ownership/bulk")

def bulk_update_ownership(

    body: OwnershipBulkUpdate,

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return manager_service.bulk_set_ownership(

            conn,

            set_code=body.setCode,

            items=[item.model_dump() for item in body.items],

        )

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.get("/copies")

def read_copy_state(

    setCode: str = Query(..., min_length=1, max_length=16),

    collectorNumber: str = Query(..., min_length=1, max_length=32),

    finish: int = Query(0, ge=0, le=2),

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return manager_service.get_copy_state(conn, setCode, collectorNumber, finish)

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.patch("/copies")

def adjust_copy_count(body: CopyAdjust, conn: sqlite3.Connection = Depends(get_db)):

    try:

        return manager_service.adjust_copy_count(

            conn,

            set_code=body.setCode,

            collector_number=body.collectorNumber,

            finish=body.finish,

            delta=body.delta,

            location_slug=body.locationSlug,

        )

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.patch("/copies/{instance_id}/storage")

def update_copy_storage(

    instance_id: int,

    body: CopyStorageUpdate,

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return manager_service.update_copy_storage(

            conn,

            instance_id=instance_id,

            location_slug=body.locationSlug,

        )

    except ManagerError as exc:

        raise _manager_error(exc) from exc





@router.post("/bulk-assign-storage")

def bulk_assign_storage(

    body: BulkAssignStorage,

    conn: sqlite3.Connection = Depends(get_db),

):

    try:

        return manager_service.bulk_assign_storage(

            conn,

            location_slug=body.locationSlug,

            items=[item.model_dump() for item in body.items],

        )

    except (ManagerError, StorageError) as exc:

        if isinstance(exc, StorageError):

            raise _storage_error(exc) from exc

        raise _manager_error(exc) from exc





def _sets_payload(conn: sqlite3.Connection) -> dict:

    sets = manager_service.list_sets(conn)

    return {

        "sets": sets,

        "favoriteSets": settings_service.get_favorite_sets(conn),

        "defaultSet": sets[0]["setCode"] if sets else "",

    }


