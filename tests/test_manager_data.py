import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import manager_service  # noqa: E402
from report import manager_data  # noqa: E402
from util.db_migrate import backfill_card_types, ensure_card_columns  # noqa: E402
from util.schema import ensure_database_schema  # noqa: E402


class ManagerDataPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT,
                image_uri TEXT,
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
            """
        )
        rows = []
        for number in range(1, 251):
            rows.append(
                (
                    "LTR",
                    str(number),
                    f"Card {number}",
                    "01. Main set",
                    None,
                    1.0,
                    2.0,
                    None,
                    1,
                    1,
                    0,
                    None,
                    "Creature",
                    "creature",
                )
            )
        self.conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style, image_uri,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_query_manager_cards_paginates_in_sql(self):
        page = manager_data.query_manager_cards_for_set(
            self.conn,
            "LTR",
            offset=0,
            limit=25,
        )
        self.assertEqual(len(page), 25)
        self.assertEqual(page[0]["collector_number"], "1")

        total = manager_data.count_manager_cards_for_set(self.conn, "LTR")
        self.assertEqual(total, 250)

    def test_list_set_cards_uses_sql_filters(self):
        payload = manager_service.list_set_cards(
            self.conn,
            "LTR",
            search="Card 2",
            page=1,
            page_size=10,
        )
        self.assertGreater(payload["total"], 0)
        self.assertLessEqual(len(payload["cards"]), 10)
        self.assertTrue(all("2" in card["collectorNumber"] for card in payload["cards"]))

    def test_manager_card_exposes_catalog_finish_without_pricing(self):
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style, image_uri,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "LTC",
                "81",
                "Commander Face",
                "02. Borderless Face Commander",
                None,
                None,
                None,
                None,
                0,
                0,
                1,
                None,
                "Legendary Creature",
                "creature",
            ),
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES ('LTC', '81', 0.0, 2)
            """
        )
        self.conn.commit()

        card = manager_data.query_manager_cards_for_set(self.conn, "LTC", search="81")[0]

        self.assertTrue(card["has_etched"])
        self.assertFalse(card["has_foil"])
        self.assertTrue(card["owned_etched"])

    def test_ensure_card_columns_does_not_backfill(self):
        with patch("util.db_migrate.backfill_card_types") as mock_backfill:
            ensure_card_columns(self.conn)
        mock_backfill.assert_not_called()

    def test_schema_bootstrap_runs_backfill_once(self):
        ensure_database_schema(self.conn)
        updated = self.conn.execute(
            "SELECT COUNT(1) FROM cards WHERE card_type = 'creature'"
        ).fetchone()[0]
        self.assertEqual(updated, 250)


if __name__ == "__main__":
    unittest.main()
