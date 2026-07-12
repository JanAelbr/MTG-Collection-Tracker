import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL  # noqa: E402
from util.cardmarket_urls import (  # noqa: E402
    _infer_product_from_neighbors,
    _nonfoil_product_points,
    backfill_cardmarket_urls,
    cardmarket_url_for_finish,
    coerce_cardmarket_url,
    find_paired_product_id,
    merge_cardmarket_urls,
    normalize_cardmarket_url_columns,
    scryfall_url_targets,
)


class CardmarketUrlTests(unittest.TestCase):
    def test_scryfall_url_targets_use_foil_print_flag(self):
        targets = scryfall_url_targets({
            "foil": True,
            "finishes": ["nonfoil", "foil"],
            "purchase_uris": {"cardmarket": "https://example.com/?idProduct=738285"},
        })
        self.assertEqual(targets, {FINISH_FOIL: "https://example.com/?idProduct=738285"})

    def test_merge_cardmarket_urls_keeps_both_finishes(self):
        nonfoil, foil = merge_cardmarket_urls(
            "https://example.com/?idProduct=738286",
            None,
            {
                "foil": True,
                "finishes": ["foil"],
                "purchase_uris": {"cardmarket": "https://example.com/?idProduct=738287"},
            },
        )
        self.assertEqual(nonfoil, "https://example.com/?idProduct=738286")
        self.assertEqual(foil, "https://example.com/?idProduct=738287")

    def test_find_paired_product_id_for_ltc_split_block(self):
        guide = {
            735309: {"trend": 12.16, "trend-foil": 0},
            735310: {"trend": 6.95, "trend-foil": 0},
            735329: {"trend": 0, "trend-foil": 11.27},
        }
        self.assertEqual(find_paired_product_id(735309, guide, FINISH_FOIL), 735329)
        self.assertEqual(find_paired_product_id(735329, guide, FINISH_NONFOIL), 735309)

    def test_normalize_backfills_ltc_split_block_foil_url(self):
        guide = {
            735309: {"trend": 12.16, "trend-foil": 0},
            735329: {"trend": 0, "trend-foil": 11.27},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=735309",
            None,
            guide,
        )
        self.assertIn("735309", nonfoil or "")
        self.assertIn("735329", foil or "")

    def test_cardmarket_url_for_finish_uses_ltc_split_block_foil(self):
        guide = {
            735309: {"trend": 12.16, "trend-foil": 0},
            735329: {"trend": 0, "trend-foil": 11.27},
        }
        row = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=735309",
            "cardmarket_url_foil": None,
        }
        url = cardmarket_url_for_finish(row, FINISH_FOIL, guide)
        self.assertIn("735329", url or "")

    def test_find_paired_product_id_for_ltr_nazgul(self):
        guide = {
            738284: {"trend": 44.23, "trend-foil": 0},
            738285: {"trend": 0, "trend-foil": 73.42},
        }
        self.assertEqual(find_paired_product_id(738285, guide, FINISH_NONFOIL), 738284)
        self.assertEqual(find_paired_product_id(738284, guide, FINISH_FOIL), 738285)

    def test_find_paired_product_id_for_sparse_scroll_showcase_gap(self):
        guide = {
            737810: {"trend": 0.14, "trend-foil": 0},
            737813: {"trend": 0, "trend-foil": 0.33},
            737814: {"trend": 1.02, "trend-foil": 0},
            737816: {"trend": 0, "trend-foil": 1.72},
        }
        self.assertEqual(find_paired_product_id(737816, guide, FINISH_NONFOIL), 737814)
        self.assertEqual(find_paired_product_id(737814, guide, FINISH_FOIL), 737816)

    def test_normalize_backfills_nonfoil_url_from_sparse_foil_only(self):
        guide = {
            737814: {"trend": 1.02, "trend-foil": 0},
            737816: {"trend": 0, "trend-foil": 1.72},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            None,
            "https://www.cardmarket.com/en/Magic/Products?idProduct=737816",
            guide,
        )
        self.assertIn("737814", nonfoil or "")
        self.assertIn("737816", foil or "")

    def test_find_paired_product_id_skips_previous_printing(self):
        guide = {
            737837: {"trend": 49.03, "trend-foil": 0},
            737838: {"trend": 0, "trend-foil": 87.46},
            737839: {"trend": 0.2, "trend-foil": 0},
            737840: {"trend": 0, "trend-foil": 0.32},
        }
        self.assertEqual(find_paired_product_id(737839, guide, FINISH_FOIL), 737840)
        self.assertEqual(find_paired_product_id(737840, guide, FINISH_NONFOIL), 737839)

    def test_normalize_backfills_missing_foil_url_from_nonfoil(self):
        guide = {
            737839: {"trend": 0.2, "trend-foil": 0},
            737840: {"trend": 0, "trend-foil": 0.32},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=737839",
            None,
            guide,
        )
        self.assertIn("737839", nonfoil or "")
        self.assertIn("737840", foil or "")

    def test_normalize_moves_foil_only_url_to_foil_column(self):
        guide = {
            738285: {"trend": 0, "trend-foil": 73.42},
            738284: {"trend": 44.23, "trend-foil": 0},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=738285",
            None,
            guide,
        )
        self.assertIn("738284", nonfoil or "")
        self.assertIn("738285", foil or "")

    def test_cardmarket_url_for_finish_uses_paired_nonfoil_product(self):
        guide = {
            738285: {"trend": 0, "trend-foil": 73.42},
            738284: {"trend": 44.23, "trend-foil": 0},
        }
        row = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=738285",
            "cardmarket_url_foil": None,
        }
        url = cardmarket_url_for_finish(row, FINISH_NONFOIL, guide)
        self.assertIn("738284", url or "")

    def test_cardmarket_url_for_finish_returns_foil_url_for_etched_only(self):
        row = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=718037",
            "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=718057",
            "has_nonfoil": 0,
            "has_foil": 0,
            "has_etched": 1,
        }
        url = cardmarket_url_for_finish(row, FINISH_ETCHED, {})
        self.assertIn("718057", url or "")

    def test_cardmarket_url_for_finish_returns_none_for_etched_without_url(self):
        row = {
            "cardmarket_url": None,
            "cardmarket_url_foil": None,
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 1,
        }
        self.assertIsNone(cardmarket_url_for_finish(row, FINISH_ETCHED, {}))

    def test_cardmarket_url_for_finish_treats_nan_foil_url_as_missing(self):
        row = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=738284",
            "cardmarket_url_foil": float("nan"),
        }
        url = cardmarket_url_for_finish(row, FINISH_NONFOIL, {})
        self.assertIn("738284", url or "")

    def test_merge_cardmarket_urls_moves_single_url_to_nonfoil_for_nonfoil_only(self):
        nonfoil, foil = merge_cardmarket_urls(
            None,
            "https://example.com/?idProduct=705035",
            {"finishes": ["nonfoil"]},
        )
        self.assertEqual(nonfoil, "https://example.com/?idProduct=705035")
        self.assertIsNone(foil)

    def test_coerce_cardmarket_url_rejects_nan(self):
        self.assertIsNone(coerce_cardmarket_url(float("nan")))

    def test_infer_product_skips_outlier_neighbor(self):
        guide = {
            834120: {"trend": 1.0},
            834121: {"trend": 0.15},
            834122: {"trend": 1.03},
            834268: {"trend": 0.57},
        }
        points = _nonfoil_product_points(
            [
                ("117", "https://www.cardmarket.com/en/Magic/Products?idProduct=834120", None, 1, 0, 0),
                ("118", "https://www.cardmarket.com/en/Magic/Products?idProduct=834268", None, 1, 0, 0),
                ("120", "https://www.cardmarket.com/en/Magic/Products?idProduct=834122", None, 1, 0, 0),
            ],
            guide,
        )
        self.assertEqual(_infer_product_from_neighbors("119", points), 834121)

    def test_backfill_repairs_mislinked_nonfoil_only_product(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        rows = [
            ("EOC", "117", "https://www.cardmarket.com/en/Magic/Products?idProduct=834120", None, 1, 0, 0),
            ("EOC", "118", "https://www.cardmarket.com/en/Magic/Products?idProduct=834268", None, 1, 0, 0),
            ("EOC", "119", None, "https://www.cardmarket.com/en/Magic/Products?idProduct=705035", 1, 0, 0),
            ("EOC", "120", "https://www.cardmarket.com/en/Magic/Products?idProduct=834122", None, 1, 0, 0),
        ]
        conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, cardmarket_url, cardmarket_url_foil,
                has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        guide = {
            705035: {"trend": 0, "trend-foil": 168.87},
            834120: {"trend": 1.0},
            834121: {"trend": 0.15},
            834122: {"trend": 1.03},
            834268: {"trend": 0.57},
        }
        updated = backfill_cardmarket_urls(conn, guide)
        row = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '119'"
        ).fetchone()
        conn.close()
        self.assertGreaterEqual(updated, 1)
        self.assertIn("834121", row[0] or "")
        self.assertIsNone(row[1])

    def test_backfill_repairs_price_outlier_nonfoil_url(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        rows = [
            ("40K", "248", "https://www.cardmarket.com/en/Magic/Products?idProduct=675760", None, 1, 0, 0),
            ("40K", "249", "https://www.cardmarket.com/en/Magic/Products?idProduct=718040", None, 1, 0, 0),
            ("40K", "250", "https://www.cardmarket.com/en/Magic/Products?idProduct=671291", None, 1, 0, 0),
        ]
        conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, cardmarket_url, cardmarket_url_foil,
                has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        guide = {
            675760: {"trend": 7.18},
            718040: {"trend": 527.88, "low": 800},
            671291: {"trend": 2.22},
        }
        updated = backfill_cardmarket_urls(conn, guide)
        row = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '249'"
        ).fetchone()
        conn.close()
        self.assertGreaterEqual(updated, 1)
        self.assertIn("671291", row[0] or "")
        self.assertIsNone(row[1])

    def test_backfill_updates_misplaced_foil_url(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO cards (set_code, collector_number, cardmarket_url, cardmarket_url_foil)
            VALUES ('LTR', '723', 'https://www.cardmarket.com/en/Magic/Products?idProduct=738285', NULL)
            """
        )
        guide = {
            738285: {"trend": 0, "trend-foil": 73.42},
            738284: {"trend": 44.23, "trend-foil": 0},
        }
        updated = backfill_cardmarket_urls(conn, guide)
        row = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '723'"
        ).fetchone()
        conn.close()
        self.assertEqual(updated, 1)
        self.assertIn("738284", row[0])
        self.assertIn("738285", row[1])

    def test_merge_keeps_repaired_nonfoil_url_over_scryfall_outlier(self):
        guide = {
            671291: {"trend": 2.22},
            718040: {"trend": 527.88},
            718047: {"trend": 0, "trend-foil": 2204.09},
        }
        nonfoil, foil = merge_cardmarket_urls(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=671291",
            None,
            {
                "finishes": ["nonfoil"],
                "purchase_uris": {
                    "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=718047",
                },
            },
            guide=guide,
        )
        self.assertIn("671291", nonfoil or "")
        self.assertIsNone(foil)

    def test_normalize_does_not_pair_scryfall_foil_product_to_outlier_nonfoil(self):
        guide = {
            718040: {"trend": 527.88},
            718047: {"trend": 0, "trend-foil": 2204.09},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=718047",
            None,
            guide,
        )
        self.assertIn("718047", foil or "")
        self.assertIsNone(nonfoil)


if __name__ == "__main__":
    unittest.main()
