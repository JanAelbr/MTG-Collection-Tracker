import runpy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.cache import bump_cache_epoch, get_cache_epoch, memory_cache  # noqa: E402
from api.http_cache import serve_cached_json, with_price_strategy  # noqa: E402
from api.services import settings_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402


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

    def test_price_strategy_update_does_not_bump_epoch(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        conn = sqlite3.connect(Path(temp_dir.name) / "test.db")
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        ensure_app_tables(conn)
        conn.commit()

        epoch_before = get_cache_epoch()
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES ('price_strategy', 'avg7')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )
        conn.commit()
        epoch_after = get_cache_epoch()
        self.assertEqual(epoch_before, epoch_after)
        self.assertEqual(settings_service.get_price_strategy(conn), "avg7")

    def test_serve_cached_json_separates_price_strategy(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        conn = sqlite3.connect(Path(temp_dir.name) / "test.db")
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        ensure_app_tables(conn)
        conn.commit()

        request = Mock(headers={})
        loader = Mock(side_effect=[{"strategy": "trend"}, {"strategy": "avg7"}])

        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES ('price_strategy', 'trend')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )
        conn.commit()
        first = serve_cached_json(
            request,
            namespace="test.pricing",
            params=with_price_strategy(conn, {"id": 1}),
            ttl=60,
            loader=loader,
        )
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES ('price_strategy', 'avg7')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )
        conn.commit()
        second = serve_cached_json(
            request,
            namespace="test.pricing",
            params=with_price_strategy(conn, {"id": 1}),
            ttl=60,
            loader=loader,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(first.headers["ETag"], second.headers["ETag"])
        self.assertEqual(loader.call_count, 2)


if __name__ == "__main__":
    unittest.main()
