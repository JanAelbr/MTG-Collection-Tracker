import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import get_db
from api.http_cache import serve_cached_json
from api.schemas import (
    BuilderAssessPowerRequest,
    BuilderGenerateRequest,
    BuilderImproveRequest,
    BuilderPoolPreview,
)
from api.services import deck_builder_service, decks_service
from api.services.deck_builder_service import DeckBuilderError
from api.services.deck_generation_service import generate_deck_proposal, improve_deck_proposal
from api.services.decks_service import DeckError

router = APIRouter(prefix="/builder", tags=["builder"])


def _builder_error(exc: DeckBuilderError | DeckError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/commanders")
def list_commanders(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=100),
    colors: str = Query(default=""),
    uniquePrints: bool = Query(default=True),
):
    color_list = [part.strip().upper() for part in colors.split(",") if part.strip()]
    return serve_cached_json(
        request,
        namespace="builder.commanders",
        params={
            "q": q,
            "page": page,
            "pageSize": pageSize,
            "colors": ",".join(color_list),
            "uniquePrints": uniquePrints,
        },
        ttl=30,
        loader=lambda: deck_builder_service.list_owned_commanders(
            conn,
            search=q,
            page=page,
            page_size=pageSize,
            colors=color_list,
            unique_prints=uniquePrints,
        ),
    )


@router.get("/presets")
def list_presets():
    return deck_builder_service.list_slot_presets()


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
            slot_counts=body.slotCounts,
            preset=body.preset,
        )
    except DeckBuilderError as exc:
        raise _builder_error(exc) from exc


@router.post("/improve")
def improve_deck(body: BuilderImproveRequest, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return decks_service.improve_existing_deck(
            conn,
            deck_id=body.deckId,
            location_slugs=body.locationSlugs,
            include_deck_storage=body.includeDeckStorage,
            land_count=body.landCount,
            budget_cap=body.budgetCap,
            exclude_categories=body.excludeCategories,
            slot_counts=body.slotCounts,
            preset=body.preset,
            rebuild=body.rebuild,
        )
    except (DeckBuilderError, DeckError) as exc:
        raise _builder_error(exc) from exc


@router.post("/assess-power")
def assess_builder_power(body: BuilderAssessPowerRequest, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return deck_builder_service.assess_builder_proposal(
            conn,
            commanders=[
                {
                    "setCode": commander.setCode,
                    "collectorNumber": commander.collectorNumber,
                    "finish": commander.finish,
                }
                for commander in body.commanders
            ],
            cards=body.cards,
        )
    except DeckBuilderError as exc:
        raise _builder_error(exc) from exc
