"""Reset the database and fetch the latest prices.

Usage:
    python scripts/reset_and_build.py
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import path_setup  # noqa: F401

from lib.config import (
    CREATE_DB_SCRIPT,
    DB_PATH,
    REPO_ROOT,
    UPDATE_PRICES_SCRIPT,
)
from lib.run_log import BuildTimer, configure_logging, get_logger

log = get_logger(__name__)


# Delete the existing SQLite database file when present.
def remove_db() -> None:
    if not DB_PATH.exists():
        log.info("No existing database found, continuing")
        return
    log.info("Removing existing database: %s", DB_PATH)
    DB_PATH.unlink()


# Run another project script as a subprocess from the repo root.
def run_script(script_path, label: str, *, extra_args: list[str] | None = None) -> None:
    command = [sys.executable, str(script_path), *(extra_args or [])]
    log.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True, cwd=str(REPO_ROOT))


# Recreate the database and fetch prices.
def main() -> None:
    parser = argparse.ArgumentParser(description="Reset database and rebuild collection data.")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress logging.",
    )
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)

    timer = BuildTimer(log)
    script_args = ["--verbose"] if args.verbose else []

    log.info("Starting full reset and build")
    with timer.step("Remove database"):
        remove_db()
    with timer.step("Create database"):
        run_script(CREATE_DB_SCRIPT, f"Creating database via {CREATE_DB_SCRIPT.name}")
    with timer.step("Update prices"):
        run_script(UPDATE_PRICES_SCRIPT, "Fetching prices (update_prices.py)", extra_args=script_args)
    timer.log_summary("Reset and build timing")
    log.info("Reset and build complete")


if __name__ == "__main__":
    main()
