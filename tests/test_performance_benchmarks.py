"""Benchmark search and set-filter request paths for regression tracking."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

runpy.run_path(str(TESTS_DIR / "_paths.py"))

from api.cache import bump_cache_epoch  # noqa: E402
from api.services import reports_service  # noqa: E402
from api.services import search_service  # noqa: E402
from api.services import stats_service  # noqa: E402
from benchmark_helpers import (  # noqa: E402
    DEFAULT_CARD_COUNT,
    bench_call,
    assert_under_threshold,
    perf_threshold_ms,
    seed_benchmark_collection,
)
from util.app_tables import ensure_app_tables  # noqa: E402


class PerformanceBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._temp_dir.name) / "benchmark.db"
        cls.summary = seed_benchmark_collection(cls.db_path, card_count=DEFAULT_CARD_COUNT)
        cls.conn = sqlite3.connect(cls.db_path)
        cls.conn.row_factory = sqlite3.Row
        ensure_app_tables(cls.conn)
        cls.conn.execute(
            """
            INSERT OR IGNORE INTO user_settings (key, value)
            VALUES ('price_strategy', 'trend')
            """
        )
        cls.conn.commit()

        cls._patches = [
            patch("api.db.DB_PATH", cls.db_path),
            patch("lib.config.DB_PATH", cls.db_path),
            patch("report.ranked_cards_data.DB_PATH", cls.db_path),
            patch("api.services.pricing_service._load_guide", return_value={}),
        ]
        for item in cls._patches:
            item.start()

        cls._results: list[str] = []

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls._patches):
            item.stop()
        cls.conn.close()
        cls._temp_dir.cleanup()
        if cls._results:
            print("\n--- Performance benchmarks ---", file=sys.stderr)
            for line in cls._results:
                print(line, file=sys.stderr)

    def setUp(self):
        bump_cache_epoch()

    def _record(self, result) -> None:
        line = result.format_line()
        self._results.append(line)
        with self.subTest(result.label):
            self.assertGreater(result.median_ms, 0.0)

    def test_benchmark_search_cards_cold(self):
        def run():
            bump_cache_epoch()
            payload = search_service.search_cards(self.conn, search="Lightning")
            self.assertGreater(payload["totalMatches"], 0)

        result = bench_call(
            f"search_cards[cold] q=Lightning cards={self.summary['cards']}",
            run,
            iterations=3,
            warmup=0,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_SEARCH_COLD_MS", 750.0))

    def test_benchmark_search_cards_warm_cache(self):
        search_service.search_cards(self.conn, search="Lightning")

        result = bench_call(
            f"search_cards[warm] q=Lightning cards={self.summary['cards']}",
            lambda: search_service.search_cards(self.conn, search="Lightning"),
            iterations=5,
            warmup=1,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_SEARCH_WARM_MS", 50.0))

    def test_benchmark_filter_cards_by_set_cold(self):
        def run():
            bump_cache_epoch()
            payload = reports_service.list_report_cards(
                self.conn,
                report="all",
                set_code="LTR",
                owned_filter="all",
            )
            self.assertGreater(payload["totalMatches"], 0)
            self.assertTrue(all(card["setCode"] == "LTR" for card in payload["cards"]))

        result = bench_call(
            f"list_report_cards[cold] set=LTR cards={self.summary['cards']}",
            run,
            iterations=3,
            warmup=0,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_SET_FILTER_COLD_MS", 750.0))

    def test_benchmark_filter_cards_by_set_warm_cache(self):
        reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            owned_filter="all",
        )

        result = bench_call(
            f"list_report_cards[warm] set=LTR cards={self.summary['cards']}",
            lambda: reports_service.list_report_cards(
                self.conn,
                report="all",
                set_code="LTR",
                owned_filter="all",
            ),
            iterations=5,
            warmup=1,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_SET_FILTER_WARM_MS", 50.0))

    def test_benchmark_strategy_switch_on_warm_set_cache(self):
        reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            owned_filter="all",
        )

        def run():
            self.conn.execute(
                """
                INSERT OR REPLACE INTO user_settings (key, value)
                VALUES ('price_strategy', 'low')
                """
            )
            self.conn.commit()
            payload = reports_service.list_report_cards(
                self.conn,
                report="all",
                set_code="LTR",
                owned_filter="all",
            )
            self.assertGreater(payload["totalMatches"], 0)

        self.conn.execute(
            """
            INSERT OR REPLACE INTO user_settings (key, value)
            VALUES ('price_strategy', 'trend')
            """
        )
        self.conn.commit()

        result = bench_call(
            f"list_report_cards[strategy-switch] set=LTR cards={self.summary['cards']}",
            run,
            iterations=5,
            warmup=1,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_STRATEGY_SWITCH_MS", 25.0))

    def test_benchmark_collection_stats_cold_set(self):
        def run():
            bump_cache_epoch()
            payload = stats_service.load_collection_stats(self.conn, set_code="LTR")
            self.assertGreater(payload["stats"]["ownedCount"], 0)

        result = bench_call(
            f"load_collection_stats[cold] set=LTR purchases={self.summary['purchases']}",
            run,
            iterations=3,
            warmup=0,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_STATS_SET_COLD_MS", 200.0))

    def test_benchmark_collection_stats_cold_all(self):
        def run():
            bump_cache_epoch()
            payload = stats_service.load_collection_stats(self.conn, set_code="All")
            self.assertGreater(payload["stats"]["ownedCount"], 0)

        result = bench_call(
            f"load_collection_stats[cold] set=All purchases={self.summary['purchases']}",
            run,
            iterations=3,
            warmup=0,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_STATS_ALL_COLD_MS", 400.0))

    def test_benchmark_collection_stats_warm_cache(self):
        stats_service.load_collection_stats(self.conn, set_code="LTR")

        result = bench_call(
            f"load_collection_stats[warm] set=LTR purchases={self.summary['purchases']}",
            lambda: stats_service.load_collection_stats(self.conn, set_code="LTR"),
            iterations=5,
            warmup=1,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_STATS_WARM_MS", 25.0))

    def test_benchmark_collection_stats_strategy_switch(self):
        stats_service.load_collection_stats(self.conn, set_code="LTR")

        def run():
            self.conn.execute(
                """
                INSERT OR REPLACE INTO user_settings (key, value)
                VALUES ('price_strategy', 'low')
                """
            )
            self.conn.commit()
            payload = stats_service.load_collection_stats(self.conn, set_code="LTR")
            self.assertGreater(payload["stats"]["ownedCount"], 0)

        self.conn.execute(
            """
            INSERT OR REPLACE INTO user_settings (key, value)
            VALUES ('price_strategy', 'trend')
            """
        )
        self.conn.commit()

        result = bench_call(
            f"load_collection_stats[strategy-switch] set=LTR purchases={self.summary['purchases']}",
            run,
            iterations=5,
            warmup=1,
        )
        self._record(result)
        assert_under_threshold(
            result,
            perf_threshold_ms("LOTR_PERF_STATS_STRATEGY_SWITCH_MS", 25.0),
        )

    def test_benchmark_collection_stats_all_then_set_drilldown(self):
        stats_service.load_collection_stats(self.conn, set_code="All")

        result = bench_call(
            f"load_collection_stats[all->set] set=LTR purchases={self.summary['purchases']}",
            lambda: stats_service.load_collection_stats(self.conn, set_code="LTR"),
            iterations=5,
            warmup=1,
        )
        self._record(result)
        assert_under_threshold(
            result,
            perf_threshold_ms("LOTR_PERF_STATS_ALL_TO_SET_MS", 25.0),
        )


class PerformanceHttpBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient  # noqa: F401
        except RuntimeError as exc:
            raise unittest.SkipTest("httpx is required for HTTP benchmarks") from exc

        from api.main import app  # noqa: E402
        from fastapi.testclient import TestClient  # noqa: E402

        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._temp_dir.name) / "benchmark-http.db"
        cls.summary = seed_benchmark_collection(cls.db_path, card_count=DEFAULT_CARD_COUNT)

        cls._patches = [
            patch("api.db.DB_PATH", cls.db_path),
            patch("lib.config.DB_PATH", cls.db_path),
            patch("report.ranked_cards_data.DB_PATH", cls.db_path),
            patch("api.services.pricing_service._load_guide", return_value={}),
        ]
        for item in cls._patches:
            item.start()

        cls.client = TestClient(app)
        cls._results: list[str] = []

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls._patches):
            item.stop()
        cls._temp_dir.cleanup()
        if cls._results:
            print("\n--- HTTP performance benchmarks ---", file=sys.stderr)
            for line in cls._results:
                print(line, file=sys.stderr)

    def setUp(self):
        bump_cache_epoch()

    def _record(self, result) -> None:
        line = result.format_line()
        self._results.append(line)
        with self.subTest(result.label):
            self.assertGreater(result.median_ms, 0.0)

    def test_benchmark_http_search_endpoint(self):
        def run():
            response = self.client.get("/api/reports/search?q=Lightning&pageSize=50")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertGreater(payload["totalMatches"], 0)

        result = bench_call(
            f"GET /api/reports/search[cold] q=Lightning cards={self.summary['cards']}",
            run,
            iterations=3,
            warmup=0,
        )
        self._record(result)
        assert_under_threshold(result, perf_threshold_ms("LOTR_PERF_HTTP_SEARCH_MS", 900.0))

    def test_benchmark_http_set_filter_endpoint(self):
        def run():
            response = self.client.get(
                "/api/reports/cards?report=all&setCode=LTR&ownedFilter=all&pageSize=500"
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertGreater(payload["totalMatches"], 0)

        result = bench_call(
            f"GET /api/reports/cards[cold] set=LTR cards={self.summary['cards']}",
            run,
            iterations=3,
            warmup=0,
        )
        self._record(result)
        assert_under_threshold(
            result,
            perf_threshold_ms("LOTR_PERF_HTTP_SET_FILTER_MS", 900.0),
        )


if __name__ == "__main__":
    unittest.main()
