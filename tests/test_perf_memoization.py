"""Regression tests for the Phase 1 memoization helpers added by the
performance roadmap: per-process deck-table readiness, cache-epoch-scoped
set-count/snapshot caches, the `idx_cards_name` index, and the unified
Cardmarket guide cache. These guard against the caches silently going stale
(serving old data forever) or never actually caching (defeating the point).
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

runpy.run_path(str(TESTS_DIR / "_paths.py"))

from api.cache import bump_cache_epoch  # noqa: E402
import util.deck_tables as deck_tables  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.schema import ensure_database_schema  # noqa: E402
from report.report_data import (  # noqa: E402
    load_catalog_count_by_set,
    load_owned_count_by_set,
)
from util.price_history import load_price_snapshot_cache  # noqa: E402
import util.cardmarket_prices as cardmarket_prices  # noqa: E402
from api.services import pricing_service  # noqa: E402


class EnsureDeckTablesMemoizationTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        deck_tables._ready_db_paths.clear()

    def test_second_call_on_same_db_path_skips_ddl(self):
        db_path = Path(self._temp_dir.name) / "deck_cache_a.db"
        conn1 = sqlite3.connect(db_path)
        self.addCleanup(conn1.close)
        ensure_deck_tables(conn1)
        self.assertIn(str(db_path), deck_tables._ready_db_paths)

        conn2 = sqlite3.connect(db_path)
        self.addCleanup(conn2.close)
        with patch("util.deck_tables.ensure_deck_columns") as mock_columns, patch(
            "util.deck_tables.ensure_deck_finish_column"
        ) as mock_finish, patch(
            "util.deck_tables.ensure_deck_card_columns"
        ) as mock_card_columns, patch(
            "util.deck_tables.ensure_deck_cards_print_unique"
        ) as mock_unique:
            ensure_deck_tables(conn2)
            mock_columns.assert_not_called()
            mock_finish.assert_not_called()
            mock_card_columns.assert_not_called()
            mock_unique.assert_not_called()

        # And the table is genuinely usable (first call did its job for real).
        conn2.execute("SELECT * FROM decks").fetchall()

    def test_different_db_paths_are_cached_independently(self):
        db_path_a = Path(self._temp_dir.name) / "deck_cache_b.db"
        db_path_b = Path(self._temp_dir.name) / "deck_cache_c.db"
        conn_a = sqlite3.connect(db_path_a)
        conn_b = sqlite3.connect(db_path_b)
        self.addCleanup(conn_a.close)
        self.addCleanup(conn_b.close)

        ensure_deck_tables(conn_a)
        self.assertIn(str(db_path_a), deck_tables._ready_db_paths)
        self.assertNotIn(str(db_path_b), deck_tables._ready_db_paths)

        with patch("util.deck_tables.ensure_deck_columns") as mock_columns:
            ensure_deck_tables(conn_b)
            mock_columns.assert_called_once()
        self.assertIn(str(db_path_b), deck_tables._ready_db_paths)

    def test_in_memory_databases_are_never_cached(self):
        conn1 = sqlite3.connect(":memory:")
        conn2 = sqlite3.connect(":memory:")
        self.addCleanup(conn1.close)
        self.addCleanup(conn2.close)

        ensure_deck_tables(conn1)
        self.assertNotIn(":memory:", deck_tables._ready_db_paths)

        with patch("util.deck_tables.ensure_deck_columns") as mock_columns:
            ensure_deck_tables(conn2)
            mock_columns.assert_called_once()


class SetCountAndSnapshotCacheMemoizationTests(unittest.TestCase):
    """Uses on-disk (not :memory:) databases: the epoch-cache keys on the file
    path, so `:memory:` connections intentionally bypass caching entirely
    (see `_database_identity`) and can't exercise this behavior."""

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        db_path = Path(self._temp_dir.name) / "memoization.db"
        self.conn = sqlite3.connect(db_path)
        self.addCleanup(self.conn.close)
        ensure_database_schema(self.conn)
        bump_cache_epoch()

    def test_owned_count_by_set_is_cached_until_epoch_bump(self):
        self.conn.execute(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) "
            "VALUES ('LTR', '1', 1.0, 0)"
        )
        self.conn.commit()

        first = load_owned_count_by_set(self.conn)
        self.assertEqual(first.get("LTR"), 1)

        # Mutate without bumping the epoch: a real cache should still return
        # the stale (pre-mutation) result.
        self.conn.execute(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) "
            "VALUES ('LTR', '2', 1.0, 0)"
        )
        self.conn.commit()
        cached = load_owned_count_by_set(self.conn)
        self.assertEqual(cached.get("LTR"), 1, "expected the cached (stale) count")

        bump_cache_epoch()
        fresh = load_owned_count_by_set(self.conn)
        self.assertEqual(fresh.get("LTR"), 2, "expected a recomputed count after epoch bump")

    def test_catalog_count_by_set_is_cached_until_epoch_bump(self):
        self.conn.execute(
            "INSERT INTO cards (set_code, collector_number, name, art_style) "
            "VALUES ('LTR', '1', 'Card A', '')"
        )
        self.conn.commit()

        first = load_catalog_count_by_set(self.conn)
        self.assertEqual(first.get("LTR"), 1)

        self.conn.execute(
            "INSERT INTO cards (set_code, collector_number, name, art_style) "
            "VALUES ('LTR', '2', 'Card B', '')"
        )
        self.conn.commit()
        cached = load_catalog_count_by_set(self.conn)
        self.assertEqual(cached.get("LTR"), 1, "expected the cached (stale) count")

        bump_cache_epoch()
        fresh = load_catalog_count_by_set(self.conn)
        self.assertEqual(fresh.get("LTR"), 2, "expected a recomputed count after epoch bump")

    def test_price_snapshot_cache_is_cached_until_epoch_bump(self):
        self.conn.execute(
            "INSERT INTO card_prices (set_code, collector_number, finish, price_date, "
            "price, source) VALUES ('LTR', '1', 0, '2026-01-01', 3.0, 'cardmarket')"
        )
        self.conn.commit()

        first = load_price_snapshot_cache(self.conn)
        self.assertIn("2026-01-01", first.snapshots)
        self.assertEqual(len(first.dates), 1)

        self.conn.execute(
            "INSERT INTO card_prices (set_code, collector_number, finish, price_date, "
            "price, source) VALUES ('LTR', '1', 0, '2026-01-02', 4.0, 'cardmarket')"
        )
        self.conn.commit()
        cached = load_price_snapshot_cache(self.conn)
        self.assertEqual(len(cached.dates), 1, "expected the cached (stale) snapshot set")

        bump_cache_epoch()
        fresh = load_price_snapshot_cache(self.conn)
        self.assertEqual(len(fresh.dates), 2, "expected a recomputed snapshot set after epoch bump")

    def test_memory_databases_bypass_the_cache_and_stay_fresh(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        ensure_database_schema(conn)

        conn.execute(
            "INSERT INTO cards (set_code, collector_number, name, art_style) "
            "VALUES ('LTR', '1', 'Card A', '')"
        )
        conn.commit()
        self.assertEqual(load_catalog_count_by_set(conn).get("LTR"), 1)

        conn.execute(
            "INSERT INTO cards (set_code, collector_number, name, art_style) "
            "VALUES ('LTR', '2', 'Card B', '')"
        )
        conn.commit()
        # No epoch bump needed: :memory: connections are never cached.
        self.assertEqual(load_catalog_count_by_set(conn).get("LTR"), 2)


class CardIndexMigrationTests(unittest.TestCase):
    def test_idx_cards_name_exists_after_schema_ensure(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        ensure_database_schema(conn)

        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_cards_name'"
        ).fetchone()
        self.assertIsNotNone(row, "expected idx_cards_name to be created on cards(name)")


class GuideCacheUnificationTests(unittest.TestCase):
    """pricing_service used to keep its own `_guide_index` cache alongside
    cardmarket_prices' `_GUIDE_INDEX_MEMORY`; regressing back to two caches
    would silently reintroduce double-loading and stale-after-refresh bugs.
    """

    def setUp(self):
        cardmarket_prices.invalidate_price_guide_memory_cache()
        self.addCleanup(cardmarket_prices.invalidate_price_guide_memory_cache)

    def test_load_guide_delegates_to_cardmarket_prices_memory_cache(self):
        guide = {123: {"trend": 1.5}}
        with patch(
            "api.services.pricing_service.load_price_guide_index", return_value=guide
        ) as mock_load:
            first = pricing_service._load_guide()
            second = pricing_service._load_guide()

        self.assertIs(first, guide)
        self.assertIs(second, guide)
        # No pricing_service-local cache: every call goes through the shared
        # loader (which does its own in-process memoization internally).
        self.assertEqual(mock_load.call_count, 2)

    def test_refresh_guide_cache_invalidates_the_shared_memory_cache(self):
        cardmarket_prices._GUIDE_INDEX_MEMORY = {1: {"trend": 9.0}}

        pricing_service.refresh_guide_cache()

        self.assertIsNone(cardmarket_prices._GUIDE_INDEX_MEMORY)


if __name__ == "__main__":
    unittest.main()
