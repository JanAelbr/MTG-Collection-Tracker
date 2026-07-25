import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.pricing_helpers import (  # noqa: E402
    apply_strategy_to_deck_df,
    apply_strategy_to_owned_df,
)


class PricingHelpersTests(unittest.TestCase):
    @patch("api.services.pricing_helpers.price_from_strategy")
    def test_apply_strategy_uses_foil_price_for_foil_only_nonfoil_purchase(self, price_mock):
        def price_for_finish(_url, finish, _strategy, **_kwargs):
            return 4.81 if int(finish) == 1 else None

        price_mock.side_effect = price_for_finish
        df = pd.DataFrame([
            {
                "finish": 0,
                "purchase_value": 3.9,
                "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products/Singles/Example/Card",
                "cardmarket_url_foil": None,
                "market_value": None,
                "market_value_foil": 4.81,
                "market_value_etched": None,
                "has_nonfoil": 0,
                "has_foil": 1,
                "has_etched": 0,
            },
        ])
        updated = apply_strategy_to_owned_df(df, "trend")
        self.assertEqual(updated.iloc[0]["current_value"], 4.81)
        self.assertAlmostEqual(updated.iloc[0]["profit_loss"], 4.81 - 3.9)

    @patch("api.services.pricing_helpers.price_from_strategy")
    def test_apply_strategy_to_deck_df_passes_finish_flags(self, price_mock):
        price_mock.return_value = 5.41
        df = pd.DataFrame([
            {
                "in_catalog": 1,
                "finish": 2,
                "qty": 1,
                "owned_qty": 1,
                "purchase_value": None,
                "cardmarket_url": None,
                "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=511260",
                "market_value": None,
                "market_value_foil": None,
                "market_value_etched": 5.41,
                "has_nonfoil": 0,
                "has_foil": 0,
                "has_etched": 1,
            },
        ])
        updated = apply_strategy_to_deck_df(df, "trend")
        self.assertEqual(updated.iloc[0]["unit_value"], 5.41)
        self.assertEqual(updated.iloc[0]["current_value"], 5.41)
        kwargs = price_mock.call_args.kwargs
        self.assertEqual(kwargs["has_nonfoil"], 0)
        self.assertEqual(kwargs["has_foil"], 0)
        self.assertEqual(kwargs["has_etched"], 1)


if __name__ == "__main__":
    unittest.main()
