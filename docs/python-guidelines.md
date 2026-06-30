# Python Guidelines — MTG Collection Tracker

These guidelines describe how we want Python code in this repo to look and behave.
They are based on the current codebase and the inconsistencies we want to remove over time.

**Target:** Python 3.10+  
**Scope:** `scripts/`, `scripts/lib/`, `scripts/report/`, `scripts/db/`, `scripts/util/`, `server-backend/api/`

---

## Goals

1. Scripts should work regardless of the current working directory.
2. Shared logic lives in importable modules; scripts stay thin.
3. One obvious way to run each workflow.
4. Failures are visible; silent data corruption is avoided.
5. User-facing text is English; code stays English.

---

## Project layout

```
lotr/
├── collection.db          # runtime database (not committed)
├── data/                  # per-set CSVs, artStyles JSON, decks/
├── docs/                  # project documentation (decks.md, python-guidelines.md)
├── logs/                  # price fetch logs
├── reports/               # generated HTML output
├── server-backend/        # FastAPI app (api/, run_api.py)
├── server-frontend/       # Vue app (Vite)
├── scripts/               # batch workflows + shared lib/report/util
│   ├── reset_and_build.py
│   ├── sync_collection.py
│   ├── purchase_import.py
│   ├── deck_import.py
│   ├── deck_sync.py
│   ├── update_prices.py
│   ├── update_prices_report.py
│   ├── generate_report.py
│   ├── build_catalog_decks.py
│   ├── build_deck_csv.py
│   ├── db/
│   │   └── create_db.py
│   ├── lib/
│   │   ├── config.py
│   │   ├── deck_csv.py
│   │   ├── deck_loader.py
│   │   ├── deck_purchase.py
│   │   ├── deck_scryfall.py
│   │   ├── deck_wiki.py
│   │   ├── purchase_csv.py
│   │   ├── purchase_loader.py
│   │   ├── collection_sync.py
│   │   └── run_log.py
│   ├── report/
│   │   ├── deck_queries.py
│   │   ├── deck_stats_data.py
│   │   ├── report_data.py
│   │   └── ...
│   └── util/
│       ├── deck_tables.py
│       ├── cardmarket_prices.py
│       └── ...
└── templates/             # report HTML/CSS/JS sources
```

### Rules

- Put **runnable workflows** in top-level `scripts/*.py` (and `scripts/db/create_db.py`).
- Put **HTTP API routes and services** in `server-backend/api/`.
- Put **shared configuration and import logic** in `scripts/lib/`.
- Put **report generation modules** in `scripts/report/`.
- Put **low-level helpers** in `scripts/util/`.
- Avoid duplicating the same workflow in multiple scripts.

---

## Paths and configuration

### Shared config

Path constants live in `scripts/lib/config.py`. Import from there instead of redefining paths:

```python
from lib.config import DB_PATH, DATA_DIR, DECKS_DIR, REPO_ROOT, list_set_csv_files
```

Deck paths and manifest: `DECKS_DIR`, `DECKS_MANIFEST_NAME` (`decks.csv`). See `docs/decks.md`.

### Do

Use `lib.config` for all repo paths:

```python
from lib.config import DB_PATH, DATA_DIR, TEMPLATES_DIR
```

Prefer `pathlib.Path` over string paths. Build absolute paths from `config`, not from `cwd`.

### Don't

```python
# Bad — breaks when cwd is not the repo root
conn = sqlite3.connect("collection.db")
csv_path = "data/ltr.csv"
```

Scripts in `scripts/db/` and `scripts/util/` add the scripts directory to `sys.path` before importing `lib.config`.

---

## Imports

### Order

1. Standard library  
2. Third-party packages  
3. Local project modules  

Blank line between each group.

```python
import csv
import sqlite3
from pathlib import Path

import pandas as pd
import requests

from lib.config import DATA_DIR, DB_PATH, REPO_ROOT
from util.formatting import euro
from report.report_data import load_collection_data
```

### Rules

- Use explicit imports (`from util.formatting import euro`), not `import *`.
- Keep sibling imports working when scripts are run as `python scripts/foo.py` from repo root.
- Long term, prefer `python -m scripts.foo` with a proper package layout; until then, stay consistent with the existing run style documented in `readme.md`.

