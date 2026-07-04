import sqlite3



from fastapi import APIRouter, Depends, Request



from api.deps import get_db

from api.http_cache import serve_cached_json

from api.cache import get_cache_epoch
from util.price_history import load_last_updated_display, prices_are_outdated



router = APIRouter(prefix="/meta", tags=["meta"])





@router.get("")

def read_app_meta(request: Request, conn: sqlite3.Connection = Depends(get_db)):

    return serve_cached_json(

        request,

        namespace="meta",

        params={},

        ttl=30,

        loader=lambda: {
            "lastPriceUpdate": load_last_updated_display(conn),
            "pricesOutdated": prices_are_outdated(conn),
            "cacheEpoch": get_cache_epoch(),
        },

    )


