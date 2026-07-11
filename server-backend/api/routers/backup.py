import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from api.deps import get_db
from api.schemas import BackupCatalogSyncRequest
from api.services import backup_service
from api.services.backup_service import BackupImportError

router = APIRouter(prefix="/backup", tags=["backup"])


def _export_filename() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"mtg-collection-{stamp}.mtgbackup.zip"


@router.get("/export")
def export_collection(conn: sqlite3.Connection = Depends(get_db)) -> Response:
    payload = backup_service.build_export_bytes(conn)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{_export_filename()}"',
        },
    )


@router.post("/preview")
async def preview_collection_backup(
    file: UploadFile = File(...),
) -> dict:
    data = await file.read()
    try:
        return backup_service.preview_import_file(data)
    except BackupImportError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/import")
async def import_collection_backup(
    file: UploadFile = File(...),
    mode: str = Form("replace"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    normalized_mode = (mode or "replace").strip().lower()
    if normalized_mode not in {"replace", "merge"}:
        raise HTTPException(status_code=400, detail="Import mode must be 'replace' or 'merge'")

    data = await file.read()
    try:
        return backup_service.import_backup_file(conn, data, mode=normalized_mode)
    except BackupImportError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/sync-catalogs")
def sync_backup_catalogs(
    body: BackupCatalogSyncRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return backup_service.sync_catalogs_for_sets(conn, body.setCodes)
