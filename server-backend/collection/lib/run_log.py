"""Shared logging setup for CLI scripts and the FastAPI app."""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

ROOT_LOGGER_NAME = "lotr"
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


# Format a duration for human-readable log output.
def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}m {remainder:.1f}s"


# Configure the root project logger once per process.
def configure_logging(*, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    level = logging.DEBUG if verbose else logging.INFO

    if logger.handlers:
        logger.setLevel(level)
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


# Return a namespaced logger, configuring defaults on first use.
def get_logger(name: str) -> logging.Logger:
    root = logging.getLogger(ROOT_LOGGER_NAME)
    if not root.handlers:
        configure_logging(verbose=False)
    if name == ROOT_LOGGER_NAME or name.startswith(f"{ROOT_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


@dataclass
class StepTimer:
    logger: logging.Logger
    label: str
    _start: float = field(default=0.0, init=False)

    def __enter__(self) -> StepTimer:
        self._start = time.perf_counter()
        self.logger.info("Starting: %s", self.label)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        elapsed = time.perf_counter() - self._start
        if exc_type is None:
            self.logger.info("Finished: %s (%s)", self.label, format_duration(elapsed))
        else:
            self.logger.error(
                "Failed: %s (%s) — %s",
                self.label,
                format_duration(elapsed),
                exc,
            )
        return False


@dataclass
class BuildTimer:
    logger: logging.Logger
    steps: list[tuple[str, float]] = field(default_factory=list)
    _overall_start: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._overall_start = time.perf_counter()

    @contextmanager
    def step(self, label: str):
        start = time.perf_counter()
        self.logger.info("Starting: %s", label)
        try:
            yield
        except Exception:
            elapsed = time.perf_counter() - start
            self.steps.append((label, elapsed))
            self.logger.error("Failed: %s (%s)", label, format_duration(elapsed))
            raise
        else:
            elapsed = time.perf_counter() - start
            self.steps.append((label, elapsed))
            self.logger.info("Finished: %s (%s)", label, format_duration(elapsed))

    def log_summary(self, title: str = "Timing summary") -> float:
        total = time.perf_counter() - self._overall_start
        self.logger.info("--- %s ---", title)
        for label, elapsed in self.steps:
            share = (elapsed / total * 100) if total else 0.0
            self.logger.info("  %-28s %8s  (%4.0f%%)", label, format_duration(elapsed), share)
        self.logger.info("  %-28s %8s", "Total", format_duration(total))
        return total
