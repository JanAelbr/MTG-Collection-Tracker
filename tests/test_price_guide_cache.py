import logging
import os
import sys
import tempfile
import unittest
import unittest.mock
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "server-backend" / "collection"
if str(COLLECTION) not in sys.path:
    sys.path.insert(0, str(COLLECTION))

from util import cardmarket_prices  # noqa: E402
from util.cardmarket_prices import (  # noqa: E402
    price_guide_cache_is_fresh,
    price_guide_expires_at,
)

BERLIN = ZoneInfo("Europe/Berlin")


def _stamp(moment: datetime) -> float:
    return moment.timestamp()


class PriceGuideExpiryTests(unittest.TestCase):
    def test_expires_at_the_next_central_european_midnight(self):
        cached = datetime(2026, 11, 15, 18, 0, tzinfo=BERLIN)
        self.assertEqual(
            price_guide_expires_at(_stamp(cached)),
            datetime(2026, 11, 16, 0, 0, tzinfo=BERLIN),
        )

    def test_same_day_cache_stays_fresh_until_midnight(self):
        cached = datetime(2026, 11, 15, 0, 10, tzinfo=BERLIN)
        later = datetime(2026, 11, 15, 23, 50, tzinfo=BERLIN)
        midnight = datetime(2026, 11, 16, 0, 0, tzinfo=BERLIN)
        self.assertTrue(price_guide_cache_is_fresh(_stamp(cached), now=later))
        self.assertFalse(price_guide_cache_is_fresh(_stamp(cached), now=midnight))

    def test_cache_from_just_before_midnight_is_stale_after(self):
        cached = datetime(2026, 11, 15, 23, 30, tzinfo=BERLIN)
        after = datetime(2026, 11, 16, 0, 5, tzinfo=BERLIN)
        self.assertFalse(price_guide_cache_is_fresh(_stamp(cached), now=after))

    def test_spring_forward_still_expires_at_local_midnight(self):
        cached = datetime(2026, 3, 29, 12, 0, tzinfo=BERLIN)
        self.assertEqual(
            price_guide_expires_at(_stamp(cached)),
            datetime(2026, 3, 30, 0, 0, tzinfo=BERLIN),
        )

    def test_fall_back_still_expires_at_local_midnight(self):
        cached = datetime(2026, 10, 25, 12, 0, tzinfo=BERLIN)
        self.assertEqual(
            price_guide_expires_at(_stamp(cached)),
            datetime(2026, 10, 26, 0, 0, tzinfo=BERLIN),
        )
        still_today = datetime(2026, 10, 25, 23, 30, tzinfo=BERLIN)
        self.assertTrue(price_guide_cache_is_fresh(_stamp(cached), now=still_today))


class EnsurePriceGuideCacheTests(unittest.TestCase):
    def tearDown(self):
        cardmarket_prices._PRICE_GUIDE_CACHE_LOGGED = False

    def test_same_cet_day_does_not_download(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "guide.json"
            cache.write_bytes(b"{}")
            cardmarket_prices._PRICE_GUIDE_CACHE_LOGGED = False
            with unittest.mock.patch.object(cardmarket_prices, "PRICE_GUIDE_CACHE", cache), \
                unittest.mock.patch.object(cardmarket_prices, "DATA_DIR", Path(temp_dir)), \
                unittest.mock.patch.object(cardmarket_prices, "http_get") as http_get:
                result = cardmarket_prices.ensure_price_guide(logger=logging.getLogger("test"))
            self.assertEqual(result, cache)
            http_get.assert_not_called()

    def test_previous_cet_day_downloads_again(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "guide.json"
            cache.write_bytes(b"{}")
            now = datetime.now(BERLIN)
            previous = datetime.combine(
                now.date() - timedelta(days=1),
                time(12, 0),
                tzinfo=BERLIN,
            )
            os.utime(cache, (previous.timestamp(), previous.timestamp()))
            response = unittest.mock.Mock()
            response.content = b"{}"
            response.raise_for_status = unittest.mock.Mock()
            with unittest.mock.patch.object(cardmarket_prices, "PRICE_GUIDE_CACHE", cache), \
                unittest.mock.patch.object(cardmarket_prices, "DATA_DIR", Path(temp_dir)), \
                unittest.mock.patch.object(
                    cardmarket_prices, "http_get", return_value=response,
                ) as http_get, \
                unittest.mock.patch.object(cardmarket_prices, "_invalidate_guide_index_cache"):
                cardmarket_prices.ensure_price_guide(logger=logging.getLogger("test"))
            http_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
