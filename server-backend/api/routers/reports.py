import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import get_db
from api.http_cache import serve_cached_json
from api.services.reports_service import ReportsError, load_reports_meta, list_report_cards
from api.services.search_service import (
    _parse_color_filters,
    _parse_optional_float,
    _parse_storage_filters,
    list_name_variants,
    search_cards,
)

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
    try:
        return list_report_cards(
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
        )
    except ReportsError as exc:
        raise _reports_error(exc) from exc


@router.get("/search")
def report_search(
    conn: sqlite3.Connection = Depends(get_db),
    q: str = Query(default=""),
    text: str = Query(default=""),
    creatureType: str = Query(default=""),
    setCode: str = Query(default="All"),
    ownedFilter: str = Query(default="all"),
    foilFilter: str = Query(default="all"),
    type: str = Query(default="all"),
    colors: str = Query(default=""),
    rarity: str = Query(default="all"),
    cmcMin: str = Query(default=""),
    cmcMax: str = Query(default=""),
    priceMin: str = Query(default=""),
    priceMax: str = Query(default=""),
    powMin: str = Query(default=""),
    tghMin: str = Query(default=""),
    storage: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=100),
):
    try:
        return search_cards(
            conn,
            search=q,
            text_search=text,
            creature_type_search=creatureType,
            set_code=setCode,
            owned_filter=ownedFilter,
            foil_filter=foilFilter,
            type_filter=type,
            color_filters=_parse_color_filters(colors),
            rarity_filter=rarity,
            cmc_min=_parse_optional_float(cmcMin),
            cmc_max=_parse_optional_float(cmcMax),
            price_min=_parse_optional_float(priceMin),
            price_max=_parse_optional_float(priceMax),
            power_min=_parse_optional_float(powMin),
            toughness_min=_parse_optional_float(tghMin),
            storage_filters=_parse_storage_filters(storage),
            page=page,
            page_size=pageSize,
        )
    except ReportsError as exc:
        raise _reports_error(exc) from exc


@router.get("/search/variants")
def report_search_variants(
    conn: sqlite3.Connection = Depends(get_db),
    name: str = Query(..., min_length=1),
    setCode: str = Query(default="All"),
    ownedFilter: str = Query(default="all"),
    foilFilter: str = Query(default="all"),
    type: str = Query(default="all"),
    colors: str = Query(default=""),
    rarity: str = Query(default="all"),
    cmcMin: str = Query(default=""),
    cmcMax: str = Query(default=""),
    priceMin: str = Query(default=""),
    priceMax: str = Query(default=""),
    powMin: str = Query(default=""),
    tghMin: str = Query(default=""),
    storage: str = Query(default=""),
):
    try:
        return list_name_variants(
            conn,
            name=name,
            set_code=setCode,
            owned_filter=ownedFilter,
            foil_filter=foilFilter,
            type_filter=type,
            color_filters=_parse_color_filters(colors),
            rarity_filter=rarity,
            cmc_min=_parse_optional_float(cmcMin),
            cmc_max=_parse_optional_float(cmcMax),
            price_min=_parse_optional_float(priceMin),
            price_max=_parse_optional_float(priceMax),
            power_min=_parse_optional_float(powMin),
            toughness_min=_parse_optional_float(tghMin),
            storage_filters=_parse_storage_filters(storage),
        )
    except ReportsError as exc:
        raise _reports_error(exc) from exc
