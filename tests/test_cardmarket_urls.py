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
    _resolve_repair_nonfoil_product_id,
    audit_cardmarket_urls,
    backfill_cardmarket_urls,
    cardmarket_url_for_finish,
    coerce_cardmarket_url,
    find_paired_product_id,
    merge_cardmarket_urls,
    normalize_cardmarket_url_columns,
    repair_finish_flag_url_mismatches,
    scryfall_url_targets,
)


class CardmarketUrlTests(unittest.TestCase):
    def test_scryfall_url_targets_prefer_finishes_over_foil_boolean(self):
        targets = scryfall_url_targets({
            "foil": True,
            "finishes": ["nonfoil", "foil"],
            "purchase_uris": {"cardmarket": "https://example.com/?idProduct=738285"},
        })
        self.assertEqual(
            targets,
            {
                FINISH_NONFOIL: "https://example.com/?idProduct=738285",
                FINISH_FOIL: "https://example.com/?idProduct=738285",
            },
        )

    def test_scryfall_url_targets_foil_only_finish(self):
        targets = scryfall_url_targets({
            "foil": True,
            "finishes": ["foil"],
            "purchase_uris": {"cardmarket": "https://example.com/?idProduct=738285"},
        })
        self.assertEqual(targets, {FINISH_FOIL: "https://example.com/?idProduct=738285"})

    def test_normalize_shares_dual_finish_product_stored_as_foil(self):
        guide = {
            716469: {"trend": 1.25, "trend-foil": 2.50},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            None,
            "https://www.cardmarket.com/en/Magic/Products?idProduct=716469",
            guide,
            has_nonfoil=1,
            has_foil=1,
        )
        self.assertIn("716469", nonfoil or "")
        self.assertIn("716469", foil or "")

    def test_normalize_shares_dual_finish_product_stored_as_nonfoil(self):
        guide = {
            716469: {"trend": 1.25, "trend-foil": 2.50},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=716469",
            None,
            guide,
            has_nonfoil=1,
            has_foil=1,
        )
        self.assertIn("716469", nonfoil or "")
        self.assertIn("716469", foil or "")

    def test_merge_cardmarket_urls_keeps_both_finishes(self):
        nonfoil, foil = merge_cardmarket_urls(
            "https://example.com/?idProduct=738286",
            None,
            {
                "foil": True,
                "finishes": ["nonfoil", "foil"],
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

    def test_find_paired_product_id_for_expensive_adjacent_one_ring(self):
        # LTR #697: foil 738253 must pair to nonfoil 738252 (~€291), not Coat 738250.
        guide = {
            738250: {"trend": 24.54, "trend-foil": 0},
            738251: {"trend": 0, "trend-foil": 36.87},
            738252: {"trend": 291.41, "trend-foil": 0},
            738253: {"trend": 0, "trend-foil": 609.76},
        }
        self.assertEqual(find_paired_product_id(738253, guide, FINISH_NONFOIL), 738252)
        self.assertEqual(find_paired_product_id(738252, guide, FINISH_FOIL), 738253)

    def test_normalize_pairs_expensive_adjacent_one_ring_nonfoil(self):
        guide = {
            738250: {"trend": 24.54, "trend-foil": 0},
            738251: {"trend": 0, "trend-foil": 36.87},
            738252: {"trend": 291.41, "trend-foil": 0},
            738253: {"trend": 0, "trend-foil": 609.76},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            None,
            "https://www.cardmarket.com/en/Magic/Products?idProduct=738253",
            guide,
        )
        self.assertIn("738252", nonfoil or "")
        self.assertIn("738253", foil or "")

    def test_normalize_repairs_one_ring_mislinked_to_previous_printing(self):
        guide = {
            738250: {"trend": 24.54, "trend-foil": 0},
            738251: {"trend": 0, "trend-foil": 36.87},
            738252: {"trend": 291.41, "trend-foil": 0},
            738253: {"trend": 0, "trend-foil": 609.76},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=738250",
            "https://www.cardmarket.com/en/Magic/Products?idProduct=738253",
            guide,
        )
        self.assertIn("738252", nonfoil or "")
        self.assertIn("738253", foil or "")

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

    def test_cardmarket_url_for_finish_skips_invented_nonfoil_on_foil_only(self):
        guide = {
            752693: {"trend": 0.35, "trend-foil": 0},
            752694: {"trend": 0, "trend-foil": 19.22},
        }
        row = {
            "cardmarket_url": None,
            "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=752694",
            "has_nonfoil": 0,
            "has_foil": 1,
            "has_etched": 0,
        }
        self.assertIsNone(cardmarket_url_for_finish(row, FINISH_NONFOIL, guide))
        self.assertIn("752694", cardmarket_url_for_finish(row, FINISH_FOIL, guide) or "")

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

    def test_backfill_keeps_expensive_valid_nonfoil_url_among_cheap_neighbors(self):
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
        backfill_cardmarket_urls(conn, guide)
        row = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '249'"
        ).fetchone()
        conn.close()
        self.assertIn("718040", row[0] or "")
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

    def test_merge_prefers_scryfall_mid_price_nonfoil_over_cheap_stored(self):
        """Chase EA cards: cheap wrong link must yield to Scryfall's real product."""
        guide = {
            701774: {"trend": 0.85},
            717741: {"trend": 16.10},
            717756: {"trend": 0.93},
            716036: {"trend": 19.73},
        }
        nonfoil, foil = merge_cardmarket_urls(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=701774",
            None,
            {
                "finishes": ["nonfoil"],
                "purchase_uris": {
                    "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=717741",
                },
            },
            guide=guide,
        )
        self.assertIn("717741", nonfoil or "")
        self.assertIsNone(foil)

        nonfoil, foil = merge_cardmarket_urls(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=717756",
            None,
            {
                "finishes": ["nonfoil"],
                "purchase_uris": {
                    "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=716036",
                },
            },
            guide=guide,
        )
        self.assertIn("716036", nonfoil or "")
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

    def test_merge_prefers_scryfall_for_underpriced_ltc_ring_urls(self):
        guide = {
            737043: {"trend": 1.08, "low": 0.5},
            718037: {"trend": 1957.52, "low": 2999},
            718038: {"trend": 481.87, "low": 680},
            718040: {"trend": 527.88, "low": 800},
        }
        nonfoil, foil = merge_cardmarket_urls(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=737043",
            None,
            {
                "foil": False,
                "finishes": ["nonfoil"],
                "purchase_uris": {
                    "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=718037",
                },
            },
            guide=guide,
        )
        self.assertIn("718037", nonfoil or "")
        self.assertIsNone(foil)

        nonfoil, foil = merge_cardmarket_urls(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=737043",
            None,
            {
                "foil": False,
                "finishes": ["nonfoil"],
                "purchase_uris": {
                    "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=718040",
                },
            },
            guide=guide,
        )
        self.assertIn("718040", nonfoil or "")

    def test_merge_moves_serialized_ring_url_to_foil_column(self):
        guide = {
            718040: {"trend": 527.88},
            718045: {"trend": 0, "trend-foil": 5716.97},
        }
        nonfoil, foil = merge_cardmarket_urls(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=718040",
            None,
            {
                "foil": True,
                "finishes": ["foil"],
                "purchase_uris": {
                    "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=718045",
                },
            },
            guide=guide,
        )
        self.assertIsNone(nonfoil)
        self.assertIn("718045", foil or "")

    def test_backfill_restores_ltc_rings_of_power_product_ids(self):
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
            ("LTC", "408", "https://www.cardmarket.com/en/Magic/Products?idProduct=737043", None, 1, 0, 0),
            ("LTC", "409", "https://www.cardmarket.com/en/Magic/Products?idProduct=737043", None, 1, 0, 0),
            ("LTC", "410", "https://www.cardmarket.com/en/Magic/Products?idProduct=737043", None, 1, 0, 0),
            ("LTC", "408z", "https://www.cardmarket.com/en/Magic/Products?idProduct=718040", None, 0, 1, 0),
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
            737043: {"trend": 1.08},
            718037: {"trend": 1957.52},
            718038: {"trend": 481.87},
            718040: {"trend": 527.88},
            718045: {"trend": 0, "trend-foil": 5716.97},
        }
        updated = backfill_cardmarket_urls(conn, guide)
        row408 = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '408'"
        ).fetchone()
        row408z = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '408z'"
        ).fetchone()
        conn.close()
        self.assertGreaterEqual(updated, 4)
        self.assertIn("718037", row408[0] or "")
        self.assertIn("718045", row408z[1] or "")
        self.assertIsNone(row408z[0])

    def test_normalize_does_not_invent_nonfoil_for_foil_only_print(self):
        guide = {
            752693: {"trend": 0.35, "trend-foil": 0},
            752694: {"trend": 0, "trend-foil": 19.22},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            None,
            "https://www.cardmarket.com/en/Magic/Products?idProduct=752694",
            guide,
            has_nonfoil=0,
            has_foil=1,
            has_etched=0,
        )
        self.assertIsNone(nonfoil)
        self.assertIn("752694", foil or "")

    def test_normalize_without_flags_still_pairs_sparse_foil(self):
        guide = {
            752693: {"trend": 0.35, "trend-foil": 0},
            752694: {"trend": 0, "trend-foil": 19.22},
        }
        nonfoil, foil = normalize_cardmarket_url_columns(
            None,
            "https://www.cardmarket.com/en/Magic/Products?idProduct=752694",
            guide,
        )
        self.assertIn("752693", nonfoil or "")
        self.assertIn("752694", foil or "")

    def test_audit_flags_foil_only_with_nonfoil_url(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, cardmarket_url, cardmarket_url_foil,
                has_nonfoil, has_foil, has_etched
            ) VALUES (
                'CLU', '279', 'Sacred Foundry',
                'https://www.cardmarket.com/en/Magic/Products?idProduct=752693',
                'https://www.cardmarket.com/en/Magic/Products?idProduct=752694',
                0, 1, 0
            )
            """
        )
        guide = {
            752693: {"trend": 0.35, "trend-foil": 0},
            752694: {"trend": 0, "trend-foil": 19.22},
        }
        report = audit_cardmarket_urls(conn, guide)
        self.assertEqual(report["counts"]["foil_only_has_nonfoil_url"], 1)
        sample = report["findings"]["foil_only_has_nonfoil_url"][0]
        self.assertEqual(sample["setCode"], "CLU")
        self.assertEqual(sample["collectorNumber"], "279")

        repaired = repair_finish_flag_url_mismatches(conn, guide)
        row = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '279'"
        ).fetchone()
        conn.close()
        self.assertEqual(repaired, 1)
        self.assertIsNone(row[0])
        self.assertIn("752694", row[1] or "")

    def test_backfill_does_not_reinvent_nonfoil_for_foil_only(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, cardmarket_url, cardmarket_url_foil,
                has_nonfoil, has_foil, has_etched
            ) VALUES (
                'CLU', '279', 'Sacred Foundry',
                'https://www.cardmarket.com/en/Magic/Products?idProduct=752693',
                'https://www.cardmarket.com/en/Magic/Products?idProduct=752694',
                0, 1, 0
            )
            """
        )
        guide = {
            752693: {"trend": 0.35, "trend-foil": 0},
            752694: {"trend": 0, "trend-foil": 19.22},
        }
        backfill_cardmarket_urls(conn, guide)
        row = conn.execute(
            "SELECT cardmarket_url, cardmarket_url_foil FROM cards WHERE collector_number = '279'"
        ).fetchone()
        report = audit_cardmarket_urls(conn, guide)
        conn.close()
        self.assertIsNone(row[0])
        self.assertIn("752694", row[1] or "")
        self.assertEqual(report["counts"]["foil_only_has_nonfoil_url"], 0)

    def test_infer_does_not_jump_across_scrambled_set_ids(self):
        points = [
            (117, 675233),
            (123, 674731),
            (125, 675239),
        ]
        self.assertIsNone(_infer_product_from_neighbors("124", points))

    def test_resolve_repair_rejects_product_owned_by_another_card(self):
        guide = {
            675233: {"trend": 0.2},
            675238: {"trend": 4.86},
            675239: {"trend": 0.27},
        }
        points = [(117, 675233), (125, 675239)]
        inferred = _resolve_repair_nonfoil_product_id(
            "124",
            points,
            guide,
            owned_product_ids={675233, 675238, 675239},
        )
        self.assertIsNone(inferred)

    def test_backfill_restores_scryfall_url_on_duplicate_product(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                scryfall_cardmarket_url TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        rows = [
            ("40K", "35", "https://www.cardmarket.com/en/Magic/Products?idProduct=675238",
             None, "https://www.cardmarket.com/en/Magic/Products?idProduct=675238", 1, 0, 0),
            ("40K", "124", "https://www.cardmarket.com/en/Magic/Products?idProduct=675238",
             None, "https://www.cardmarket.com/en/Magic/Products?idProduct=674727", 1, 0, 0),
            ("40K", "125", "https://www.cardmarket.com/en/Magic/Products?idProduct=675239",
             None, "https://www.cardmarket.com/en/Magic/Products?idProduct=675239", 1, 0, 0),
        ]
        conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, cardmarket_url, cardmarket_url_foil,
                scryfall_cardmarket_url, has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        guide = {
            674727: {"trend": 28.19, "trend-foil": 40.94},
            675238: {"trend": 4.86, "trend-foil": 8.59},
            675239: {"trend": 0.27, "trend-foil": 0.58},
        }
        backfill_cardmarket_urls(conn, guide, fetch_set_cards=lambda _set: [])
        row = conn.execute(
            "SELECT cardmarket_url FROM cards WHERE collector_number = '124'"
        ).fetchone()
        other = conn.execute(
            "SELECT cardmarket_url FROM cards WHERE collector_number = '35'"
        ).fetchone()
        conn.close()
        self.assertIn("674727", row[0] or "")
        self.assertIn("675238", other[0] or "")

    def test_backfill_fetches_scryfall_for_collision_set(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                scryfall_cardmarket_url TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, cardmarket_url, cardmarket_url_foil,
                scryfall_cardmarket_url, has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("40K", "35", "https://www.cardmarket.com/en/Magic/Products?idProduct=675238",
                 None, None, 1, 0, 0),
                ("40K", "124", "https://www.cardmarket.com/en/Magic/Products?idProduct=675238",
                 None, None, 1, 0, 0),
            ],
        )
        guide = {
            674727: {"trend": 28.19},
            675238: {"trend": 4.86},
        }

        def fetch_set_cards(set_code):
            self.assertEqual(set_code, "40K")
            return [
                {
                    "collector_number": "35",
                    "finishes": ["nonfoil"],
                    "purchase_uris": {
                        "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=675238",
                    },
                },
                {
                    "collector_number": "124",
                    "finishes": ["nonfoil"],
                    "purchase_uris": {
                        "cardmarket": "https://www.cardmarket.com/en/Magic/Products?idProduct=674727",
                    },
                },
            ]

        backfill_cardmarket_urls(conn, guide, fetch_set_cards=fetch_set_cards)
        row = conn.execute(
            """
            SELECT cardmarket_url, scryfall_cardmarket_url
            FROM cards WHERE collector_number = '124'
            """
        ).fetchone()
        conn.close()
        self.assertIn("674727", row[0] or "")
        self.assertIn("674727", row[1] or "")

    def test_backfill_skips_scryfall_sourced_collisions(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                scryfall_cardmarket_url TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        scryfall_url = (
            "https://www.cardmarket.com/en/Magic/Products?idProduct=100"
            "&referrer=scryfall&utm_source=scryfall"
        )
        conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, cardmarket_url, cardmarket_url_foil,
                scryfall_cardmarket_url, has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2X2", "1", scryfall_url, None, None, 1, 0, 0),
                ("2X2", "2", scryfall_url, None, None, 1, 0, 0),
            ],
        )
        fetched = []
        backfill_cardmarket_urls(
            conn,
            {100: {"trend": 1.0}},
            fetch_set_cards=lambda set_code: fetched.append(set_code) or [],
        )
        conn.close()
        self.assertEqual(fetched, [])


if __name__ == "__main__":
    unittest.main()