---

## Script entry points

Every runnable script should follow this shape:

```python
def main() -> None:
    ...

if __name__ == "__main__":
    main()
```

### Rules

- No side effects at import time (no DB writes, no `print()` at module level).
- Expose reusable functions; call them from `main()` or from other modules.
- Put usage in a module docstring or `--help` via `argparse` for user-facing scripts.

### Orchestration

Pick one composition style per pipeline:

| Style | When to use |
|-------|-------------|
| Direct function calls | Same process, shared state, easier debugging |
| `subprocess.run(..., check=True)` | Isolated steps, separate failure boundaries |

`reset_and_build.py` currently subprocesses child scripts. New code should either follow that pattern or we migrate the orchestrator to direct imports — not both.

---

## Database access

### Do

```python
def fetch_cards(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT ...", conn)

def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        ...
        conn.commit()
    finally:
        conn.close()
```

Or use a context manager:

```python
with sqlite3.connect(DB_PATH) as conn:
    ...
```

### Rules

- Open/close connections in one place; don't leak connections across modules.
- Keep SQL in the module that owns the domain (`report_data.py` for reads, `update_prices.py` for price writes).
- Use parameterized queries (`?` placeholders). Never interpolate user or file data into SQL strings.
- Prefer one read layer (`report_data.py`) over copy-pasted queries.

### Schema changes

- Update `scripts/db/create_db.py` for fresh databases.
- Add incremental migrations in `scripts/util/` (e.g. `deck_tables.ensure_deck_cards_print_unique`) and call them from `ensure_*` helpers so existing `collection.db` files upgrade in place.
- Document breaking changes in commit messages.

### Deck and purchase domains

| Module | Responsibility |
|--------|----------------|
| `lib/deck_csv.py` | Read/write deck CSVs and manifest; set sync set discovery |
| `lib/deck_loader.py` | Import deck rows into `deck_cards` |
| `lib/deck_purchase.py` | Allocate deck purchase price; upsert purchase rows |
| `lib/purchase_loader.py` | Import set CSVs + deck ownership (clears `purchases` first) |
| `lib/deck_scryfall.py` | Resolve deck card names to Scryfall prints (precon builders) |
| `util/deck_tables.py` | Create/migrate `decks` and `deck_cards` tables |

Deck import does **not** write purchases. Use `sync_collection.py` (decks + purchases), or `deck_sync.py` / `deck_import.py` followed by `purchase_import.py`. `generate_report.py` only builds HTML from the database.

---

## Data processing

### Pandas

- Use `pd.isna(x)` for missing values, not `x != x`.
- Keep SQL aggregation in SQLite where possible; use pandas for report shaping and display formatting.
- Avoid mutating DataFrames in hard-to-follow chains; name intermediate steps when logic is non-trivial.

### Money and display

- Keep raw numeric values numeric until the last formatting step.
- Use `util/formatting.py` for display (`euro()`). Don't duplicate currency formatting in multiple files.
- Handle `None`/NaN at formatting boundaries:

```python
def format_money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    return euro(value)
```

### Set codes and files

- Set codes in the DB: **uppercase** (`LTR`, `LTC`, `C13`).
- Purchase filenames in `data/`: **lowercase** (`ltr.csv`).
- Art-style filenames in `data/art_styles/`: **lowercase** (`ltr.json`).
- When discovering purchase sets, glob `data/*.csv` and exclude `purchases.csv` and `example.csv`.
- Deck print sets are discovered from `data/decks/*.csv` via `list_deck_sync_set_codes()`; `update_prices.get_set_codes()` unions purchase and deck sets.

---

## Error handling

### Do

- Fail fast on unexpected input with a clear message.
- Catch exceptions only when you can recover or add context.
- Log or print enough context to debug (set code, file path, row number).

### Don't

```python
except Exception:
    purchase_value = 0.0  # hides bad CSV data
```

For CSV parsing, prefer explicit validation:

```python
try:
    purchase_value = float(raw.replace(",", "."))
except ValueError as exc:
    raise ValueError(f"Invalid purchase_value in {path} row {row_num}: {raw!r}") from exc
```

