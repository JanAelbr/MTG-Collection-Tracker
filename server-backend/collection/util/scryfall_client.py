"""Daily on-disk cache for Scryfall API responses."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import requests

from lib.config import DATA_DIR
from lib.run_log import get_logger
from util.http_client import format_request_url, http_get

log = get_logger(__name__)

SCRYFALL_CACHE_DIR = DATA_DIR / "scryfall_cache"
CACHEABLE_STATUS_CODES = frozenset({200, 404})


def cache_dir_for_date(cache_date: date | None = None, *, root: Path | None = None) -> Path:
    stamp = (cache_date or date.today()).isoformat()
    return (root or SCRYFALL_CACHE_DIR) / stamp


def cache_path_for_url(
    url: str,
    *,
    cache_date: date | None = None,
    root: Path | None = None,
) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir_for_date(cache_date, root=root) / f"{digest}.json"


def _response_from_cache(url: str, status_code: int, body: str) -> requests.Response:
    response = requests.Response()
    response.url = url
    response.status_code = status_code
    response._content = body.encode("utf-8")
    response.encoding = "utf-8"
    return response


def read_cached_response(cache_path: Path) -> requests.Response | None:
    if not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        url = payload["url"]
        status_code = int(payload["status_code"])
        body = payload["body"]
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None
    return _response_from_cache(url, status_code, body)


def write_cached_response(cache_path: Path, url: str, response: requests.Response) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "url": url,
        "status_code": response.status_code,
        "body": response.text,
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")


def scryfall_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
    logger: logging.Logger | None = None,
    label: str | None = None,
    force: bool = False,
    cache_date: date | None = None,
    cache_root: Path | None = None,
    **kwargs: Any,
) -> requests.Response:
    """GET a Scryfall URL, using a per-day on-disk cache when available."""
    request_log = logger or log
    display_url = format_request_url(url, params)
    cache_path = cache_path_for_url(display_url, cache_date=cache_date, root=cache_root)

    if not force:
        cached = read_cached_response(cache_path)
        if cached is not None:
            if label:
                request_log.info("Scryfall cache hit %s (%s)", display_url, label)
            else:
                request_log.info("Scryfall cache hit %s", display_url)
            return cached

    response = http_get(
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        logger=request_log,
        label=label,
        **kwargs,
    )
    if response.status_code in CACHEABLE_STATUS_CODES:
        write_cached_response(cache_path, display_url, response)
    return response
