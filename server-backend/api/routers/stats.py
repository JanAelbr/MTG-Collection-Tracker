import sqlite3

from fastapi import APIRouter, Depends, Query

from api.deps import get_db
from api.services import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/collection")
def collection_stats(
    conn: sqlite3.Connection = Depends(get_db),
    setCode: str = Query(default="All"),
    finishFilter: str = Query(default="all"),
    foilFilter: str | None = Query(default=None),
):
    return stats_service.load_collection_stats(
        conn,
        set_code=setCode,
        finish_filter=foilFilter or finishFilter,
    )
