import json
import tempfile
import unittest
from pathlib import Path

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from util.last_price_sync import (  # noqa: E402
    load_last_price_sync,
    normalize_price_sync_movers,
    save_last_price_sync,
)


class LastPriceSyncCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "last_price_sync.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_overwrites_previous_result(self):
        save_last_price_sync(
            {
                "applied": True,
                "message": "first",
                "movers": {"risers": [{"id": "old"}], "fallers": []},
            },
            path=self.path,
        )
        save_last_price_sync(
            {
                "applied": True,
                "message": "second",
                "movers": {
                    "absolute": {"risers": [{"id": "new", "delta": 4}], "fallers": []},
                    "relative": {"risers": [{"id": "new", "percent": 20}], "fallers": []},
                },
                "cards": [{"id": "card-1", "artStyle": "Showcase", "delta": 4}],
            },
            path=self.path,
        )
        loaded = load_last_price_sync(path=self.path)
        self.assertEqual(loaded["message"], "second")
        self.assertEqual(loaded["movers"]["absolute"]["risers"][0]["id"], "new")
        self.assertEqual(loaded["cards"][0]["id"], "card-1")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["message"], "second")

    def test_normalizes_legacy_flat_movers(self):
        movers = normalize_price_sync_movers({
            "risers": [{"id": "up"}],
            "fallers": [{"id": "down"}],
        })
        self.assertEqual(movers["absolute"]["risers"][0]["id"], "up")
        self.assertEqual(movers["relative"]["fallers"][0]["id"], "down")


if __name__ == "__main__":
    unittest.main()
