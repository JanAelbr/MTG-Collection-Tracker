import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.db_migrate import ensure_card_columns  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


def _seed_test_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
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
            "",
            "",
        ),
    )
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
            "LTR-2",
            "LTR",
            "2",
            "Catalog Card",
            "Main",
            1.0,
            None,
            None,
            1,
            0,
            0,
            '["U"]',
            "Instant",
            "Instant",
            "",
            "",
        ),
    )
    conn.execute(
        """
        INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
        VALUES ('LTR', '1', 1.0, 0)
        """
    )
    conn.execute(
        """
        INSERT INTO card_prices (
            set_code, collector_number, finish, price, source, price_date
        ) VALUES ('LTR', '1', 0, 1.5, 'cardmarket', '2026-06-01')
        """
    )
    conn.execute(
        """
        INSERT INTO card_instances (
            set_code, collector_number, finish, location_slug, purchase_value
        ) VALUES ('LTR', '1', 0, 'storage:general', 1.0)
        """
    )
    conn.execute(
        """
        INSERT INTO sets (set_code, name, released_at, scryfall_uri, updated_at)
        VALUES ('LTR', 'The Lord of the Rings', '2023-06-23', '', '2026-06-01')
        """
    )
    conn.execute(
        """
        INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
        VALUES ('Test Deck', 'test-deck', NULL, '2026-06-01', '2026-06-01')
        """
    )
    deck_id = conn.execute("SELECT deck_id FROM decks").fetchone()[0]
    conn.execute(
        """
        INSERT INTO deck_cards (
            deck_id, card_name, set_code, collector_number, finish, qty, owned_qty, section, sort_order, in_catalog
        ) VALUES (?, 'Test Card', 'LTR', '1', 0, 1, 1, 'main', 0, 1)
        """,
        (deck_id,),
    )
    ensure_app_tables(conn)
    conn.commit()
    conn.close()


class ApiEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        _seed_test_db(self.db_path)
        self.db_patch = patch("api.db.DB_PATH", self.db_path)
        self.config_patch = patch("lib.config.DB_PATH", self.db_path)
        self.db_patch.start()
        self.config_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.db_patch.stop()
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def _get(self, path: str) -> None:
        response = self.client.get(path)
        self.assertLess(response.status_code, 500, f"{path} -> {response.status_code}: {response.text[:300]}")

    def test_read_endpoints_do_not_error(self):
        deck_id = self.client.get("/api/decks").json()["decks"][0]["id"]
        endpoints = [
            "/api/health",
            "/api/meta",
            "/api/settings",
            "/api/favorites",
            "/api/stats/collection",
            "/api/stats/collection?setCode=LTR&finishFilter=nonfoil",
            "/api/reports/meta",
            "/api/reports/cards",
            "/api/reports/cards?report=risers&foilFilter=foil",
            "/api/reports/cards?report=fallers&foilFilter=etched",
            "/api/decks",
            "/api/decks/browse-index",
            "/api/decks/stats",
            f"/api/decks/{deck_id}/browse",
            "/api/manager/sets",
            "/api/manager/sets/LTR/cards",
            "/api/manager/sets/LTR/art-styles",
            "/api/cards/LTR/1",
            "/api/cards/LTR/1?finish=foil",
            "/api/prices/sync/status",
            "/api/storage/locations",
            "/api/storage/locations/storage:general/cards",
        ]
        for path in endpoints:
            with self.subTest(path=path):
                self._get(path)

    def test_reports_cards_returns_payload(self):
        response = self.client.get("/api/reports/cards?report=all&setCode=LTR")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("cards", payload)
        self.assertGreaterEqual(payload["totalMatches"], 1)

    def test_write_endpoints_validate_input(self):
        response = self.client.patch("/api/settings", json={"priceStrategy": "trend"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["priceStrategy"], "trend")

        response = self.client.patch("/api/settings", json={"pageSize": 50})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pageSize"], 50)

        response = self.client.post(
            "/api/manager/sets/LTR/favorite",
            json={"favorite": True},
        )
        self.assertEqual(response.status_code, 200)

    def test_manager_ownership_accepts_finish_and_foil_aliases(self):
        response = self.client.patch(
            "/api/manager/ownership",
            json={
                "setCode": "LTR",
                "collectorNumber": "1",
                "finish": 0,
                "owned": True,
                "purchaseValue": 1.0,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ownedNonfoil"])

        response = self.client.patch(
            "/api/manager/ownership",
            json={
                "setCode": "LTR",
                "collectorNumber": "1",
                "foil": 1,
                "owned": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ownedNonfoil"])
        self.assertTrue(payload["ownedFoil"])


if __name__ == "__main__":
    unittest.main()
