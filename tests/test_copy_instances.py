import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import card_service, manager_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.card_prices import ensure_card_prices_table  # noqa: E402
from util.db_migrate import ensure_card_columns  # noqa: E402
from util.set_catalog import SETS_TABLE_SQL  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class CopyInstanceTests(unittest.TestCase):
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
            """
        )
        ensure_card_columns(self.conn)
        ensure_card_prices_table(self.conn)
        self.conn.executescript(SETS_TABLE_SQL)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES ('LTR', '1', 'Dual Card', '01. Main set', 1.0, 2.0, NULL, 1, 1, 0, NULL, NULL, NULL)
            """
        )
        ensure_app_tables(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _seed_instances(self):
        manager_service.adjust_copy_count(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            delta=1,
            location_slug="storage:general",
        )
        manager_service.adjust_copy_count(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=1,
            delta=1,
            location_slug="storage:general",
        )
        rows = self.conn.execute(
            """
            SELECT instance_id, finish
            FROM card_instances
            WHERE set_code = 'LTR' AND collector_number = '1'
            ORDER BY finish, instance_id
            """
        ).fetchall()
        self.conn.execute(
            "UPDATE card_instances SET purchase_value = ? WHERE instance_id = ?",
            (1.0, rows[0][0]),
        )
        self.conn.execute(
            "UPDATE card_instances SET purchase_value = ? WHERE instance_id = ?",
            (3.0, rows[1][0]),
        )
        manager_service._sync_finish_purchase_aggregate(self.conn, "LTR", "1", 0)
        manager_service._sync_finish_purchase_aggregate(self.conn, "LTR", "1", 1)
        self.conn.commit()
        return rows

    def test_load_owned_instances_includes_purchase_values(self):
        self._seed_instances()
        payload = manager_service.load_owned_instances_for_print(
            self.conn,
            "LTR",
            "1",
            strategy="trend",
        )

        self.assertEqual(len(payload["ownedInstances"]), 2)
        purchases = {
            instance["finish"]: instance["purchaseValue"]
            for instance in payload["ownedInstances"]
        }
        self.assertEqual(purchases[0], 1.0)
        self.assertEqual(purchases[1], 3.0)
        for instance in payload["ownedInstances"]:
            self.assertEqual(instance["locationType"], "storage")
            self.assertEqual(instance["locationSlug"], "storage:general")

    def test_owned_instances_include_deck_location_metadata(self):
        from util.deck_tables import ensure_deck_tables
        from util.storage_tables import seed_storage_locations

        ensure_deck_tables(self.conn)
        self.conn.execute(
            """
            INSERT INTO decks (deck_id, name, slug, created_at, updated_at)
            VALUES (1, 'Nekusar', 'nekusar', '2024-01-01', '2024-01-01')
            """
        )
        seed_storage_locations(self.conn)
        manager_service.adjust_copy_count(
            self.conn,
            set_code="LTR",
            collector_number="1",
            finish=0,
            delta=1,
            location_slug="storage:general",
        )
        instance_id = self.conn.execute(
            "SELECT instance_id FROM card_instances WHERE set_code = 'LTR'"
        ).fetchone()[0]
        # Move via SQL to simulate deck reconcile (manual assign to deck is blocked).
        self.conn.execute(
            "UPDATE card_instances SET location_slug = 'deck:nekusar' WHERE instance_id = ?",
            (instance_id,),
        )
        self.conn.commit()

        payload = manager_service.load_owned_instances_for_print(
            self.conn,
            "LTR",
            "1",
            strategy="trend",
        )
        instance = payload["ownedInstances"][0]
        self.assertEqual(instance["locationType"], "deck")
        self.assertEqual(instance["locationSlug"], "deck:nekusar")
        self.assertEqual(instance["deckId"], 1)
        self.assertEqual(instance["deckSlug"], "nekusar")

    def test_card_detail_includes_deck_memberships(self):
        from util.deck_tables import ensure_deck_tables

        ensure_deck_tables(self.conn)
        self.conn.execute(
            """
            INSERT INTO decks (deck_id, name, slug, created_at, updated_at)
            VALUES (7, 'Test Deck', 'test-deck', '2024-01-01', '2024-01-01')
            """
        )
        self.conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish, qty, owned_qty, section, sort_order
            ) VALUES (7, 'Dual Card', 'LTR', '1', 0, 2, 1, 'main', 0)
            """
        )
        self.conn.commit()

        detail = card_service.load_card_detail(self.conn, "LTR", "1")
        self.assertEqual(len(detail["deckMemberships"]), 1)
        membership = detail["deckMemberships"][0]
        self.assertEqual(membership["deckId"], 7)
        self.assertEqual(membership["deckName"], "Test Deck")
        self.assertEqual(membership["deckSlug"], "test-deck")
        self.assertEqual(membership["locationSlug"], "deck:test-deck")
        self.assertEqual(membership["qty"], 2)
        self.assertEqual(membership["ownedQty"], 1)

    def test_ownership_summary_averages_positive_purchases_only(self):
        self._seed_instances()
        payload = manager_service.load_owned_instances_for_print(
            self.conn,
            "LTR",
            "1",
            strategy="trend",
        )

        summary = {row["finish"]: row for row in payload["ownershipSummary"]}
        self.assertEqual(summary[0]["count"], 1)
        self.assertEqual(summary[0]["avgPurchase"], 1.0)
        self.assertEqual(summary[1]["count"], 1)
        self.assertEqual(summary[1]["avgPurchase"], 3.0)

    def test_update_copy_instance_purchase_syncs_finish_aggregate(self):
        rows = self._seed_instances()
        nonfoil_id = rows[0][0]

        manager_service.update_copy_instance(
            self.conn,
            instance_id=nonfoil_id,
            purchase_value=2.5,
        )
        purchase = self.conn.execute(
            """
            SELECT purchase_value
            FROM purchases
            WHERE set_code = 'LTR' AND collector_number = '1' AND finish = 0
            """
        ).fetchone()[0]
        self.assertEqual(float(purchase), 2.5)

    def test_update_copy_instance_finish_moves_aggregate(self):
        rows = self._seed_instances()
        nonfoil_id = rows[0][0]

        manager_service.update_copy_instance(
            self.conn,
            instance_id=nonfoil_id,
            finish=1,
        )
        nonfoil_purchase = self.conn.execute(
            """
            SELECT purchase_value
            FROM purchases
            WHERE set_code = 'LTR' AND collector_number = '1' AND finish = 0
            """
        ).fetchone()
        foil_instances = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM card_instances
            WHERE set_code = 'LTR' AND collector_number = '1' AND finish = 1
            """
        ).fetchone()[0]

        self.assertIsNone(nonfoil_purchase)
        self.assertEqual(foil_instances, 2)

    def test_delete_copy_instance_removes_specific_row(self):
        rows = self._seed_instances()
        nonfoil_id = rows[0][0]

        payload = manager_service.delete_copy_instance(self.conn, instance_id=nonfoil_id)

        self.assertEqual(len(payload["ownedInstances"]), 1)
        self.assertEqual(payload["ownedInstances"][0]["finish"], 1)
        remaining = self.conn.execute(
            "SELECT COUNT(*) FROM card_instances WHERE set_code = 'LTR' AND collector_number = '1'"
        ).fetchone()[0]
        self.assertEqual(remaining, 1)

    def test_card_detail_includes_owned_instances_payload(self):
        self._seed_instances()
        payload = card_service.load_card_detail(self.conn, "LTR", "1")

        self.assertEqual(len(payload["ownedInstances"]), 2)
        self.assertEqual(len(payload["ownershipSummary"]), 2)


if __name__ == "__main__":
    unittest.main()
