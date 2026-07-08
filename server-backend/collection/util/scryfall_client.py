"""Daily on-disk cache for Scryfall API responses."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import requests

from lib.config import DATA_DIR
from lib.run_log import get_logger
from util.http_client import format_request_url, http_get

log = get_logger(__name__)

SCRYFALL_CACHE_DIR = DATA_DIR / "scryfall_cache"
CACHE_DATE_MARKER = ".cache_date"
CACHEABLE_STATUS_CODES = frozenset({200, 404})


def _cache_root(root: Path | None = None) -> Path:
    return root or SCRYFALL_CACHE_DIR


def _read_cache_marker(cache_root: Path) -> str:
    marker_path = cache_root / CACHE_DATE_MARKER
    try:
        return marker_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _cache_is_current(cache_root: Path, cache_date: date | None = None) -> bool:
    stamp = (cache_date or date.today()).isoformat()
    return _read_cache_marker(cache_root) == stamp


def _reset_cache_for_date(cache_root: Path, cache_date: date | None = None) -> None:
    cache_root.mkdir(parents=True, exist_ok=True)
    stamp = (cache_date or date.today()).isoformat()
    for entry in cache_root.iterdir():
        if entry.name == CACHE_DATE_MARKER:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    (cache_root / CACHE_DATE_MARKER).write_text(stamp, encoding="utf-8")


def _ensure_current_day_cache(
    cache_root: Path,
    *,
    cache_date: date | None = None,
) -> None:
    if _cache_is_current(cache_root, cache_date):
        cache_root.mkdir(parents=True, exist_ok=True)
        return
    _reset_cache_for_date(cache_root, cache_date)


def cache_path_for_url(
    url: str,
    *,
    cache_date: date | None = None,
    root: Path | None = None,
) -> Path:
    cache_root = _cache_root(root)
    _ensure_current_day_cache(cache_root, cache_date=cache_date)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_root / f"{digest}.json"


def _response_from_cache(url: str, status_code: int, body: str) -> requests.Response:
    response = requests.Response()
    response.url = url
    response.status_code = status_code
    response._content = body.encode("utf-8")
    response.encoding = "utf-8"
    return response


def read_cached_response(
    cache_path: Path,
    *,
    cache_date: date | None = None,
    root: Path | None = None,
) -> requests.Response | None:
    cache_root = _cache_root(root) if root is not None else cache_path.parent
    if not _cache_is_current(cache_root, cache_date):
        return None
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


def write_cached_response(
    cache_path: Path,
    url: str,
    response: requests.Response,
    *,
    cache_date: date | None = None,
    root: Path | None = None,
) -> None:
    cache_root = _cache_root(root) if root is not None else cache_path.parent
    _ensure_current_day_cache(cache_root, cache_date=cache_date)
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
    """GET a Scryfall URL, using a same-day on-disk cache when available."""
    request_log = logger or log
    display_url = format_request_url(url, params)
    resolved_root = _cache_root(cache_root)
    cache_path = cache_path_for_url(
        display_url,
        cache_date=cache_date,
        root=resolved_root,
    )

    if not force:
        cached = read_cached_response(
            cache_path,
            cache_date=cache_date,
            root=resolved_root,
        )
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
        write_cached_response(
            cache_path,
            display_url,
            response,
            cache_date=cache_date,
            root=resolved_root,
        )
    return response