### External APIs (Scryfall, Cardmarket, MTG Wiki)

- Route HTTP calls through `util.http_client.http_get` so every request is logged at INFO.
- Check HTTP status before parsing JSON.
- Respect rate limits (`time.sleep` between pages is fine).
- Surface API errors with response body snippet, not a generic "Fout".
- `update_prices.py` calls Scryfall only once per set, when that set is not yet stored in the local catalog. Cardmarket updates always cover owned cards; unowned catalog prices are synced only in sets where owned count ≥ min(25, 25% of set size), and cleared elsewhere.

---

## Logging and user output

CLI scripts use `lib/run_log.py`:

```python
from lib.run_log import configure_logging, get_logger

log = get_logger(__name__)

def main() -> None:
    configure_logging(verbose=False)
    log.info("Starting …")
```

- Pass `-v` / `--verbose` on user-facing scripts for debug detail.
- **English** for log messages and user-facing report labels.

---

## Types and docstrings

### Types

Use type hints on public functions:

```python
def generate_report(
    output_file: Path | str = OUTPUT_FILE_OWNED,
    owned_only: bool = True,
) -> list[Path]:
    ...
```

Run type checking once we add tooling (`pyright` or `mypy`).

### Docstrings

Use docstrings on modules and public functions. Keep them short and factual:

```python
def load_collection_data(owned_only: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load card and summary data from the database."""
```

Don't restate the type signature in the docstring.

### Function size

- Keep functions at **20 lines or fewer** (excluding blank lines is not enforced; aim for readable, single-purpose units).
- Prefer early returns over nested `if` blocks.
- Extract helpers or dataclasses when parameter lists or bodies grow.
- Move large SQL blocks to dedicated modules (see `report_queries.py`).

---

## SQL style

- Keywords in uppercase (`SELECT`, `FROM`, `WHERE`).
- One clause per line for non-trivial queries.
- Align duplicated query branches by extracting shared fragments instead of copying 80-line blocks.
- Name columns in snake_case to match pandas (`set_code`, `art_style`, `purchase_value`).

---

## Dependencies

Add a root `requirements.txt` (or `pyproject.toml`) and pin major versions:

```text
pandas>=3.0,<4
requests>=2.31,<3
```

Install into `.venv` and document setup in `readme.md`. Do not commit `.venv/`.

---

## Quality tooling (recommended next steps)

| Tool | Purpose |
|------|---------|
| `ruff` | Lint + import sort + some formatting |
| `ruff format` or `black` | Consistent formatting |
| `pyright` | Static type checking |
| `pytest` | Tests for CSV parsing, art-style mapping, report data |

Start with `ruff` on `scripts/` before chasing full test coverage.

---

## Review checklist

Before merging Python changes, check:

- [ ] Paths use `config`, not bare relative strings
- [ ] Script has `main()` and no import-time side effects
- [ ] DB connections are closed; transactions committed explicitly
- [ ] SQL is parameterized; no duplicated query blocks without reason
- [ ] Missing values handled with `pd.isna`, not `x != x`
- [ ] User-facing Dutch strings only in output/templates, not in identifiers
- [ ] Deck changes documented if CSV format or import behavior changes (`docs/decks.md`)
- [ ] Purchase import tested when changing ownership or allocation logic

---

## Suggested refactor order

Apply guidelines incrementally in this order:

1. ~~Add `scripts/lib/config.py` and migrate path constants.~~ Done — extend `lib/config.py` when new paths are needed.
2. ~~Add `requirements.txt` and align `readme.md` with actual commands/files.~~ Done.
3. Guard all `db/*.py` scripts with `main()`; stop running logic at import time.
4. ~~Consolidate purchase import into one module.~~ Done — use `purchase_import.py` + `lib/purchase_loader.py` (set CSVs + deck ownership).
5. ~~Add deck list import and deck reports.~~ Done — see `docs/decks.md`.
6. Deduplicate SQL in `report_data.py`.
7. Add `ruff` + `pyright`; fix the highest-signal issues first.
8. Extend pytest coverage for deck CSV parsing and report payloads.

Guidelines should evolve with the codebase — update this doc when we adopt a new convention.
