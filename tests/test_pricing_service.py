import unittest
from unittest.mock import patch

import pandas as pd

from api.services.card_service import _guide_price_matrix
from api.services.pricing_helpers import build_neutral_owned_df
from api.services.pricing_service import (
    all_guide_prices_for_card,
    price_from_strategy,
    values_by_strategy_for_finish,
)


class PricingServiceEtchedTests(unittest.TestCase):
    @patch("api.services.pricing_service._load_guide")
    def test_all_guide_prices_resolves_nonfoil_from_foil_only_url(self, load_guide):
        load_guide.return_value = {
            737814: {"trend": 1.02, "avg": 1.42},
            737816: {"trend-foil": 1.72, "avg-foil": 1.71},
        }
        grouped = all_guide_prices_for_card(
            None,
            "https://www.cardmarket.com/en/Magic/Products?idProduct=737816",
        )
        self.assertEqual(grouped["nonfoil"]["trend"], 1.02)
        self.assertEqual(grouped["foil"]["trend"], 1.72)

    @patch("api.services.pricing_service._load_guide")
    def test_all_guide_prices_skips_nonfoil_when_print_is_foil_only(self, load_guide):
        load_guide.return_value = {
            752693: {"trend": 0.35, "avg": 0.37},
            752694: {"trend": 0, "trend-foil": 19.22, "avg-foil": 19.0},
        }
        grouped = all_guide_prices_for_card(
            None,
            "https://www.cardmarket.com/en/Magic/Products?idProduct=752694",
            has_nonfoil=0,
            has_foil=1,
            has_etched=0,
        )
        self.assertIsNone(grouped["nonfoil"]["trend"])
        self.assertEqual(grouped["foil"]["trend"], 19.22)

    @patch("api.services.pricing_service.guide_prices_for_url")
    def test_all_guide_prices_for_card_does_not_backfill_etched(self, guide_prices_for_url):
        guide_prices_for_url.side_effect = lambda url: {
            "https://example.com/nonfoil": {
                "trend_nonfoil": 2.42,
                "trend_foil": 5.54,
            },
            "https://example.com/foil": {
                "trend_foil": 5.54,
            },
        }.get(url, {})
        grouped = all_guide_prices_for_card("https://example.com/nonfoil", "https://example.com/foil")
        self.assertEqual(grouped["nonfoil"]["trend"], 2.42)
        self.assertEqual(grouped["foil"]["trend"], 5.54)
        self.assertEqual(grouped["etched"], {})

    @patch("api.services.pricing_service.guide_prices_for_url")
    @patch("api.services.pricing_service.cardmarket_url_for_finish")
    def test_all_guide_prices_for_card_uses_foil_keys_from_primary_url(
        self,
        cardmarket_url_for_finish,
        guide_prices_for_url,
    ):
        cardmarket_url_for_finish.return_value = None
        guide_prices_for_url.return_value = {
            "trend_nonfoil": 1.2,
            "trend_foil": 3.4,
            "avg_nonfoil": 1.1,
            "avg_foil": 3.1,
        }
        grouped = all_guide_prices_for_card("https://example.com/card", None)
        self.assertEqual(grouped["nonfoil"]["trend"], 1.2)
        self.assertEqual(grouped["foil"]["trend"], 3.4)
        self.assertEqual(grouped["foil"]["avg"], 3.1)

    @patch("api.services.pricing_service._load_guide")
    def test_price_from_strategy_returns_none_for_guide_outlier_without_fallback(self, load_guide):
        load_guide.return_value = {
            718040: {"trend": 527.88, "low": 800},
            718047: {"trend": 0, "trend-foil": 2204.09},
        }
        value = price_from_strategy(
            "https://www.cardmarket.com/en/Magic/Products?idProduct=718047",
            0,
            "trend",
            market_value=2.22,
        )
        self.assertIsNone(value)

    @patch("api.services.pricing_service._load_guide")
    def test_price_from_strategy_etched_ignores_stored_value(self, load_guide):
        load_guide.return_value = {
            123: {"trend": 2.42, "trend-foil": 5.54},
        }
        value = price_from_strategy(
            "https://www.cardmarket.com/en/Magic/Products/Singles/123",
            2,
            "trend",
            market_value_etched=9.99,
        )
        self.assertIsNone(value)

    @patch("api.services.pricing_service._load_guide")
    def test_price_from_strategy_etched_ignores_nonfoil_guide(self, load_guide):
        load_guide.return_value = {
            123: {"trend": 2.42, "trend-foil": 5.54},
        }
        value = price_from_strategy(
            "https://www.cardmarket.com/en/Magic/Products/Singles/123",
            2,
            "trend",
            market_value_etched=None,
        )
        self.assertIsNone(value)

    def test_guide_price_matrix_does_not_inject_stored_etched(self):
        matrix = _guide_price_matrix(
            {"nonfoil": {"trend": 2.0}, "foil": {"trend": 4.0}},
            stored_etched=12.5,
            price_strategy="avg7",
        )
        etched_by_strategy = {row["strategyId"]: row["etched"] for row in matrix["rows"]}
        self.assertIsNone(etched_by_strategy["trend"])
        self.assertIsNone(etched_by_strategy["avg7"])
        self.assertIsNone(etched_by_strategy["low"])

    def test_values_by_strategy_for_finish_uses_foil_guide_for_etched_only(self):
        card = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=718037",
            "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=718057",
            "market_value_etched": None,
            "has_nonfoil": 0,
            "has_foil": 0,
            "has_etched": 1,
        }
        with patch("api.services.pricing_service._load_guide") as load_guide:
            load_guide.return_value = {
                718057: {"trend-foil": 0.34, "avg-foil": 0.35},
            }
            values = values_by_strategy_for_finish(card, 2)
        self.assertEqual(values["trend"], 0.34)

    def test_values_by_strategy_for_finish_uses_ltc_split_block_foil(self):
        card = {
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=735309",
            "cardmarket_url_foil": None,
            "market_value": 12.16,
            "market_value_foil": None,
        }
        with patch("api.services.pricing_service._load_guide") as load_guide:
            load_guide.return_value = {
                735309: {"trend": 12.16, "trend-foil": 0},
                735329: {"trend": 0, "trend-foil": 11.27},
            }
            values = values_by_strategy_for_finish(card, 1)
        self.assertEqual(values["trend"], 11.27)

    def test_values_by_strategy_for_finish_does_not_fallback_to_stored_market_value(self):
        card = {
            "cardmarket_url": float("nan"),
            "cardmarket_url_foil": float("nan"),
            "market_value": 2.0,
            "market_value_foil": 3.0,
        }
        values = values_by_strategy_for_finish(card, 0)
        self.assertIsNone(values.get("trend"))

    def test_build_neutral_owned_df_does_not_fallback_to_stored_market_value(self):
        raw = pd.DataFrame([{
            "set_code": "LTR",
            "collector_number": "1",
            "name": "Test Card",
            "art_style": "Main",
            "finish": 0,
            "purchase_value": 1.0,
            "market_value": 2.0,
            "market_value_foil": 3.0,
            "market_value_etched": None,
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
            "cardmarket_url": float("nan"),
            "cardmarket_url_foil": float("nan"),
        }])
        neutral = build_neutral_owned_df(raw)
        self.assertIsNone(neutral.iloc[0]["values_by_finish"][0]["trend"])


if __name__ == "__main__":
    unittest.main()
