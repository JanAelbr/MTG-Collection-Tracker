import unittest
from unittest.mock import patch

from api.services.card_service import _guide_price_matrix
from api.services.pricing_service import all_guide_prices_for_card, price_from_strategy


class PricingServiceEtchedTests(unittest.TestCase):
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
    def test_price_from_strategy_etched_uses_stored_value_only(self, load_guide):
        load_guide.return_value = {
            123: {"trend": 2.42, "trend-foil": 5.54},
        }
        value = price_from_strategy(
            "https://www.cardmarket.com/en/Magic/Products/Singles/123",
            2,
            "trend",
            market_value_etched=9.99,
        )
        self.assertEqual(value, 9.99)

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

    def test_guide_price_matrix_shows_stored_etched_on_active_strategy_only(self):
        matrix = _guide_price_matrix(
            {"nonfoil": {"trend": 2.0}, "foil": {"trend": 4.0}},
            stored_etched=12.5,
            price_strategy="avg7",
        )
        etched_by_strategy = {row["strategyId"]: row["etched"] for row in matrix["rows"]}
        self.assertIsNone(etched_by_strategy["trend"])
        self.assertEqual(etched_by_strategy["avg7"], 12.5)
        self.assertIsNone(etched_by_strategy["low"])


if __name__ == "__main__":
    unittest.main()
