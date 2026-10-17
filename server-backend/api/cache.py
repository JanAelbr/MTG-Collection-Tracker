"""Process-wide response cache scoped per profile.

Two kinds of epoch exist: one for the shared catalog (prices, sets, art style
rules) and one per profile (purchases, decks, storage, settings). The public
epoch for a request is the opaque string ``"<catalog>.<profile>"`` so a change
to either invalidates ETags and cache keys. Cache entries are partitioned by
profile, so a profile mutation only drops that profile's entries.
"""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any

from lib.profile_context import get_current_profile_id

_lock = threading.RLock()
_catalog_epoch = 0
_profile_epochs: dict[str, int] = {}

GLOBAL_PARTITION = ""


def _partition(profile_id: str | None = None) -> str:
    return profile_id if profile_id is not None else (get_current_profile_id() or GLOBAL_PARTITION)


def get_catalog_epoch() -> int:
    with _lock:
        return _catalog_epoch


def get_profile_epoch(profile_id: str | None = None) -> int:
    with _lock:
        return _profile_epochs.get(_partition(profile_id), 0)


def get_cache_epoch(profile_id: str | None = None) -> str:
    partition = _partition(profile_id)
    with _lock:
        return f"{_catalog_epoch}.{_profile_epochs.get(partition, 0)}"


def bump_cache_epoch(profile_id: str | None = None) -> str:
    """Invalidate the current (or given) profile's cached responses."""
    partition = _partition(profile_id)
    with _lock:
        _profile_epochs[partition] = _profile_epochs.get(partition, 0) + 1
        memory_cache.clear_partition(partition)
        return f"{_catalog_epoch}.{_profile_epochs[partition]}"


def bump_catalog_epoch() -> str:
    """Invalidate every profile's cached responses (shared catalog changed)."""
    global _catalog_epoch
    with _lock:
        _catalog_epoch += 1
        memory_cache.clear()
        return get_cache_epoch()


class MemoryCache:
    def __init__(self, max_entries: int = 256) -> None:
        self._max_entries = max_entries
        self._partitions: dict[str, OrderedDict[str, tuple[Any, float]]] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._partitions.clear()

    def clear_partition(self, partition: str) -> None:
        with self._lock:
            self._partitions.pop(partition, None)

    def make_key(self, namespace: str, params: Any, epoch: Any) -> str:
        partition = _partition()
        payload = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(
            f"{partition}:{epoch}:{namespace}:{payload}".encode()
        ).hexdigest()[:16]
        return f"{partition}|{namespace}:{digest}"

    @staticmethod
    def _split(key: str) -> str:
        partition, sep, _rest = key.partition("|")
        return partition if sep else GLOBAL_PARTITION

    def get(self, key: str) -> Any | None:
        with self._lock:
            entries = self._partitions.get(self._split(key))
            if not entries:
                return None
            entry = entries.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del entries[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            entries = self._partitions.setdefault(self._split(key), OrderedDict())
            if len(entries) >= self._max_entries and key not in entries:
                entries.popitem(last=False)
            entries[key] = (value, time.monotonic() + ttl_seconds)


memory_cache = MemoryCache()


def build_etag(epoch: Any, cache_key: str) -> str:
    digest = hashlib.sha256(cache_key.encode()).hexdigest()[:12]
    return f'W/"{epoch}-{digest}"'
