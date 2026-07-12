from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.db import connect
from api.routers import backup, cards, deck_builder, decks, health, manager, meta, prices, reports, settings, stats, storage
from lib.config import FRONTEND_DIST
from util.schema import ensure_database_schema

OPENAPI_PATH_PREFIXES = ("docs", "redoc", "openapi.json")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = connect()
    try:
        ensure_database_schema(conn)
        conn.commit()
    finally:
        conn.close()
    yield


app = FastAPI(
    title="MTG Collection API",
    version="0.1.0",
    description=(
        "Interactive API for the MTG collection tracker (collection browser, decks, storage, "
        "stats, and price sync). Use Swagger UI below to explore endpoints and try requests."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Service health checks."},
        {"name": "meta", "description": "App metadata (price freshness, cache epoch)."},
        {"name": "settings", "description": "User preferences and favourites."},
        {"name": "reports", "description": "Collection report payloads for the UI."},
        {"name": "stats", "description": "Aggregated collection statistics."},
        {"name": "decks", "description": "Commander deck lists and browse data."},
        {"name": "builder", "description": "Commander deck builder and generation."},
        {"name": "cards", "description": "Single-card detail lookups."},
        {"name": "manager", "description": "Set manager: ownership, art styles, favourites."},
        {"name": "storage", "description": "Physical storage locations and assignments."},
        {"name": "prices", "description": "Cardmarket price sync."},
        {"name": "backup", "description": "Collection backup export and restore."},
    ],
)


@app.get("/api/docs", include_in_schema=False)
async def api_docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "X-Cache-Epoch", "Cache-Control"],
)

app.include_router(health.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(storage.router, prefix="/api")
app.include_router(manager.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(decks.router, prefix="/api")
app.include_router(deck_builder.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(backup.router, prefix="/api")


def _mount_frontend() -> None:
    if not FRONTEND_DIST.is_dir():
        return

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        root_segment = full_path.split("/", 1)[0] if full_path else ""
        if root_segment in OPENAPI_PATH_PREFIXES or full_path.startswith("docs/"):
            raise HTTPException(status_code=404, detail="Not found")

        if full_path:
            candidate = FRONTEND_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)

        index_file = FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend build not found")


_mount_frontend()
