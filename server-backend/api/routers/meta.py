import sqlite3



from fastapi import APIRouter, Depends, Request



from api.deps import get_db

from api.http_cache import serve_cached_json

from lib.config import REPORTS_DIR

from util.price_history import load_last_updated_display, prices_are_outdated

from api.cache import get_cache_epoch



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

            "legacyReportsAvailable": (REPORTS_DIR / "index.html").is_file(),

            "legacyReportsPath": "/legacy/index.html"

            if (REPORTS_DIR / "index.html").is_file()

            else None,

            "cacheEpoch": get_cache_epoch(),

        },

    )


