"""Resolve the ``X-Profile-Id`` header into the request's active profile."""

import json

from lib.db import single_database_path
from lib.profile_context import PROFILE_HEADER, reset_current_profile_id, set_current_profile_id
from util.profile_registry import get_default_profile_id, get_profile

PROFILE_EXEMPT_PREFIXES = ("/api/profiles", "/api/health")
_HEADER_KEY = PROFILE_HEADER.lower().encode("latin-1")


def _header_value(scope) -> str | None:
    for key, value in scope.get("headers") or ():
        if key == _HEADER_KEY:
            text = value.decode("latin-1").strip()
            return text or None
    return None


def _query_value(scope) -> str | None:
    """Fallback for plain links (``<a href download>``) that cannot set headers."""
    from urllib.parse import parse_qs

    raw = (scope.get("query_string") or b"").decode("latin-1")
    values = parse_qs(raw).get("profileId") or []
    return values[0].strip() if values and values[0].strip() else None


async def _send_profile_not_found(send, profile_id: str | None) -> None:
    body = json.dumps({
        "detail": {
            "code": "profile_not_found",
            "message": "Profile not found" if profile_id else "No profile exists yet",
            "profileId": profile_id,
        }
    }).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin-1")),
        ],
    })
    await send({"type": "http.response.body", "body": body})


def resolve_request_profile(requested: str | None) -> str | None:
    """Return the profile id to serve, or None when it does not exist.

    This is the single seam for profile access control (e.g. a future PIN).
    """
    if requested:
        return requested if get_profile(requested) else None
    return get_default_profile_id()


class ProfileContextMiddleware:
    """Pure ASGI middleware so the context var propagates into sync endpoints."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path") or ""
        if (
            scope["type"] != "http"
            or not path.startswith("/api/")
            or path.startswith(PROFILE_EXEMPT_PREFIXES)
            or single_database_path() is not None
        ):
            await self.app(scope, receive, send)
            return
        requested = _header_value(scope) or _query_value(scope)
        profile_id = resolve_request_profile(requested)
        if not profile_id:
            await _send_profile_not_found(send, requested)
            return
        token = set_current_profile_id(profile_id)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_profile_id(token)
