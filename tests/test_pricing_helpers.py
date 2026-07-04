import runpy
import sys
import unittest
from pathlib import Path

import pandas as pd

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.pricing_helpers import apply_strategy_to_owned_df  # noqa: E402


class PricingHelpersTests(unittest.TestCase):
    def test_apply_strategy_uses_foil_price_for_foil_only_nonfoil_purchase(self):
        df = pd.DataFrame([
            {
                "finish": 0,
                "purchase_value": 3.9,
                "cardmarket_url": None,
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
