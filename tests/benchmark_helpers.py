"""Helpers for collection API performance benchmarks."""

from __future__ import annotations

import os
import sqlite3
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from util.schema import ensure_database_schema

DEFAULT_CARD_COUNT = 2500
DEFAULT_SET_CODES = ("LTR", "MH3", "BLB", "OTJ", "DSK", "FDN")

SEARCH_NAMES = (
    "Lightning Bolt",
    "Lightning Greaves",
    "Counterspell",
    "Sol Ring",
    "Frodo Baggins",
    "Island",
    "Plains",
    "Sheoldred, the Apocalypse",
    "The One Ring",
    "Orcish Bowmasters",
)

OTHER_NAMES = (
    "Ancient Tomb",
    "Thoughtseize",
    "Ragavan, Nimble Pilferer",
    "Ledger Shredder",
    "Delver of Secrets",
    "Snapcaster Mage",
    "Tarmogoyf",
    "Dark Confidant",
    "Birds of Paradise",
    "Llanowar Elves",
)


@dataclass(frozen=True)
class BenchResult:
    label: str
    samples_ms: tuple[float, ...]

    @property
    def median_ms(self) -> float:
        return statistics.median(self.samples_ms)

    @property
    def p95_ms(self) -> float:
        if len(self.samples_ms) == 1:
            return self.samples_ms[0]
        ordered = sorted(self.samples_ms)
        index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
        return ordered[index]

    def format_line(self) -> str:
        sample_text = ", ".join(f"{value:.1f}" for value in self.samples_ms)
        return (
            f"PERF {self.label}: "
            f"median={self.median_ms:.1f}ms p95={self.p95_ms:.1f}ms "
            f"[{sample_text}]"
        )


def seed_benchmark_collection(
    db_path: Path,
    *,
    card_count: int = DEFAULT_CARD_COUNT,
    set_codes: tuple[str, ...] = DEFAULT_SET_CODES,
) -> dict[str, int]:
    """Create a multi-set catalog with purchases for benchmark runs."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        ensure_database_schema(conn)
        conn.execute("DELETE FROM purchases")
        conn.execute("DELETE FROM cards")
        conn.execute("DELETE FROM sets")

        cards_per_set = max(1, card_count // len(set_codes))
        purchase_id = 0
        for set_index, set_code in enumerate(set_codes):
            conn.execute(
                """
                INSERT INTO sets (set_code, name, released_at, scryfall_uri, updated_at)
                VALUES (?, ?, ?, '', '2026-01-01')
                """,
                (
                    set_code,
                    f"Benchmark {set_code}",
                    f"202{set_index % 5}-0{(set_index % 9) + 1}-15",
                ),
            )
            for number in range(1, cards_per_set + 1):
                global_index = set_index * cards_per_set + number
                if global_index > card_count:
                    break
                name_pool = SEARCH_NAMES if global_index % 4 == 0 else OTHER_NAMES
                name = name_pool[global_index % len(name_pool)]
                if global_index % 17 == 0:
                    name = f"{name} {global_index}"
                collector_number = str(number)
                card_id = f"{set_code}-{collector_number}"
                market_value = round(0.5 + (global_index % 40) * 0.25, 2)
                market_value_foil = round(market_value * 1.8, 2)
                conn.execute(
                    """
                    INSERT INTO cards (
                        id, set_code, collector_number, name, art_style,
                        market_value, market_value_foil, market_value_etched,
                        has_nonfoil, has_foil, has_etched,
                        image_uri, cardmarket_url, cardmarket_url_foil,
                        colors, type_line, card_type
                    ) VALUES (?, ?, ?, ?, 'All', ?, ?, NULL, 1, 1, 0, '', NULL, NULL, NULL, NULL, NULL)
                    """,
                    (
                        card_id,
                        set_code,
                        collector_number,
                        name,
                        market_value,
                        market_value_foil,
                    ),
                )
                if global_index % 3 == 0:
                    purchase_id += 1
                    conn.execute(
                        """
                        INSERT INTO purchases (
                            set_code, collector_number, purchase_value, finish
                        ) VALUES (?, ?, ?, 0)
                        """,
                        (set_code, collector_number, round(market_value * 0.8, 2)),
                    )
        conn.commit()
        summary = {
            "cards": conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0],
            "purchases": conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0],
            "sets": conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0],
        }
    finally:
        conn.close()
    return summary


DEFAULT_GUIDE_PRODUCT_COUNT = 125_000


def build_synthetic_price_guide_payload(
    product_count: int = DEFAULT_GUIDE_PRODUCT_COUNT,
) -> dict:
    """Build a Cardmarket price-guide JSON payload sized like the real feed.

    The real feed is ~125k products / ~24MB of JSON. Benchmarks that mock the
    guide to ``{}`` never pay (or measure) that cold JSON-parse + pickle-cache
    cost, so this generates a representative subset with the same field shape
    (``idProduct`` plus trend/avg/low, foil variants for ~1 in 3 products).
    """
    products = []
    for index in range(1, product_count + 1):
        entry = {
            "idProduct": index,
            "trend": round(0.1 + (index % 500) * 0.15, 2),
            "avg": round(0.1 + (index % 480) * 0.14, 2),
            "avg7": round(0.1 + (index % 460) * 0.13, 2),
            "avg30": round(0.1 + (index % 440) * 0.12, 2),
            "avg1": round(0.1 + (index % 420) * 0.11, 2),
            "low": round(0.05 + (index % 100) * 0.05, 2),
        }
        if index % 3 == 0:
            entry.update(
                {
                    "trend-foil": round(0.2 + (index % 500) * 0.3, 2),
                    "avg-foil": round(0.2 + (index % 480) * 0.28, 2),
                    "avg7-foil": round(0.2 + (index % 460) * 0.26, 2),
                    "avg30-foil": round(0.2 + (index % 440) * 0.24, 2),
                    "avg1-foil": round(0.2 + (index % 420) * 0.22, 2),
                    "low-foil": round(0.1 + (index % 100) * 0.1, 2),
                }
            )
        products.append(entry)
    return {"priceGuides": products}


def bench_call(
    label: str,
    func,
    *,
    iterations: int = 5,
    warmup: int = 1,
) -> BenchResult:
    samples: list[float] = []
    total = warmup + iterations
    for index in range(total):
        start = time.perf_counter()
        func()
        elapsed_ms = (time.perf_counter() - start) * 1000
        if index >= warmup:
            samples.append(elapsed_ms)
    return BenchResult(label=label, samples_ms=tuple(samples))


def perf_threshold_ms(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return float(raw)


def assert_under_threshold(result: BenchResult, threshold_ms: float) -> None:
    if os.environ.get("LOTR_PERF_STRICT") != "1":
        return
    if result.p95_ms > threshold_ms:
        raise AssertionError(
            f"{result.label} p95 {result.p95_ms:.1f}ms exceeds {threshold_ms:.1f}ms"
        )
