import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_db
from api.http_cache import serve_cached_json, with_price_strategy
from api.schemas import SettingsUpdate
from api.services import settings_service
from api.services.settings_service import SettingsError

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def read_settings(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return serve_cached_json(
        request,
        namespace="settings",
        params=with_price_strategy(conn),
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
    if "favoritesCardsPriceStrategy" in updates:
        kwargs["favorites_cards_price_strategy"] = updates["favoritesCardsPriceStrategy"]
    if "favoritesArtStylesPriceStrategy" in updates:
        kwargs["favorites_art_styles_price_strategy"] = updates[
            "favoritesArtStylesPriceStrategy"
        ]
    if "favoriteCards" in updates:
        kwargs["favorite_cards"] = updates["favoriteCards"]
    if "favoriteArtStyles" in updates:
        kwargs["favorite_art_styles"] = updates["favoriteArtStyles"]
    if "pageSize" in updates:
        kwargs["page_size"] = updates["pageSize"]
    if "collectionCardScale" in updates:
        kwargs["collection_card_scale"] = updates["collectionCardScale"]
    if "setSortMode" in updates:
        kwargs["set_sort_mode"] = updates["setSortMode"]
    if "defaultStorageLocation" in updates:
        kwargs["default_storage_location"] = updates["defaultStorageLocation"]
    try:
        return settings_service.update_settings(conn, **kwargs)
    except SettingsError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
