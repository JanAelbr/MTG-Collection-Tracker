import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.http_client import format_request_url, http_get  # noqa: E402


class HttpClientTests(unittest.TestCase):
    def test_format_request_url_appends_params(self):
        url = format_request_url(
            "https://api.example.com/search",
            {"q": "set:ltr", "unique": "prints"},
        )
        self.assertIn("q=set%3Altr", url)
        self.assertIn("unique=prints", url)

    @patch("util.http_client.requests.get")
    def test_http_get_logs_request_and_response(self, get_mock):
        response = MagicMock()
        response.status_code = 200
        get_mock.return_value = response
        request_log = MagicMock(spec=logging.Logger)

        result = http_get(
            "https://api.example.com/sets/ltr",
            headers={"User-Agent": "test"},
            logger=request_log,
            label="Scryfall set LTR",
        )

        self.assertIs(result, response)
        get_mock.assert_called_once()
        request_log.info.assert_any_call(
            "HTTP GET %s (%s)",
            "https://api.example.com/sets/ltr",
            "Scryfall set LTR",
        )
        request_log.info.assert_any_call(
            "HTTP GET %s -> HTTP %s",
            "https://api.example.com/sets/ltr",
            200,
        )


if __name__ == "__main__":
    unittest.main()
