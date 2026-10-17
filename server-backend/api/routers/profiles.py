from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from api.routers.backup import backup_zip_response
from api.schemas import ProfileCreate, ProfileReorder, ProfileUpdate
from api.services import profile_service
from api.services.profile_service import ProfileError
from util.profile_registry import PROFILE_COLORS

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _raise(exc: ProfileError):
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("")
def list_profiles(stats: bool = False) -> dict:
    payload = profile_service.list_profiles_payload(with_stats=stats)
    payload["colors"] = list(PROFILE_COLORS)
    return payload


@router.post("", status_code=201)
def create_profile(body: ProfileCreate) -> dict:
    try:
        return profile_service.create_profile(
            name=body.name,
            color=body.color,
            avatar=body.avatar,
            duplicate_from=body.copyFrom,
        )
    except ProfileError as exc:
        _raise(exc)


@router.put("/order")
def reorder_profiles(body: ProfileReorder) -> dict:
    return profile_service.reorder(body.profileIds)


@router.post("/import", status_code=201)
async def import_profile(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    color: str | None = Form(None),
) -> dict:
    data = await file.read()
    try:
        return profile_service.import_profile_from_backup(data, name=name, color=color)
    except ProfileError as exc:
        _raise(exc)


@router.get("/{profile_id}")
def get_profile(profile_id: str) -> dict:
    try:
        return profile_service.get_profile_payload(profile_id)
    except ProfileError as exc:
        _raise(exc)


@router.patch("/{profile_id}")
def update_profile(profile_id: str, body: ProfileUpdate) -> dict:
    try:
        return profile_service.patch_profile(
            profile_id,
            name=body.name,
            color=body.color,
            avatar=body.avatar,
            is_default=body.isDefault,
        )
    except ProfileError as exc:
        _raise(exc)


@router.delete("/{profile_id}")
def delete_profile(profile_id: str) -> dict:
    try:
        return profile_service.delete_profile(profile_id)
    except ProfileError as exc:
        _raise(exc)


@router.post("/{profile_id}/activate")
def activate_profile(profile_id: str) -> dict:
    try:
        return profile_service.activate_profile(profile_id)
    except ProfileError as exc:
        _raise(exc)


@router.get("/{profile_id}/export")
def export_profile(profile_id: str) -> Response:
    try:
        payload, name = profile_service.export_profile_backup(profile_id)
    except ProfileError as exc:
        _raise(exc)
    return backup_zip_response(payload, name)
