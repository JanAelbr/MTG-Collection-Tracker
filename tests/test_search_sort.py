import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.search_service import (  # noqa: E402
    _rank_search_pool,
    normalize_search_sort,
)


class SearchRaritySortTests(unittest.TestCase):
    def test_normalize_includes_rarity(self):
        self.assertEqual(normalize_search_sort("rarity"), "rarity")
        self.assertEqual(normalize_search_sort("power"), "power")
        self.assertEqual(normalize_search_sort("nope"), "newest")

    def test_rank_search_pool_by_rarity(self):
        pool = [
            {"name": "Mythic", "rarity": "mythic", "setCode": "A", "collectorNumber": "1"},
            {"name": "Common", "rarity": "common", "setCode": "A", "collectorNumber": "2"},
            {"name": "Rare", "rarity": "rare", "setCode": "A", "collectorNumber": "3"},
        ]
        ranked = _rank_search_pool(
            pool,
            sort="rarity",
            sort_dir="asc",
            release_dates={},
        )
        self.assertEqual([card["name"] for card in ranked], ["Common", "Rare", "Mythic"])

        ranked_desc = _rank_search_pool(
            pool,
            sort="rarity",
            sort_dir="desc",
            release_dates={},
        )
        self.assertEqual(
            [card["name"] for card in ranked_desc],
            ["Mythic", "Rare", "Common"],
        )

    def test_rank_search_pool_by_power(self):
        pool = [
            {"name": "Small", "power": "1", "setCode": "A", "collectorNumber": "1"},
            {"name": "Big", "power": "5", "setCode": "A", "collectorNumber": "2"},
            {"name": "Star", "power": "*", "setCode": "A", "collectorNumber": "3"},
        ]
        ranked = _rank_search_pool(
            pool,
            sort="power",
            sort_dir="desc",
            release_dates={},
        )
        self.assertEqual([card["name"] for card in ranked], ["Big", "Small", "Star"])


if __name__ == "__main__":
    unittest.main()
