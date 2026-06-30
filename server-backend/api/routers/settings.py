import sqlite3



from fastapi import APIRouter, Depends, HTTPException, Request



from api.deps import get_db

from api.http_cache import serve_cached_json

from api.schemas import SettingsUpdate

from api.services import settings_service
from api.services.settings_service import SettingsError



router = APIRouter(prefix="/settings", tags=["settings"])





@router.get("")

def read_settings(request: Request, conn: sqlite3.Connection = Depends(get_db)):

    return serve_cached_json(

        request,

        namespace="settings",

        params={},

        ttl=60,

        loader=lambda: settings_service.get_settings(conn),

    )





@router.patch("")

def patch_settings(body: SettingsUpdate, conn: sqlite3.Connection = Depends(get_db)):
    updates = body.model_dump(exclude_unset=True)
    kwargs = {
        "price_strategy": updates.get("priceStrategy"),
        "favorite_sets": updates.get("favoriteSets"),
    }
    if "compareDate" in updates:
        kwargs["compare_date"] = updates["compareDate"]
        kwargs["set_compare_date"] = True
    if "pageSize" in updates:
        kwargs["page_size"] = updates["pageSize"]
    if "collectionCardScale" in updates:
        kwargs["collection_card_scale"] = updates["collectionCardScale"]
    if "setSortMode" in updates:
        kwargs["set_sort_mode"] = updates["setSortMode"]
    if "setPickerMode" in updates:
        kwargs["set_picker_mode"] = updates["setPickerMode"]
    if "defaultStorageLocation" in updates:
        kwargs["default_storage_location"] = updates["defaultStorageLocation"]
    try:
        return settings_service.update_settings(conn, **kwargs)
    except SettingsError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


