import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.services import stats_service
from api.services.reports_service import ReportsError

router = APIRouter(prefix="/stats", tags=["stats"])


def _optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


@router.get("/collection")
def collection_stats(
    conn: sqlite3.Connection = Depends(get_db),
    setCode: str = Query(default="All"),
    family: bool = Query(default=False),
    finishFilter: str = Query(default="all"),
    foilFilter: str | None = Query(default=None),
    artStyle: str = Query(default=""),
    ownedFilter: str = Query(default="owned"),
    typeFilter: str = Query(default="all"),
    colors: str = Query(default=""),
    colorMode: str = Query(default="exact"),
    search: str = Query(default=""),
    rarity: str = Query(default="all"),
    cmcMin: str | None = Query(default=None),
    cmcMax: str | None = Query(default=None),
    priceMin: str | None = Query(default=None),
    priceMax: str | None = Query(default=None),
    powMin: str | None = Query(default=None),
    tghMin: str | None = Query(default=None),
    storage: str = Query(default=""),
):
    storage_filters = [
        item.strip()
        for item in (storage or "").split(",")
        if item.strip()
    ]
    try:
        return stats_service.load_collection_stats(
            conn,
            set_code=setCode,
            finish_filter=foilFilter or finishFilter,
            family=family,
            art_style=artStyle,
            owned_filter=ownedFilter,
            type_filter=typeFilter,
            color_filters=colors,
            color_mode=colorMode,
            search=search,
            rarity_filter=rarity,
            cmc_min=_optional_float(cmcMin),
            cmc_max=_optional_float(cmcMax),
            price_min=_optional_float(priceMin),
            price_max=_optional_float(priceMax),
            power_min=_optional_float(powMin),
            toughness_min=_optional_float(tghMin),
            storage_filters=storage_filters,
        )
    except ReportsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
