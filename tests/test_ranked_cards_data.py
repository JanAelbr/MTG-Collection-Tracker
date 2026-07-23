import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.ranked_cards_data import expand_cards_for_ranking, serialize_ranked_cards  # noqa: E402


class RankedCardsDataTests(unittest.TestCase):
    def test_owned_without_price_is_kept(self):
        cards_df = pd.DataFrame([
            {
                "set_code": "LTR",
                "collector_number": "10",
                "name": "Test Card",
                "art_style": "Main",
                "image_uri": "",
                "cardmarket_url": "",
                "market_value": None,
                "market_value_foil": None,
                "market_value_etched": None,
                "has_nonfoil": 1,
                "has_foil": 1,
                "has_etched": 0,
                "finish": 0,
                "purchase_value": 1.5,
                "current_value": None,
                "profit_loss": None,
            }
        ])

        expanded = expand_cards_for_ranking(cards_df)

        self.assertEqual(len(expanded), 1)
        row = expanded.iloc[0]
        self.assertEqual(row["purchase_value"], 1.5)
        self.assertTrue(pd.isna(row["current_value"]))

    def test_unowned_without_price_is_kept(self):
        cards_df = pd.DataFrame([
            {
                "set_code": "LTR",
                "collector_number": "11",
                "name": "Unowned Card",
                "art_style": "Main",
                "image_uri": "",
                "cardmarket_url": "",
                "market_value": None,
                "market_value_foil": None,
                "market_value_etched": None,
                "has_nonfoil": 0,
                "has_foil": 0,
                "has_etched": 0,
                "finish": pd.NA,
                "purchase_value": None,
                "current_value": None,
                "profit_loss": None,
            }
        ])

        expanded = expand_cards_for_ranking(cards_df)

        self.assertEqual(len(expanded), 1)
        self.assertTrue(pd.isna(expanded.iloc[0]["purchase_value"]))

    def test_unowned_with_finish_flags_but_no_prices_uses_fallback_row(self):
        cards_df = pd.DataFrame([
            {
                "set_code": "HOU",
                "collector_number": "73",
                "name": "Razaketh, the Foulblooded",
                "art_style": "All",
                "image_uri": "",
                "cardmarket_url": "",
                "market_value": None,
                "market_value_foil": None,
                "market_value_etched": None,
                "has_nonfoil": 1,
                "has_foil": 1,
                "has_etched": 0,
                "finish": pd.NA,
                "purchase_value": None,
                "current_value": None,
                "profit_loss": None,
            }
        ])

        expanded = expand_cards_for_ranking(cards_df)

        self.assertEqual(len(expanded), 1)
        self.assertTrue(pd.isna(expanded.iloc[0]["purchase_value"]))

    def test_unowned_with_prices_expands_priced_finishes_only(self):
        cards_df = pd.DataFrame([
            {
                "set_code": "HOU",
                "collector_number": "73",
                "name": "Razaketh, the Foulblooded",
                "art_style": "All",
                "image_uri": "",
                "cardmarket_url": "",
                "market_value": 2.5,
                "market_value_foil": 4.0,
                "market_value_etched": None,
                "has_nonfoil": 1,
                "has_foil": 1,
                "has_etched": 0,
                "finish": pd.NA,
                "purchase_value": None,
                "current_value": None,
                "profit_loss": None,
            }
        ])

        expanded = expand_cards_for_ranking(cards_df)
        finishes = sorted(int(finish) for finish in expanded["finish"])

        self.assertEqual(len(expanded), 2)
        self.assertEqual(finishes, [0, 1])

    def test_foil_only_with_stale_nonfoil_price_lists_foil_only(self):
        cards_df = pd.DataFrame([
            {
                "set_code": "CLU",
                "collector_number": "279",
                "name": "Sacred Foundry",
                "art_style": "Main",
                "image_uri": "",
                "cardmarket_url": "",
                "market_value": 0.35,
                "market_value_foil": 19.22,
                "market_value_etched": None,
                "has_nonfoil": 0,
                "has_foil": 1,
                "has_etched": 0,
                "finish": pd.NA,
                "purchase_value": None,
                "current_value": None,
                "profit_loss": None,
            }
        ])

        expanded = expand_cards_for_ranking(cards_df)
        finishes = [int(finish) for finish in expanded["finish"]]

        self.assertEqual(len(expanded), 1)
        self.assertEqual(finishes, [1])
        self.assertEqual(float(expanded.iloc[0]["current_value"]), 19.22)

    def test_foil_only_without_prices_uses_foil_fallback(self):
        cards_df = pd.DataFrame([
            {
                "set_code": "CLU",
                "collector_number": "279",
                "name": "Sacred Foundry",
                "art_style": "Main",
                "image_uri": "",
                "cardmarket_url": "",
                "market_value": None,
                "market_value_foil": None,
                "market_value_etched": None,
                "has_nonfoil": 0,
                "has_foil": 1,
                "has_etched": 0,
                "finish": pd.NA,
                "purchase_value": None,
                "current_value": None,
                "profit_loss": None,
            }
        ])

        expanded = expand_cards_for_ranking(cards_df)

        self.assertEqual(len(expanded), 1)
        self.assertEqual(int(expanded.iloc[0]["finish"]), 1)

    def test_all_cards_query_selects_finish_flags(self):
        from report.report_queries import ALL_CARDS_QUERY, ORPHAN_PURCHASES_QUERY

        for column in ("has_nonfoil", "has_foil", "has_etched"):
            self.assertIn(column, ALL_CARDS_QUERY)
            self.assertIn(column, ORPHAN_PURCHASES_QUERY)

    def test_serialize_ranked_cards_includes_foil_cardmarket_url(self):
        cards_df = pd.DataFrame([
            {
                "set_code": "LTR",
                "collector_number": "790",
                "name": "The Ozolith",
                "art_style": "15. Surge foil",
                "image_uri": "",
                "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=100",
                "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=200",
                "market_value": 10.0,
                "market_value_foil": 144.91,
                "market_value_etched": None,
                "has_nonfoil": 0,
                "has_foil": 1,
                "has_etched": 0,
                "finish": 1,
                "purchase_value": 100.0,
                "current_value": 144.91,
                "profit_loss": 44.91,
                "colors": None,
                "type_line": "Legendary Artifact",
                "card_type": "artifact",
            }
        ])

        cards = serialize_ranked_cards(cards_df)

        self.assertEqual(
            cards[0]["cardmarket_url_foil"],
            "https://www.cardmarket.com/en/Magic/Products?idProduct=200",
        )


if __name__ == "__main__":
    unittest.main()
