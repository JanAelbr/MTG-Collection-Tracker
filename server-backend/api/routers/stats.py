import sqlite3



from fastapi import APIRouter, Depends, HTTPException, Query, Request



from api.deps import get_db

from api.http_cache import serve_cached_json, with_price_strategy

from api.services import stats_service



router = APIRouter(prefix="/stats", tags=["stats"])





@router.get("/collection")

def collection_stats(

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

    setCode: str = Query(default="All"),

    finishFilter: str = Query(default="all"),
    foilFilter: str | None = Query(default=None),

):

    return serve_cached_json(

        request,

        namespace="stats.collection",

        params=with_price_strategy(
            conn,
            {"setCode": setCode, "finishFilter": finishFilter, "foilFilter": foilFilter},
        ),

        ttl=120,

        loader=lambda: stats_service.load_collection_stats(

            conn,

            set_code=setCode,

            finish_filter=foilFilter or finishFilter,

        ),

    )


