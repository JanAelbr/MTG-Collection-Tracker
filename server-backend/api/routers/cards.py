import sqlite3



from fastapi import APIRouter, Depends, HTTPException, Query, Request



from api.deps import get_db

from api.http_cache import serve_cached_json, with_price_strategy

from api.services.card_service import CardError, load_card_detail



router = APIRouter(prefix="/cards", tags=["cards"])





@router.get("/{set_code}/{collector_number}")

def get_card_detail(

    set_code: str,

    collector_number: str,

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

    finish: int | None = Query(default=None, ge=0, le=2),
):

    params = with_price_strategy(
        conn,
        {
            "setCode": set_code,
            "collectorNumber": collector_number,
            "finish": finish,
        },
    )

    try:

        return serve_cached_json(

            request,

            namespace="cards.detail",

            params=params,

            ttl=120,

            loader=lambda: load_card_detail(

                conn,

                set_code,

                collector_number,

                finish=finish,

            ),

        )

    except CardError as exc:

        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


