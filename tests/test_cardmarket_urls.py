import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL  # noqa: E402
from util.cardmarket_urls import (  # noqa: E402
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

    def test_find_paired_product_id_for_ltr_nazgul(self):
        guide = {
            738284: {"trend": 44.23, "trend-foil": 0},
            738285: {"trend": 0, "trend-foil": 73.42},
        }
        self.assertEqual(find_paired_product_id(738285, guide, FINISH_NONFOIL), 738284)
        self.assertEqual(find_paired_product_id(738284, guide, FINISH_FOIL), 738285)

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

    def test_cardmarket_url_for_finish_returns_none_for_etched(self):
        row = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=738284",
            "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=738285",
        }
        self.assertIsNone(cardmarket_url_for_finish(row, FINISH_ETCHED, {}))

    def test_cardmarket_url_for_finish_treats_nan_foil_url_as_missing(self):
        row = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=738284",
            "cardmarket_url_foil": float("nan"),
        }
        url = cardmarket_url_for_finish(row, FINISH_NONFOIL, {})
        self.assertIn("738284", url or "")

    def test_coerce_cardmarket_url_rejects_nan(self):
        self.assertIsNone(coerce_cardmarket_url(float("nan")))

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


if __name__ == "__main__":
    unittest.main()
