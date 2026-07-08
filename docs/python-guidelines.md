# Python Guidelines — MTG Collection Tracker

These guidelines describe how we want Python code in this repo to look and behave.
They are based on the current codebase and the inconsistencies we want to remove over time.

**Target:** Python 3.10+  
**Scope:** `scripts/` (CLI entrypoints), `server-backend/collection/` (`lib/`, `report/`, `util/`), `server-backend/api/`

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
├── collection.db          # runtime database (not committed; in APP_DATA_DIR)
├── data/                  # art_styles JSON, Cardmarket cache
├── docs/
├── server-backend/
│   ├── api/               # FastAPI routers + services
│   ├── collection/        # shared Python packages
│   │   ├── lib/           # config, art_styles, deck_purchase, run_log, …
│   │   ├── report/        # report_data, manager_data, deck queries, …
│   │   └── util/          # schema, tracked_sets, deck_tables, Cardmarket, …
│   └── run_api.py
├── server-frontend/
└── scripts/               # app launchers and frontend build helpers
    └── …
```

### Rules

- Put **HTTP API routes and services** in `server-backend/api/`.
- Put **shared configuration** in `server-backend/collection/lib/`.
- Put **shared data/query modules used by the API** in `server-backend/collection/report/`.
- Put **low-level helpers** (schema, migrations, external APIs) in `server-backend/collection/util/`.
- Import shared code via `from lib…`, `from report…`, `from util…` with `server-backend/collection` on `PYTHONPATH`.

---

## Paths and configuration

### Shared config

Path constants live in `server-backend/collection/lib/config.py`:

```python
from lib.config import DB_PATH, DATA_DIR, REPO_ROOT, ART_STYLES_DIR
```

`PYTHONPATH` includes `server-backend/collection` and `server-backend` (see `run_api.py` and PowerShell launchers).

### Do

Use `lib.config` for all repo paths:

```python
from lib.config import DB_PATH, DATA_DIR, ART_STYLES_DIR
```

Prefer `pathlib.Path` over string paths. Build absolute paths from `config`, not from `cwd`.

### Don't

```python
# Bad — breaks when cwd is not the repo root
conn = sqlite3.connect("collection.db")
rules_path = "data/art_styles/ltr.json"
```

Use `lib.config` for all repo paths. `run_api.py` adds `server-backend/collection` and `server-backend` to `sys.path` before imports.

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
| Direct function calls | Same process, shared state, easier debugging and tests |

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
- Keep SQL in the module that owns the domain (`report_data.py` for reads, `util/price_sync.py` and `util/cardmarket_prices.py` for price writes).
- Use parameterized queries (`?` placeholders). Never interpolate user or file data into SQL strings.
- Prefer one read layer (`report_data.py`) over copy-pasted queries.

### Schema changes

- Update `server-backend/collection/util/schema.py` for fresh databases and incremental upgrades.
- Add incremental migrations in `server-backend/collection/util/` (e.g. `deck_tables.ensure_deck_cards_print_unique`, `tracked_sets`) and call them from `ensure_*` helpers so existing `collection.db` files upgrade in place.
- Document breaking changes in commit messages.

### Deck and purchase domains

| Module | Responsibility |
|--------|----------------|
| `util/deck_tables.py` | Create/migrate `decks` and `deck_cards`; `list_deck_sync_set_codes(conn)` |
| `util/deck_helpers.py` | Resolve deck card rows against the catalog (`resolve_deck_row`) |
| `lib/deck_purchase.py` | `lookup_unit_market`, `upsert_purchase_value` for Set Manager |
| `util/tracked_sets.py` | Which sets are registered in Set Manager |
| `util/collection_backup.py` | Portable backup ZIP export/import |

Decks and ownership are edited via the API. Use **Settings → Backup & restore** to move data between installs.

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
- Art-style filenames in `data/art_styles/`: **lowercase** (`ltr.json`).
- Tracked sets come from `tracked_sets`; deck print sets from `deck_cards` via `list_deck_sync_set_codes(conn)`. `util.price_sync.get_set_codes()` unions both.

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
- `util/price_sync.py` calls Scryfall when Set Manager imports a catalog. Cardmarket updates always cover owned cards; unowned catalog prices are synced only in sets where owned count ≥ min(25, 25% of set size), and cleared elsewhere.

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
def load_collection_data(owned_only: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
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
- [ ] Deck or backup behavior changes documented in `docs/decks.md`
- [ ] Ownership / purchase logic tested when changing manager or storage APIs

---

## Suggested refactor order

Apply guidelines incrementally in this order:

1. ~~Add `scripts/lib/config.py` and migrate path constants.~~ Done — extend `lib/config.py` when new paths are needed.
2. ~~Add `requirements.txt` and align `readme.md` with actual commands/files.~~ Done.
3. Guard all `db/*.py` scripts with `main()`; stop running logic at import time.
4. ~~Move collection code under `server-backend/collection/`.~~ Done.
5. ~~SQLite-only decks and tracked sets (no CSV import).~~ Done — see `docs/decks.md` and `util/tracked_sets.py`.
6. Deduplicate SQL in `report_data.py`.
7. Add `ruff` + `pyright`; fix the highest-signal issues first.
8. Extend pytest coverage for backup restore and report payloads.

Guidelines should evolve with the codebase — update this doc when we adopt a new convention.
