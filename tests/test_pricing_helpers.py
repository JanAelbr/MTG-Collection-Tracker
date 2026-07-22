import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.pricing_helpers import apply_strategy_to_owned_df  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
