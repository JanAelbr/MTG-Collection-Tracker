import json
from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from api.cache import build_etag, get_cache_epoch, memory_cache

DEFAULT_TTL_SECONDS = 120


def cache_headers(*, etag: str, ttl: int, epoch: int) -> dict[str, str]:
    return {
        "ETag": etag,
        "Cache-Control": "private, no-store",
        "X-Cache-Epoch": str(epoch),
    }


def serve_cached_json(
    request: Request,
    *,
    namespace: str,
    params: Any,
    ttl: int = DEFAULT_TTL_SECONDS,
    loader: Callable[[], Any],
) -> Response:
    epoch = get_cache_epoch()
    cache_key = memory_cache.make_key(namespace, params, epoch)
    etag = build_etag(epoch, cache_key)

    if request.headers.get("if-none-match") == etag:
        cached = memory_cache.get(cache_key)
        if cached is not None:
            return Response(status_code=304, headers=cache_headers(etag=etag, ttl=ttl, epoch=epoch))

    cached = memory_cache.get(cache_key)
    if cached is None:
        cached = loader()
        memory_cache.set(cache_key, cached, ttl)

    return JSONResponse(
        content=cached,
        headers=cache_headers(etag=etag, ttl=ttl, epoch=epoch),
    )
