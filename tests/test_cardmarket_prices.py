import sqlite3
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.card_prices import CARD_PRICES_TABLE_SQL  # noqa: E402
from util.cardmarket_prices import (  # noqa: E402
    PriceSyncContext,
    _nonfoil_low_is_reliable,
    clear_unowned_prices_for_non_qualifying_sets,
    load_price_sync_context,
    parse_id_product,
    price_from_guide_entry,
    should_sync_finish,
    sync_prices_from_guide,
    unowned_price_threshold,
)


def _open_context(db_path: Path) -> PriceSyncContext:
    conn = sqlite3.connect(db_path)
    try:
        return load_price_sync_context(conn, {"LTR"})
    finally:
        conn.close()


class CardmarketPriceTests(unittest.TestCase):
    def test_parse_id_product_from_query(self):
        url = "https://www.cardmarket.com/en/Magic/Products?idProduct=716201"
        self.assertEqual(parse_id_product(url), 716201)

    def test_parse_id_product_from_embedded_string(self):
        url = "https://example.com/path?idProduct=42&foo=bar"
        self.assertEqual(parse_id_product(url), 42)

    def test_price_from_guide_prefers_trend_over_low(self):
        entry = {"trend": 12.5, "low": 500.0, "trend-foil": 588.0}
        self.assertEqual(price_from_guide_entry(entry, finish=0), 12.5)

    def test_nonfoil_low_rejected_when_near_foil_trend(self):
        entry = {"low": 548.0, "trend-foil": 588.79}
        self.assertFalse(_nonfoil_low_is_reliable(entry, 548.0))
        self.assertIsNone(price_from_guide_entry(entry, finish=0))

    def test_nonfoil_low_allowed_without_foil_trend(self):
        entry = {"low": 4.5}
        self.assertTrue(_nonfoil_low_is_reliable(entry, 4.5))
        self.assertEqual(price_from_guide_entry(entry, finish=0), 4.5)

    def test_foil_price_uses_foil_keys(self):
        entry = {"trend": 1.0, "trend-foil": 9.5, "low-foil": 8.0}
        self.assertEqual(price_from_guide_entry(entry, finish=1), 9.5)

    def test_unowned_price_threshold_uses_smaller_of_fixed_or_fraction(self):
        self.assertEqual(unowned_price_threshold(400), 25)
        self.assertEqual(unowned_price_threshold(40), 10)
        self.assertEqual(unowned_price_threshold(8), 2)


class PriceSyncContextTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir._ignore_cleanup_errors = True
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL
            );
            CREATE TABLE purchases (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2))
            );
            """
        )

    def tearDown(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        self.temp_dir.cleanup()

    def test_should_sync_owned_finish_even_in_non_qualifying_set(self):
        context = PriceSyncContext(
            owned_finishes=frozenset({("ABC", "1", 0)}),
            qualifying_sets=frozenset(),
            set_owned_counts={"ABC": 1},
            set_catalog_sizes={"ABC": 300},
        )
        self.assertTrue(should_sync_finish("ABC", "1", False, context))
        self.assertFalse(should_sync_finish("ABC", "1", True, context))
        self.assertFalse(should_sync_finish("ABC", "2", False, context))

    def test_clear_unowned_prices_for_non_qualifying_sets(self):
        self.conn.executemany(
            "INSERT INTO cards VALUES (?, ?, ?, ?, ?)",
            [
                ("ABC", "1", 1.0, 2.0, None),
                ("ABC", "2", 3.0, 4.0, None),
            ],
        )
        self.conn.executemany(
            "INSERT INTO purchases VALUES (?, ?, ?)",
            [("ABC", "1", 0)],
        )
        self.conn.commit()
        context = PriceSyncContext(
            owned_finishes=frozenset({("ABC", "1", 0)}),
            qualifying_sets=frozenset(),
            set_owned_counts={"ABC": 1},
            set_catalog_sizes={"ABC": 300},
        )
        cleared = clear_unowned_prices_for_non_qualifying_sets(
            self.conn, context, {"ABC"},
        )
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT collector_number, market_value, market_value_foil FROM cards ORDER BY collector_number"
        ).fetchall()
        self.assertEqual(cleared, 3)
        self.assertEqual(rows, [("1", 1.0, None), ("2", None, None)])

    def test_load_price_sync_context_marks_small_owned_sets_as_qualifying(self):
        self.conn.executemany(
            "INSERT INTO cards (set_code, collector_number) VALUES (?, ?)",
            [("LTR", str(number)) for number in range(1, 41)],
        )
        self.conn.executemany(
            "INSERT INTO purchases (set_code, collector_number, finish) VALUES (?, ?, ?)",
            [("LTR", str(number), 0) for number in range(1, 11)],
        )
        self.conn.commit()
        context = load_price_sync_context(self.conn, {"LTR"})
        self.assertIn("LTR", context.qualifying_sets)

    def test_load_price_sync_context_includes_deck_owned_finishes(self):
        self.conn.executescript(
            """
            CREATE TABLE decks (
                deck_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL
            );
            CREATE TABLE deck_cards (
                deck_id INTEGER NOT NULL,
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER NOT NULL DEFAULT 0 CHECK (finish IN (0, 1, 2)),
                owned_qty INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.conn.executemany(
            "INSERT INTO cards (set_code, collector_number, market_value, market_value_foil, market_value_etched) VALUES (?, ?, ?, ?, ?)",
            [
                ("FDN", "58", 1.0, None, None),
                ("FDN", "99", 2.0, None, None),
            ],
        )
        self.conn.execute(
            "INSERT INTO decks (deck_id, name, slug) VALUES (1, 'Henzie', 'henzie')"
        )
        self.conn.execute(
            """
            INSERT INTO deck_cards (deck_id, set_code, collector_number, finish, owned_qty)
            VALUES (1, 'FDN', '58', 0, 1)
            """
        )
        self.conn.commit()
        context = load_price_sync_context(self.conn, {"FDN"})
        self.assertIn(("FDN", "58", 0), context.owned_finishes)
        self.assertNotIn(("FDN", "99", 0), context.owned_finishes)
        self.assertEqual(context.set_owned_counts.get("FDN"), 1)

    def test_clear_unowned_prices_keeps_deck_owned_market_values(self):
        self.conn.executescript(
            """
            CREATE TABLE decks (
                deck_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL
            );
            CREATE TABLE deck_cards (
                deck_id INTEGER NOT NULL,
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER NOT NULL DEFAULT 0 CHECK (finish IN (0, 1, 2)),
                owned_qty INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.conn.executemany(
            "INSERT INTO cards (set_code, collector_number, market_value, market_value_foil, market_value_etched) VALUES (?, ?, ?, ?, ?)",
            [("ABC", str(number), float(number), float(number) + 0.5, None) for number in range(1, 101)],
        )
        self.conn.execute(
            "INSERT INTO decks (deck_id, name, slug) VALUES (1, 'Test', 'test')"
        )
        self.conn.execute(
            """
            INSERT INTO deck_cards (deck_id, set_code, collector_number, finish, owned_qty)
            VALUES (1, 'ABC', '1', 0, 1)
            """
        )
        self.conn.commit()
        context = load_price_sync_context(self.conn, {"ABC"})
        self.assertNotIn("ABC", context.qualifying_sets)
        cleared = clear_unowned_prices_for_non_qualifying_sets(
            self.conn, context, {"ABC"},
        )
        self.conn.commit()
        owned_row = self.conn.execute(
            "SELECT market_value, market_value_foil FROM cards WHERE collector_number = '1'"
        ).fetchone()
        unowned_row = self.conn.execute(
            "SELECT market_value, market_value_foil FROM cards WHERE collector_number = '2'"
        ).fetchone()
        self.assertGreater(cleared, 0)
        self.assertEqual(owned_row, (1.0, None))
        self.assertEqual(unowned_row, (None, None))


class SyncPricesFromGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir._ignore_cleanup_errors = True
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                cardmarket_url TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            );
            CREATE TABLE purchases (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2))
            );
            """
        )
        self.conn.executescript(CARD_PRICES_TABLE_SQL)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, market_value, market_value_foil, market_value_etched,
                cardmarket_url, has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "LTR",
                "697",
                548.0,
                588.79,
                None,
                "https://www.cardmarket.com/en/Magic/Products?idProduct=738253",
                1,
                1,
                0,
            ),
        )
        self.conn.execute(
            "INSERT INTO purchases (set_code, collector_number, finish) VALUES (?, ?, ?)",
            ("LTR", "697", 0),
        )
        self.conn.commit()
        self.context = PriceSyncContext(
            owned_finishes=frozenset({("LTR", "697", 0)}),
            qualifying_sets=frozenset({"LTR"}),
            set_owned_counts={"LTR": 1},
            set_catalog_sizes={"LTR": 1},
        )

    def tearDown(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        self.temp_dir.cleanup()

    def test_sync_clears_stale_value_when_guide_has_no_reliable_price(self):
        row = {
            "set_code": "LTR",
            "collector_number": "697",
            "market_value": 548.0,
            "market_value_foil": 588.79,
            "market_value_etched": None,
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=738253",
            "cardmarket_url_foil": None,
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
        }
        guide = {738253: {"low": 548.0, "trend-foil": 588.79}}
        self.conn.close()
        with unittest.mock.patch(
            "util.cardmarket_prices.DB_PATH",
            self.db_path,
        ), unittest.mock.patch(
            "util.cardmarket_prices.load_price_sync_context",
            return_value=self.context,
        ), unittest.mock.patch(
            "util.cardmarket_prices.clear_unowned_prices_for_non_qualifying_sets",
            return_value=0,
        ), unittest.mock.patch(
            "util.cardmarket_prices.list_cards_for_price_sync",
            return_value=[row],
        ), unittest.mock.patch(
            "util.cardmarket_prices.load_price_guide_index",
            return_value=guide,
        ), unittest.mock.patch(
            "util.cardmarket_urls.backfill_cardmarket_urls",
            return_value=0,
        ):
            stats = sync_prices_from_guide(
                "2026-06-16",
                set_codes={"LTR"},
                missing_only=False,
            )

        verify_conn = sqlite3.connect(self.db_path)
        market_value, market_value_foil = verify_conn.execute(
            """
            SELECT market_value, market_value_foil
            FROM cards
            WHERE set_code = 'LTR' AND collector_number = '697'
            """
        ).fetchone()
        verify_conn.close()
        self.assertIsNone(market_value)
        self.assertEqual(market_value_foil, 588.79)
        self.assertEqual(stats["cleared_fields"], 1)


class SyncPricesFromGuideUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir._ignore_cleanup_errors = True
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                cardmarket_url TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            );
            CREATE TABLE purchases (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2))
            );
            """
        )
        self.conn.executescript(CARD_PRICES_TABLE_SQL)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, market_value, market_value_foil, market_value_etched,
                cardmarket_url, has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "LTR",
                "1",
                1.0,
                None,
                None,
                "https://www.cardmarket.com/en/Magic/Products?idProduct=42",
                1,
                1,
                0,
            ),
        )
        self.conn.executemany(
            "INSERT INTO purchases (set_code, collector_number, finish) VALUES (?, ?, ?)",
            [("LTR", "1", 0), ("LTR", "1", 1)],
        )
        self.conn.commit()
        self.context = PriceSyncContext(
            owned_finishes=frozenset({("LTR", "1", 0), ("LTR", "1", 1)}),
            qualifying_sets=frozenset({"LTR"}),
            set_owned_counts={"LTR": 2},
            set_catalog_sizes={"LTR": 1},
        )

    def tearDown(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        self.temp_dir.cleanup()

    def test_sync_prices_from_guide_updates_existing_values(self):
        row = {
            "set_code": "LTR",
            "collector_number": "1",
            "market_value": 1.0,
            "market_value_foil": None,
            "market_value_etched": None,
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=42",
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
        }
        guide = {42: {"trend": 3.5, "trend-foil": 7.0}}
        self.conn.close()
        with unittest.mock.patch(
            "util.cardmarket_prices.DB_PATH",
            self.db_path,
        ), unittest.mock.patch(
            "util.cardmarket_prices.load_price_sync_context",
            return_value=self.context,
        ), unittest.mock.patch(
            "util.cardmarket_prices.clear_unowned_prices_for_non_qualifying_sets",
            return_value=0,
        ), unittest.mock.patch(
            "util.cardmarket_prices.list_cards_for_price_sync",
            return_value=[row],
        ), unittest.mock.patch(
            "util.cardmarket_prices.load_price_guide_index",
            return_value=guide,
        ):
            stats = sync_prices_from_guide(
                "2026-06-16",
                set_codes={"LTR"},
                missing_only=False,
            )

        verify_conn = sqlite3.connect(self.db_path)
        market_value, market_value_foil = verify_conn.execute(
            """
            SELECT market_value, market_value_foil
            FROM cards
            WHERE set_code = 'LTR' AND collector_number = '1'
            """
        ).fetchone()
        history_rows = verify_conn.execute(
            """
            SELECT finish, price
            FROM card_prices
            WHERE set_code = 'LTR' AND collector_number = '1'
            ORDER BY finish
            """
        ).fetchall()
        verify_conn.close()
        self.assertEqual(stats["updated_fields"], 2)
        self.assertEqual(market_value, 3.5)
        self.assertEqual(market_value_foil, 7.0)
        self.assertEqual(history_rows, [(0, 3.5), (1, 7.0)])

    def test_sync_skips_history_for_unchanged_values(self):
        row = {
            "set_code": "LTR",
            "collector_number": "1",
            "market_value": 3.5,
            "market_value_foil": 7.0,
            "market_value_etched": None,
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=42",
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
        }
        guide = {42: {"trend": 3.5, "trend-foil": 7.0}}
        self.conn.close()
        with unittest.mock.patch(
            "util.cardmarket_prices.DB_PATH",
            self.db_path,
        ), unittest.mock.patch(
            "util.cardmarket_prices.load_price_sync_context",
            return_value=self.context,
        ), unittest.mock.patch(
            "util.cardmarket_prices.clear_unowned_prices_for_non_qualifying_sets",
            return_value=0,
        ), unittest.mock.patch(
            "util.cardmarket_prices.list_cards_for_price_sync",
            return_value=[row],
        ), unittest.mock.patch(
            "util.cardmarket_prices.load_price_guide_index",
            return_value=guide,
        ), unittest.mock.patch(
            "util.cardmarket_prices.snapshot_owned_cardmarket_prices",
        ) as snapshot_mock:
            stats = sync_prices_from_guide(
                "2026-06-16",
                set_codes={"LTR"},
                missing_only=False,
            )

        verify_conn = sqlite3.connect(self.db_path)
        history_count = verify_conn.execute("SELECT COUNT(*) FROM card_prices").fetchone()[0]
        verify_conn.close()
        self.assertEqual(stats["unchanged_fields"], 2)
        self.assertEqual(stats["updated_fields"], 0)
        self.assertEqual(history_count, 0)
        snapshot_mock.assert_called_once()


class SyncPairedCardmarketUrlTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir._ignore_cleanup_errors = True
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            );
            CREATE TABLE purchases (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2))
            );
            """
        )
        self.conn.executescript(CARD_PRICES_TABLE_SQL)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, market_value, market_value_foil,
                cardmarket_url, cardmarket_url_foil, has_nonfoil, has_foil, has_etched
            ) VALUES (
                'LTR', '723', NULL, 73.42,
                'https://www.cardmarket.com/en/Magic/Products?idProduct=738285', NULL,
                1, 1, 0
            )
            """
        )
        self.conn.execute(
            "INSERT INTO purchases (set_code, collector_number, finish) VALUES ('LTR', '723', 0)"
        )
        self.conn.commit()
        self.context = PriceSyncContext(
            owned_finishes=frozenset({("LTR", "723", 0)}),
            qualifying_sets=frozenset({"LTR"}),
            set_owned_counts={"LTR": 1},
            set_catalog_sizes={"LTR": 1},
        )

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_sync_uses_paired_nonfoil_product_for_silver_foil_split(self):
        row = {
            "set_code": "LTR",
            "collector_number": "723",
            "market_value": None,
            "market_value_foil": 73.42,
            "market_value_etched": None,
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=738284",
            "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=738285",
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
        }
        guide = {
            738284: {"trend": 44.23, "trend-foil": 0},
            738285: {"trend": 0, "trend-foil": 73.42},
        }
        self.conn.close()
        with unittest.mock.patch("util.cardmarket_prices.DB_PATH", self.db_path), unittest.mock.patch(
            "util.cardmarket_prices.load_price_sync_context", return_value=self.context
        ), unittest.mock.patch(
            "util.cardmarket_prices.clear_unowned_prices_for_non_qualifying_sets", return_value=0
        ), unittest.mock.patch(
            "util.cardmarket_prices.list_cards_for_price_sync", return_value=[row]
        ), unittest.mock.patch(
            "util.cardmarket_prices.load_price_guide_index", return_value=guide
        ), unittest.mock.patch(
            "util.cardmarket_urls.backfill_cardmarket_urls", return_value=0
        ), unittest.mock.patch(
            "util.cardmarket_prices.snapshot_owned_cardmarket_prices",
        ):
            sync_prices_from_guide("2026-06-16", set_codes={"LTR"})

        verify_conn = sqlite3.connect(self.db_path)
        market_value = verify_conn.execute(
            "SELECT market_value FROM cards WHERE collector_number = '723'"
        ).fetchone()[0]
        verify_conn.close()
        self.assertEqual(market_value, 44.23)


if __name__ == "__main__":
    unittest.main()
