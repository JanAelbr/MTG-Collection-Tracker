import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.cache import bump_cache_epoch, get_cache_epoch, memory_cache  # noqa: E402
from api.http_cache import serve_cached_json  # noqa: E402


class CacheTests(unittest.TestCase):
    def setUp(self):
        memory_cache.clear()

    def test_bump_cache_epoch_increments(self):
        first = get_cache_epoch()
        second = bump_cache_epoch()
        self.assertEqual(second, first + 1)

    def test_serve_cached_json_reuses_loader(self):
        request = Mock(headers={})
        loader = Mock(return_value={"value": 1})

        first = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 1},
            ttl=60,
            loader=loader,
        )
        second = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 1},
            ttl=60,
            loader=loader,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.headers["ETag"], second.headers["ETag"])
        loader.assert_called_once()

    def test_serve_cached_json_returns_304_when_etag_matches(self):
        request = Mock(headers={})
        loader = Mock(return_value={"value": 1})

        first = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 2},
            ttl=60,
            loader=loader,
        )
        etag = first.headers["ETag"]

        cached_request = Mock(headers={"if-none-match": etag})
        second = serve_cached_json(
            cached_request,
            namespace="test.payload",
            params={"id": 2},
            ttl=60,
            loader=loader,
        )

        self.assertEqual(second.status_code, 304)
        loader.assert_called_once()

    def test_bump_invalidates_cached_payload(self):
        request = Mock(headers={})
        loader = Mock(side_effect=[{"value": 1}, {"value": 2}])

        first = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 3},
            ttl=60,
            loader=loader,
        )
        bump_cache_epoch()
        second = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 3},
            ttl=60,
            loader=loader,
        )

        self.assertNotEqual(first.headers["ETag"], second.headers["ETag"])
        self.assertEqual(loader.call_count, 2)


if __name__ == "__main__":
    unittest.main()
