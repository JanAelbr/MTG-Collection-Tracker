import re
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from api.deps import get_db
from api.schemas import BackupCatalogSyncRequest
from api.services import backup_service
from api.services.backup_service import BackupImportError

router = APIRouter(prefix="/backup", tags=["backup"])


def export_filename(profile_name: str | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", str(profile_name or "").lower()).strip("-")
    suffix = f"-{slug}" if slug else ""
    return f"mtg-collection{suffix}-{stamp}.mtgbackup.zip"


def backup_zip_response(payload: bytes, profile_name: str | None = None) -> Response:
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{export_filename(profile_name)}"',
        },
    )


@router.get("/export")
def export_collection(conn: sqlite3.Connection = Depends(get_db)) -> Response:
    profile = backup_service.current_profile_manifest()
    payload = backup_service.build_export_bytes(conn, profile=profile)
    return backup_zip_response(payload, (profile or {}).get("name"))


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
