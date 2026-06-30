import runpy
import unittest
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.stats_service import _serialize_stats_page  # noqa: E402


class StatsSerializationTests(unittest.TestCase):
    def test_unknown_stats_fields_serialized(self):
        page = {
            "unknownInvested": 12.5,
            "unknownCount": 2,
            "unknownCards": [
                {
                    "set_code": "LTR",
                    "collector_number": "1",
                    "name": "Test",
                    "art_style": "Main",
                    "foil": 0,
                },
            ],
        }
        result = _serialize_stats_page(page)
        self.assertEqual(result["unknownInvested"], 12.5)
        self.assertEqual(result["unknownCount"], 2)
        self.assertEqual(len(result["unknownCards"]), 1)


if __name__ == "__main__":
    unittest.main()
