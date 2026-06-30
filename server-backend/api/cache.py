import hashlib
import json
import threading
import time
from typing import Any

_lock = threading.Lock()
_epoch = 0


def get_cache_epoch() -> int:
    with _lock:
        return _epoch


def bump_cache_epoch() -> int:
    global _epoch
    with _lock:
        _epoch += 1
        memory_cache.clear()
        return _epoch


class MemoryCache:
    def __init__(self, max_entries: int = 256) -> None:
        self._max_entries = max_entries
        self._entries: dict[str, tuple[Any, float]] = {}

    def clear(self) -> None:
        self._entries.clear()

    def make_key(self, namespace: str, params: Any, epoch: int) -> str:
        payload = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{epoch}:{namespace}:{payload}".encode()).hexdigest()[:16]
        return f"{namespace}:{digest}"

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if len(self._entries) >= self._max_entries and key not in self._entries:
            oldest_key = next(iter(self._entries))
            del self._entries[oldest_key]
        self._entries[key] = (value, time.monotonic() + ttl_seconds)


memory_cache = MemoryCache()


def build_etag(epoch: int, cache_key: str) -> str:
    digest = hashlib.sha256(cache_key.encode()).hexdigest()[:12]
    return f'W/"{epoch}-{digest}"'
