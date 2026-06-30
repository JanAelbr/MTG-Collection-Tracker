import sqlite3



from fastapi import APIRouter, Depends, HTTPException, Query, Request



from api.deps import get_db

from api.http_cache import serve_cached_json

from api.services.reports_service import ReportsError, load_reports_meta, list_report_cards
from api.services.search_service import list_name_variants, random_name_explore, search_cards



router = APIRouter(prefix="/reports", tags=["reports"])





def _reports_error(exc: ReportsError) -> HTTPException:

    return HTTPException(status_code=exc.status_code, detail=exc.message)





@router.get("/meta")

def reports_meta(request: Request, conn: sqlite3.Connection = Depends(get_db)):

    return serve_cached_json(

        request,

        namespace="reports.meta",

        params={},

        ttl=120,

        loader=lambda: load_reports_meta(conn),

    )





@router.get("/cards")

def report_cards(

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

    report: str = Query(default="top"),

    setCode: str = Query(default="All"),

    artStyle: str = Query(default=""),

    ownedFilter: str = Query(default="owned"),

    foilFilter: str = Query(default="all"),

    typeFilter: str = Query(default="all"),

    colors: str = Query(default=""),

    compareDate: str | None = Query(default=None),

    pageSize: int = Query(default=25, ge=1, le=500),

):

    params = {

        "report": report,

        "setCode": setCode,

        "artStyle": artStyle,

        "ownedFilter": ownedFilter,

        "foilFilter": foilFilter,

        "typeFilter": typeFilter,

        "colors": colors,

        "compareDate": compareDate,

        "pageSize": pageSize,

    }

    try:

        return serve_cached_json(

            request,

            namespace="reports.cards",

            params=params,

            ttl=120,

            loader=lambda: list_report_cards(

                conn,

                report=report,

                set_code=setCode,

                art_style=artStyle,

                owned_filter=ownedFilter,

                foil_filter=foilFilter,

                type_filter=typeFilter,

                color_filters=colors,

                compare_date=compareDate,

                page_size=pageSize,

            ),

        )

    except ReportsError as exc:

        raise _reports_error(exc) from exc


@router.get("/search")

def report_search(

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

    q: str = Query(default=""),

    setCode: str = Query(default="All"),

    ownedFilter: str = Query(default="all"),

    foilFilter: str = Query(default="all"),

    page: int = Query(default=1, ge=1),

    pageSize: int = Query(default=50, ge=1, le=100),

):

    params = {

        "q": q,

        "setCode": setCode,

        "ownedFilter": ownedFilter,

        "foilFilter": foilFilter,

        "page": page,

        "pageSize": pageSize,

    }

    try:

        return serve_cached_json(

            request,

            namespace="reports.search",

            params=params,

            ttl=60,

            loader=lambda: search_cards(

                conn,

                search=q,

                set_code=setCode,

                owned_filter=ownedFilter,

                foil_filter=foilFilter,

                page=page,

                page_size=pageSize,

            ),

        )

    except ReportsError as exc:

        raise _reports_error(exc) from exc


@router.get("/search/variants")

def report_search_variants(

    request: Request,

    conn: sqlite3.Connection = Depends(get_db),

    name: str = Query(..., min_length=1),

    q: str = Query(default=""),

    setCode: str = Query(default="All"),

    ownedFilter: str = Query(default="all"),

    foilFilter: str = Query(default="all"),

):

    params = {

        "name": name,

        "q": q,

        "setCode": setCode,

        "ownedFilter": ownedFilter,

        "foilFilter": foilFilter,

    }

    try:

        return serve_cached_json(

            request,

            namespace="reports.search.variants",

            params=params,

            ttl=60,

            loader=lambda: list_name_variants(

                conn,

                name=name,

                search=q,

                set_code=setCode,

                owned_filter=ownedFilter,

                foil_filter=foilFilter,

            ),

        )

    except ReportsError as exc:

        raise _reports_error(exc) from exc


@router.get("/search/random")

def report_search_random(

    conn: sqlite3.Connection = Depends(get_db),

    q: str = Query(default=""),

    setCode: str = Query(default="All"),

    ownedFilter: str = Query(default="all"),

    foilFilter: str = Query(default="all"),

):

    try:

        return random_name_explore(

            conn,

            search=q,

            set_code=setCode,

            owned_filter=ownedFilter,

            foil_filter=foilFilter,

        )

    except ReportsError as exc:

        raise _reports_error(exc) from exc


