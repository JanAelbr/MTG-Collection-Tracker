import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.schemas import ScanArtSearch, ScanIngest
from api.services.scan_service import ScanError, ingest_scan, search_card_names_for_ocr
from util.art_hash import fill_missing_art_hashes, search_prints_by_art_hash
from util.db_migrate import ensure_card_columns, ensure_card_indexes

router = APIRouter(prefix="/scan", tags=["scan"])


def _scan_error(exc: ScanError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/name-search")
def scan_name_search(
    conn: sqlite3.Connection = Depends(get_db),
    q: str = Query(default="", max_length=200),
    name: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=8, ge=1, le=20),
):
    """OCR-oriented quick name search (lightweight, returns ranked names + prints)."""
    try:
        return search_card_names_for_ocr(conn, query=q, name=name, limit=limit)
    except ScanError as exc:
        raise _scan_error(exc) from exc


@router.post("/art-search")
def scan_art_search(body: ScanArtSearch, conn: sqlite3.Connection = Depends(get_db)):
    """Match a camera art fingerprint against catalog preview hashes."""
    ensure_card_columns(conn)
    ensure_card_indexes(conn)
    try:
        return search_prints_by_art_hash(
            conn,
            body.artHash,
            limit=int(body.limit if body.limit is not None else 12),
            build_missing=bool(body.buildMissing if body.buildMissing is not None else True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/art-index")
def scan_art_index(
    conn: sqlite3.Connection = Depends(get_db),
    limit: int = Query(default=80, ge=1, le=300),
):
    """Build more art hashes from catalog preview images."""
    ensure_card_columns(conn)
    ensure_card_indexes(conn)
    built = fill_missing_art_hashes(conn, limit=limit)
    from util.art_hash import art_hash_coverage

    return {"hashesBuilt": built, "coverage": art_hash_coverage(conn)}


@router.post("/ingest")
def scan_ingest(body: ScanIngest, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return ingest_scan(
            conn,
            set_code=body.setCode,
            collector_number=body.collectorNumber,
            finish=int(body.finish if body.finish is not None else 0),
            name_hint=body.nameHint,
        )
    except ScanError as exc:
        raise _scan_error(exc) from exc
