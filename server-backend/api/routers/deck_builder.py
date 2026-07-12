import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import get_db
from api.http_cache import serve_cached_json
from api.schemas import BuilderGenerateRequest, BuilderPoolPreview
from api.services import deck_builder_service
from api.services.deck_builder_service import DeckBuilderError
from api.services.deck_generation_service import generate_deck_proposal

router = APIRouter(prefix="/builder", tags=["builder"])


def _builder_error(exc: DeckBuilderError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/commanders")
def list_commanders(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=100),
):
    return serve_cached_json(
        request,
        namespace="builder.commanders",
        params={"q": q, "page": page, "pageSize": pageSize},
        ttl=30,
        loader=lambda: deck_builder_service.list_owned_commanders(
            conn,
            search=q,
            page=page,
            page_size=pageSize,
        ),
    )


@router.post("/pool/preview")
def preview_pool(body: BuilderPoolPreview, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return deck_builder_service.preview_pool(
            conn,
            location_slugs=body.locationSlugs,
            include_deck_storage=body.includeDeckStorage,
        )
    except DeckBuilderError as exc:
        raise _builder_error(exc) from exc


@router.post("/generate")
def generate_deck(body: BuilderGenerateRequest, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return generate_deck_proposal(
            conn,
            commanders=[
                {
                    "setCode": commander.setCode,
                    "collectorNumber": commander.collectorNumber,
                    "finish": commander.finish,
                }
                for commander in body.commanders
            ],
            location_slugs=body.locationSlugs,
            include_deck_storage=body.includeDeckStorage,
            land_count=body.landCount,
            budget_cap=body.budgetCap,
            exclude_categories=body.excludeCategories,
        )
    except DeckBuilderError as exc:
        raise _builder_error(exc) from exc
