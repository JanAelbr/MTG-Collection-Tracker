import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.scryfall_client import (  # noqa: E402
    cache_path_for_url,
    read_cached_response,
    scryfall_get,
    write_cached_response,
)


class ScryfallClientTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_root = Path(self.temp_dir.name) / "scryfall_cache"
        self.cache_date = date(2026, 6, 11)
        self.url = "https://api.scryfall.com/sets/plst"
        self.cache_path = cache_path_for_url(
            self.url,
            cache_date=self.cache_date,
            root=self.cache_root,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cache_path_is_stable_for_same_url(self):
        first = cache_path_for_url(self.url, cache_date=self.cache_date, root=self.cache_root)
        second = cache_path_for_url(self.url, cache_date=self.cache_date, root=self.cache_root)
        self.assertEqual(first, second)
        self.assertIn("2026-06-11", str(first))

    def test_write_and_read_cached_response(self):
        response = MagicMock()
        response.status_code = 200
        response.text = '{"code":"plst"}'
        write_cached_response(self.cache_path, self.url, response)

        cached = read_cached_response(self.cache_path)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.status_code, 200)
        self.assertEqual(cached.json(), {"code": "plst"})

    @patch("util.scryfall_client.http_get")
    def test_scryfall_get_uses_cache_without_network(self, http_get_mock):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(
                {
                    "url": self.url,
                    "status_code": 200,
                    "body": '{"object":"set","code":"plst"}',
                }
            ),
            encoding="utf-8",
        )

        response = scryfall_get(
            self.url,
            cache_date=self.cache_date,
            cache_root=self.cache_root,
        )

        http_get_mock.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], "plst")

    @patch("util.scryfall_client.http_get")
    def test_scryfall_get_writes_cache_on_miss(self, http_get_mock):
        response = MagicMock()
        response.status_code = 200
        response.text = '{"object":"set","code":"plst"}'
        http_get_mock.return_value = response

        result = scryfall_get(
            self.url,
            cache_date=self.cache_date,
            cache_root=self.cache_root,
        )

        http_get_mock.assert_called_once()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(self.cache_path.is_file())
        cached = read_cached_response(self.cache_path)
        self.assertEqual(cached.json()["code"], "plst")

    @patch("util.scryfall_client.http_get")
    def test_scryfall_get_force_bypasses_cache(self, http_get_mock):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(
                {
                    "url": self.url,
                    "status_code": 200,
                    "body": '{"code":"old"}',
                }
            ),
            encoding="utf-8",
        )
        response = MagicMock()
        response.status_code = 200
        response.text = '{"code":"new"}'
        response.json.return_value = {"code": "new"}
        http_get_mock.return_value = response

        result = scryfall_get(
            self.url,
            cache_date=self.cache_date,
            cache_root=self.cache_root,
            force=True,
        )

        http_get_mock.assert_called_once()
        self.assertEqual(result.json()["code"], "new")

    @patch("util.scryfall_client.http_get")
    def test_scryfall_get_does_not_cache_transient_errors(self, http_get_mock):
        response = MagicMock()
        response.status_code = 503
        response.text = "Service unavailable"
        http_get_mock.return_value = response

        scryfall_get(
            self.url,
            cache_date=self.cache_date,
            cache_root=self.cache_root,
        )

        self.assertFalse(self.cache_path.is_file())

    @patch("util.scryfall_client.http_get")
    def test_scryfall_get_caches_404(self, http_get_mock):
        response = MagicMock()
        response.status_code = 404
        response.text = '{"object":"error","code":"not_found"}'
        http_get_mock.return_value = response

        first = scryfall_get(
            self.url,
            cache_date=self.cache_date,
            cache_root=self.cache_root,
        )
        second = scryfall_get(
            self.url,
            cache_date=self.cache_date,
            cache_root=self.cache_root,
        )

        http_get_mock.assert_called_once()
        self.assertEqual(first.status_code, 404)
        self.assertEqual(second.status_code, 404)


if __name__ == "__main__":
    unittest.main()
