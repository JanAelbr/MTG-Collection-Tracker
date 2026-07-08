"""Logged HTTP helpers for external API calls."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

import requests

from lib.run_log import get_logger

log = get_logger(__name__)


# Build a display URL including query parameters.
def format_request_url(url: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return url
    parsed = urlparse(url)
    query = urlencode(params, doseq=True)
    if parsed.query:
        query = f"{parsed.query}&{query}"
    return urlunparse(parsed._replace(query=query))


# Perform a GET request and log the URL and response status at INFO level.
def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
    logger: logging.Logger | None = None,
    label: str | None = None,
    **kwargs: Any,
) -> requests.Response:
    request_log = logger or log
    display_url = format_request_url(url, params)
    if label:
        request_log.info("HTTP GET %s (%s)", display_url, label)
    else:
        request_log.info("HTTP GET %s", display_url)
    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        **kwargs,
    )
    request_log.info("HTTP GET %s -> HTTP %s", display_url, response.status_code)
    return response
