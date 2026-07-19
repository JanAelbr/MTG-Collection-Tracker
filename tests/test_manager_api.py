import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import manager_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.card_prices import ensure_card_prices_table  # noqa: E402
from util.db_migrate import ensure_card_columns  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402
from util.set_catalog import ensure_sets_table  # noqa: E402
from util.tracked_sets import add_tracked_set, ensure_tracked_sets_table  # noqa: E402


class ManagerApiServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_storage_tables(self.conn)
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
                card_type TEXT,
                cardmarket_url TEXT
            );
            CREATE TABLE purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
                UNIQUE (set_code, collector_number, finish)
            );
            CREATE TABLE decks (
                deck_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                purchase_price REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE deck_cards (
                deck_card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                card_name TEXT NOT NULL,
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER NOT NULL DEFAULT 0 CHECK (finish IN (0, 1, 2)),
                qty INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
                owned_qty INTEGER NOT NULL DEFAULT 0,
                section TEXT NOT NULL DEFAULT 'main',
                sort_order INTEGER NOT NULL DEFAULT 0,
                in_catalog INTEGER NOT NULL DEFAULT 0,
                UNIQUE (deck_id, set_code, collector_number, finish, section),
                FOREIGN KEY (deck_id) REFERENCES decks(deck_id) ON DELETE CASCADE
            );
            """
        )
        ensure_card_columns(self.conn)
        ensure_card_prices_table(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES ('LTR', '1', 'Test Card', '01. Main set', 1.0, 2.0, NULL, 1, 1, 0, NULL, NULL, NULL)
            """
        )
        ensure_app_tables(self.conn)
        self.conn.commit()

    @patch("report.report_data.get_all_set_codes", return_value=["MB2", "LTR"])
    def test_favorite_sets_appear_first_in_manager_list(self, _mock_codes):
        manager_service.toggle_favorite_set(self.conn, "LTR")
        sets = manager_service.list_sets(self.conn)

        self.assertEqual([item["setCode"] for item in sets], ["LTR", "MB2"])
        self.assertTrue(sets[0]["favorite"])
        self.assertFalse(sets[1]["favorite"])

        toggled = manager_service.toggle_favorite_set(self.conn, "LTR")
        self.assertFalse(toggled["favorite"])
        self.assertEqual(toggled["favoriteSets"], [])

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_list_set_cards_with_art_filter(self):
        payload = manager_service.list_set_cards(self.conn, "LTR")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["cards"][0]["collectorNumber"], "1")

        filtered = manager_service.list_set_cards(
            self.conn,
            "LTR",
            art_style="Missing",
        )
        self.assertEqual(filtered["total"], 0)

    def test_list_set_cards_includes_location_aggregates(self):
        self.conn.execute(
            """
            INSERT INTO storage_locations (
                location_slug, label, location_type, sort_order, description
            ) VALUES ('storage:deckbox', 'Deck box', 'storage', 2, '')
            """
        )
        self.conn.commit()
        manager_service.set_copy_allocations(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            allocations=[
                {"locationSlug": "storage:general", "count": 2},
                {"locationSlug": "storage:deckbox", "count": 1},
            ],
        )

        payload = manager_service.list_set_cards(self.conn, "LTR")
        card = payload["cards"][0]
        self.assertEqual(
            sorted((item["slug"], item["count"]) for item in card["locationsNonfoil"]),
            [("storage:deckbox", 1), ("storage:general", 2)],
        )
        self.assertEqual(card["locationsFoil"], [])
        self.assertEqual(card["locationsEtched"], [])

    def test_list_set_cards_includes_image_uri_back(self):
        self.conn.execute(
            """
            UPDATE cards
            SET image_uri_back = 'https://example.com/back.jpg'
            WHERE set_code = 'LTR' AND collector_number = '1'
            """
        )
        self.conn.commit()

        payload = manager_service.list_set_cards(self.conn, "LTR")
        card = payload["cards"][0]
        self.assertEqual(card["imageUriBack"], "https://example.com/back.jpg")

    def test_list_set_cards_with_foil_filter(self):
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES ('LTR', '2', 'Foil Only', '02. Showcase', 1.0, 2.0, NULL, 0, 1, 0, NULL, NULL, NULL)
            """
        )
        self.conn.commit()

        nonfoil = manager_service.list_set_cards(self.conn, "LTR", finish_filter="nonfoil")
        foil = manager_service.list_set_cards(self.conn, "LTR", finish_filter="foil")

        self.assertEqual(nonfoil["total"], 1)
        self.assertEqual(nonfoil["cards"][0]["collectorNumber"], "1")
        self.assertEqual(foil["total"], 2)
        self.assertEqual(
            {card["collectorNumber"] for card in foil["cards"]},
            {"1", "2"},
        )

    def test_set_and_clear_ownership(self):
        updated = manager_service.set_ownership(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            owned=True,
            purchase_value=1.5,
        )
        self.assertTrue(updated["ownedNonfoil"])

        cleared = manager_service.set_ownership(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            owned=False,
        )
        self.assertFalse(cleared["ownedNonfoil"])

        row = self.conn.execute(
            """
            SELECT COUNT(*) FROM card_instances
            WHERE set_code = 'LTR' AND collector_number = '1' AND finish = 0
            """
        ).fetchone()
        self.assertEqual(row[0], 0)

    def test_add_foil_variant_when_nonfoil_owned(self):
        manager_service.set_ownership(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            owned=True,
            purchase_value=1.0,
        )
        updated = manager_service.set_ownership(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=1,
            owned=True,
            purchase_value=2.0,
        )
        self.assertTrue(updated["ownedNonfoil"])
        self.assertTrue(updated["ownedFoil"])

        rows = self.conn.execute(
            """
            SELECT finish FROM purchases
            WHERE set_code = 'LTR' AND collector_number = '1'
            ORDER BY finish
            """
        ).fetchall()
        self.assertEqual([row[0] for row in rows], [0, 1])

    def test_update_purchase_price_preserves_copy_count(self):
        for _ in range(3):
            manager_service.adjust_copy_count(
                self.conn,
                set_code="LTR",
                collector_number="1",
                finish=0,
                delta=1,
                location_slug="storage:general",
            )
        updated = manager_service.set_ownership(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            owned=True,
            purchase_value=4.5,
        )
        self.assertTrue(updated["ownedNonfoil"])
        self.assertAlmostEqual(updated["purchaseValueNonfoil"], 4.5)
        count = self.conn.execute(
            """
            SELECT COUNT(*) FROM card_instances
            WHERE set_code = 'LTR' AND collector_number = '1' AND finish = 0
            """
        ).fetchone()[0]
        self.assertEqual(count, 3)

    def test_change_ownership_finish_moves_purchase_and_instances(self):
        manager_service.set_ownership(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            owned=True,
            purchase_value=1.5,
        )
        result = manager_service.change_ownership_finish(
            self.conn,
            set_code="LTR",
            collector_number="1",
            from_finish=0,
            to_finish=1,
        )
        self.assertEqual(result["fromFinish"], 0)
        self.assertEqual(result["toFinish"], 1)
        self.assertEqual(result["ownedCount"], 1)

        ownership = manager_service.get_card_ownership(self.conn, "LTR", "1")
        self.assertFalse(ownership["ownedNonfoil"])
        self.assertTrue(ownership["ownedFoil"])
        self.assertAlmostEqual(ownership["purchaseValueFoil"], 1.5)

        instance = self.conn.execute(
            """
            SELECT finish FROM card_instances
            WHERE set_code = 'LTR' AND collector_number = '1'
            """
        ).fetchone()
        self.assertEqual(instance[0], 1)

    @patch("api.services.manager_service.import_set_catalog_from_scryfall", return_value=42)
    def test_reload_set_catalog(self, mock_import):
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES ('LTR', '99', 'Old Card', '01. Main set', 1.0, 2.0, NULL, 1, 1, 0, NULL, NULL, NULL)
            """
        )
        self.conn.commit()

        result = manager_service.reload_set_catalog(self.conn, "LTR")

        self.assertEqual(result["setCode"], "LTR")
        self.assertEqual(result["catalogCount"], 42)
        mock_import.assert_called_once_with(self.conn, "LTR")

    def test_reload_set_catalog_rejects_unknown_set(self):
        with self.assertRaises(manager_service.ManagerError):
            manager_service.reload_set_catalog(self.conn, "ZZZZ")

    def test_bulk_assign_storage(self):
        manager_service.set_ownership(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            owned=True,
            purchase_value=1.0,
        )
        result = manager_service.bulk_assign_storage(
            self.conn,
            location_slug="storage:general",
            items=[
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "finish": 0,
                }
            ],
        )
        self.assertEqual(result["moved"], 1)

        row = self.conn.execute(
            """
            SELECT location_slug FROM card_instances
            WHERE set_code = 'LTR' AND collector_number = '1' AND finish = 0
            """
        ).fetchone()
        self.assertEqual(row[0], "storage:general")

    def test_set_copy_allocations_splits_across_storages(self):
        self.conn.execute(
            """
            INSERT INTO storage_locations (
                location_slug, label, location_type, sort_order, description
            ) VALUES ('storage:deckbox', 'Deck box', 'storage', 2, '')
            """
        )
        self.conn.commit()

        state = manager_service.set_copy_allocations(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            allocations=[
                {"locationSlug": "storage:general", "count": 2},
                {"locationSlug": "storage:deckbox", "count": 3},
            ],
        )
        self.assertEqual(state["ownedCount"], 5)
        self.assertEqual(
            sorted((item["slug"], item["count"]) for item in state["locations"]),
            [("storage:deckbox", 3), ("storage:general", 2)],
        )

        cleared = manager_service.set_copy_allocations(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            allocations=[],
        )
        self.assertEqual(cleared["ownedCount"], 0)
        self.assertEqual(cleared["locations"], [])

    def test_copy_limits_and_per_copy_storage(self):
        state = manager_service.adjust_copy_count(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            delta=1,
            location_slug="storage:general",
        )
        self.assertEqual(state["ownedCount"], 1)
        self.assertEqual(len(state["copies"]), 1)

        second = manager_service.adjust_copy_count(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            delta=1,
            location_slug="storage:general",
        )
        self.assertEqual(second["ownedCount"], 2)
        self.assertEqual(len(second["copies"]), 2)

        third = manager_service.adjust_copy_count(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            delta=1,
            location_slug="storage:general",
        )
        state = manager_service.get_copy_state(self.conn, "LTR", "1", 0)
        self.assertEqual(third["ownedCount"], 3)
        self.assertEqual(state["ownedCount"], 3)
        self.assertEqual(state["maxCopies"], 99)
        self.assertEqual(len(state["copies"]), 3)

        fourth = manager_service.adjust_copy_count(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            delta=1,
            location_slug="storage:general",
        )
        self.assertEqual(fourth["ownedCount"], 4)

        deck_row = self.conn.execute(
            "SELECT location_slug FROM storage_locations WHERE location_slug != 'storage:general' LIMIT 1"
        ).fetchone()
        if deck_row is None:
            self.conn.execute(
                """
                INSERT INTO storage_locations (
                    location_slug, label, location_type, sort_order, description
                ) VALUES ('storage:deckbox', 'Deck box', 'deck', 2, '')
                """
            )
            self.conn.commit()
            deck_slug = "storage:deckbox"
        else:
            deck_slug = deck_row[0]

        instance_id = state["copies"][0]["instanceId"]
        updated = manager_service.update_copy_storage(
            self.conn,
            instance_id=instance_id,
            location_slug=deck_slug,
        )
        self.assertEqual(updated["copies"][0]["locationSlug"], deck_slug)
        self.assertEqual(updated["copies"][1]["locationSlug"], "storage:general")

    @patch("api.services.manager_service.list_deck_sync_set_codes", return_value=[])
    def test_remove_set_without_owned_cards(self, _mock_decks):
        ensure_tracked_sets_table(self.conn)
        add_tracked_set(self.conn, "MB2")
        self.conn.commit()

        result = manager_service.remove_set(self.conn, "MB2")

        self.assertTrue(result["removed"])
        self.assertEqual(result["setCode"], "MB2")
        self.assertFalse(
            self.conn.execute(
                "SELECT 1 FROM tracked_sets WHERE set_code = 'MB2'"
            ).fetchone()
        )

    @patch("api.services.manager_service.list_deck_sync_set_codes", return_value=[])
    def test_remove_set_with_owned_cards_fails(self, _mock_decks):
        ensure_tracked_sets_table(self.conn)
        add_tracked_set(self.conn, "LTR")
        self.conn.commit()
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES ('LTR', '1', 1.0, 0)
            """
        )
        self.conn.commit()

        with self.assertRaises(manager_service.ManagerError):
            manager_service.remove_set(self.conn, "LTR")

    @patch("api.services.manager_service.list_deck_sync_set_codes", return_value=[])
    def test_prune_orphan_catalogs(self, _mock_decks):
        ensure_tracked_sets_table(self.conn)
        add_tracked_set(self.conn, "LTR")
        self.conn.commit()
        ensure_sets_table(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES ('ORPH', '1', 'Orphan Card', '', 1.0, NULL, NULL, 1, 0, 0, NULL, NULL, NULL)
            """
        )
        self.conn.execute(
            "INSERT INTO sets (set_code, name, updated_at) VALUES ('ORPH', 'Orphan', '2026-01-01')"
        )
        self.conn.commit()

        result = manager_service.prune_orphan_catalogs(self.conn)

        self.assertEqual(result["removedSets"], ["ORPH"])
        self.assertEqual(result["deletedCards"], 1)
        row = self.conn.execute(
            "SELECT COUNT(*) FROM cards WHERE set_code = 'ORPH'"
        ).fetchone()
        self.assertEqual(row[0], 0)

    def test_save_art_style_rules_for_set_updates_cards(self):
        self.conn.execute("DELETE FROM cards WHERE set_code = 'LTR'")
        self.conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES (?, ?, ?, ?, 1.0, NULL, NULL, 1, 0, 0, NULL, NULL, NULL)
            """,
            [
                ("LTR", "1", "Card One", ""),
                ("LTR", "100", "Card Two", ""),
            ],
        )
        self.conn.commit()

        result = manager_service.save_art_style_rules_for_set(
            self.conn,
            "LTR",
            [{"name": "Main", "firstNumber": 1, "lastNumber": 99}],
        )

        self.assertEqual(result["updatedCards"], 2)
        self.assertEqual(result["artStyles"][0]["artStyle"], "Main")
        row = self.conn.execute(
            "SELECT art_style FROM cards WHERE set_code = 'LTR' AND collector_number = '1'"
        ).fetchone()
        self.assertEqual(row[0], "Main")

    @patch("api.services.manager_service.fetch_all_scryfall_sets")
    def test_list_available_sets_excludes_tracked_and_sorts_newest_first(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "code": "ltr",
                "name": "Tales of Middle-earth",
                "released_at": "2023-06-23",
                "icon_svg_uri": "https://svgs.scryfall.io/sets/ltr.svg",
            },
            {
                "code": "mh3",
                "name": "Modern Horizons 3",
                "released_at": "2024-06-14",
                "icon_svg_uri": "https://svgs.scryfall.io/sets/mh3.svg",
            },
            {
                "code": "dsk",
                "name": "Duskmourn",
                "released_at": "2024-09-27",
                "icon_svg_uri": "https://svgs.scryfall.io/sets/dsk.svg",
            },
        ]
        ensure_tracked_sets_table(self.conn)
        add_tracked_set(self.conn, "LTR")
        self.conn.commit()

        available = manager_service.list_available_sets(self.conn)

        self.assertEqual([item["setCode"] for item in available], ["DSK", "MH3"])
        self.assertEqual(available[0]["name"], "Duskmourn")
        self.assertTrue(available[0]["iconUri"].endswith("/dsk.svg"))


if __name__ == "__main__":
    unittest.main()
