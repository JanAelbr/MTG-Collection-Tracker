import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.db_migrate import ensure_card_columns  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402
from util.tracked_sets import add_tracked_set  # noqa: E402


def _seed_test_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_app_tables(conn)
    ensure_storage_tables(conn)
    ensure_deck_tables(conn)
    conn.executescript(
        """
        CREATE TABLE cards (
            id TEXT PRIMARY KEY,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            name TEXT NOT NULL,
            art_style TEXT,
            image_uri TEXT,
            cardmarket_url TEXT,
            market_value REAL,
            market_value_foil REAL,
            market_value_etched REAL,
            has_nonfoil INTEGER,
            has_foil INTEGER,
            has_etched INTEGER,
            colors TEXT,
            type_line TEXT,
            card_type TEXT
        );
        CREATE TABLE purchases (
            purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            purchase_value REAL NOT NULL DEFAULT 0,
            finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
            UNIQUE (set_code, collector_number, finish)
        );
        CREATE TABLE card_prices (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
            price REAL NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('scryfall', 'cardmarket')),
            price_date TEXT NOT NULL,
            UNIQUE (set_code, collector_number, finish, source, price_date)
        );
        CREATE TABLE sets (
            set_code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            released_at TEXT,
            scryfall_uri TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    ensure_card_columns(conn)
    add_tracked_set(conn, "LTR")
    conn.execute(
        """
        INSERT INTO cards (
            id, set_code, collector_number, name, art_style,
            market_value, market_value_foil, market_value_etched,
            has_nonfoil, has_foil, has_etched,
            colors, type_line, card_type, image_uri, cardmarket_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "LTR-1",
            "LTR",
            "1",
            "Test Card",
            "Main",
            2.0,
            4.0,
            None,
            1,
            1,
            0,
            '["W"]',
            "Creature",
            "Creature",
            "https://example.test/card.jpg",
            "",
        ),
    )
    conn.execute(
        "INSERT INTO sets (set_code, name, released_at, scryfall_uri, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("LTR", "The Lord of the Rings", "2023-06-23", "", "2024-01-01"),
    )
    conn.execute(
        "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, ?, ?)",
        ("LTR", "1", 1.5, 1),
    )
    conn.execute(
        "INSERT INTO user_settings (key, value) VALUES (?, ?)",
        ("favorite_sets", json.dumps(["LTR"])),
    )
    conn.commit()
    conn.close()


class FavoritesApiTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        _seed_test_db(self.db_path)
        self.db_patch = patch("api.db.DB_PATH", self.db_path)
        self.db_patch.start()
        # report loaders import DB_PATH by value — patch each consumer module.
        self.extra_patches = [
            patch("lib.config.DB_PATH", self.db_path),
            patch("report.report_data.DB_PATH", self.db_path),
            patch("report.ranked_cards_data.DB_PATH", self.db_path),
            patch("report.manager_data.DB_PATH", self.db_path),
        ]
        for item in self.extra_patches:
            item.start()
        from api.cache import memory_cache

        memory_cache.clear()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        for item in self.extra_patches:
            item.stop()
        self.db_patch.stop()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_toggle_favorite_card_and_list(self):
        first = self.client.post(
            "/api/favorites/cards",
            json={"setCode": "LTR", "collectorNumber": "1", "finish": 1},
        )
        self.assertEqual(first.status_code, 200)
        body = first.json()
        self.assertTrue(body["favorite"])
        self.assertEqual(len(body["favoriteCards"]), 1)

        listed = self.client.get("/api/favorites")
        self.assertEqual(listed.status_code, 200)
        payload = listed.json()
        self.assertEqual(len(payload["sets"]), 1)
        self.assertEqual(payload["sets"][0]["setCode"], "LTR")
        self.assertEqual(len(payload["cards"]), 1)
        self.assertEqual(payload["cards"][0]["name"], "Test Card")
        self.assertTrue(payload["cards"][0]["owned"])
        self.assertFalse(payload["cards"][0]["missing"])

        second = self.client.post(
            "/api/favorites/cards",
            json={"setCode": "LTR", "collectorNumber": "1", "finish": 1},
        )
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["favorite"])
        self.assertEqual(second.json()["favoriteCards"], [])

    def test_toggle_favorite_art_style(self):
        first = self.client.post(
            "/api/favorites/art-styles",
            json={"setCode": "LTR", "artStyle": "Main"},
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["favorite"])

        listed = self.client.get("/api/favorites")
        self.assertEqual(listed.status_code, 200)
        styles = listed.json()["artStyles"]
        self.assertEqual(len(styles), 1)
        self.assertEqual(styles[0]["artStyle"], "Main")
        self.assertEqual(styles[0]["setCode"], "LTR")

        settings = self.client.get("/api/settings")
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(
            settings.json()["favoriteArtStyles"],
            [{"setCode": "LTR", "artStyle": "Main"}],
        )


if __name__ == "__main__":
    unittest.main()
