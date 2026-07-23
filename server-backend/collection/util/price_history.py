import sqlite3

from dataclasses import dataclass

from datetime import date



import pandas as pd



from lib.config import DB_PATH

from util.card_finishes import card_price_key



SOURCE_RANK = {"cardmarket": 0, "scryfall": 1}





@dataclass(frozen=True)

class PriceSnapshotCache:

    dates: list[str]

    snapshots: dict[str, dict[str, float]]





# Return distinct snapshot dates in card_prices, newest first.

def get_price_snapshot_dates(conn: sqlite3.Connection) -> list[str]:

    rows = conn.execute(

        "SELECT DISTINCT price_date FROM card_prices ORDER BY price_date DESC"

    ).fetchall()

    return [row[0] for row in rows]





# Load one price snapshot, preferring Cardmarket over legacy Scryfall rows.

def load_snapshot_prices(conn: sqlite3.Connection, price_date: str) -> pd.DataFrame:

    df = pd.read_sql_query(

        """

        SELECT set_code, collector_number, finish, price, source

        FROM card_prices

        WHERE price_date = ?

        """,

        conn,

        params=(price_date,),

    )

    if df.empty:

        return df



    df["source_rank"] = df["source"].map(SOURCE_RANK).fillna(99)

    df = df.sort_values("source_rank").drop_duplicates(

        ["set_code", "collector_number", "finish"],

        keep="first",

    )

    return df[["set_code", "collector_number", "finish", "price"]].rename(

        columns={"price": "previous_value"},

    )





# Load all snapshot price maps once for repeated portfolio calculations.

_SNAPSHOT_CACHE_TTL = 300


def _database_identity(conn: sqlite3.Connection) -> str | None:
    """On-disk path for this connection, or None when not safely cacheable.

    ``:memory:`` / temp databases (used heavily in tests) get a distinct DB per
    connection but share the process-wide memory_cache, so caching them by
    epoch alone would leak results across unrelated databases.
    """
    row = conn.execute("PRAGMA database_list").fetchone()
    path = row[2] if row else ""
    return path if path else None


def load_price_snapshot_cache(conn: sqlite3.Connection) -> PriceSnapshotCache:
    """Cache the full per-date snapshot price maps by cache-epoch.

    This scans every row of every price_date snapshot, so without memoizing it
    every portfolio/history request re-reads the whole card_prices table.
    """
    db_path = _database_identity(conn)
    if db_path is None:
        return _load_price_snapshot_cache_uncached(conn)

    from api.cache import get_cache_epoch, memory_cache

    epoch = get_cache_epoch()
    cache_key = memory_cache.make_key("price_history.snapshot_cache", {"db": db_path}, epoch)
    cached = memory_cache.get(cache_key)
    if cached is not None:
        return cached

    result = _load_price_snapshot_cache_uncached(conn)
    memory_cache.set(cache_key, result, _SNAPSHOT_CACHE_TTL)
    return result


def _load_price_snapshot_cache_uncached(conn: sqlite3.Connection) -> PriceSnapshotCache:

    dates = get_price_snapshot_dates(conn)

    snapshots: dict[str, dict[str, float]] = {}

    for price_date in dates:

        snapshot_df = load_snapshot_prices(conn, price_date)

        if snapshot_df.empty:

            snapshots[price_date] = {}

            continue

        keys = (

            snapshot_df["set_code"].str.upper()

            + "|"

            + snapshot_df["collector_number"].astype(str)

            + "|"

            + snapshot_df["finish"].fillna(0).astype(int).astype(str)

        )

        snapshots[price_date] = dict(

            zip(keys, snapshot_df["previous_value"].astype(float), strict=False)

        )

    return PriceSnapshotCache(dates=dates, snapshots=snapshots)





# Return snapshot dates that can be used as a comparison baseline.

def get_compare_dates(dates: list[str]) -> list[str]:

    if len(dates) <= 1:

        return []

    return dates[1:]





# Return the default comparison date (previous snapshot).

def default_compare_date(dates: list[str]) -> str | None:

    compare_dates = get_compare_dates(dates)

    return compare_dates[0] if compare_dates else None






# Load compare metadata and the default snapshot map for card detail pages.

def load_card_detail_compare_context(

    conn: sqlite3.Connection,

) -> tuple[dict, dict[str, float]]:

    dates = get_price_snapshot_dates(conn)

    compare_dates = get_compare_dates(dates)

    default_compare = default_compare_date(dates)

    default_snapshot: dict[str, float] = {}



    if default_compare:

        price_df = load_snapshot_prices(conn, default_compare)

        if not price_df.empty:

            default_snapshot = {

                card_price_key(row.set_code, row.collector_number, row.finish): float(

                    row.previous_value,

                )

                for row in price_df.itertuples(index=False)

            }



    return {

        "compareDates": compare_dates,

        "currentDate": dates[0] if dates else None,

        "defaultCompareDate": default_compare,

    }, default_snapshot






def load_last_updated_display(conn: sqlite3.Connection | None = None) -> str:

    if conn is None:

        with sqlite3.connect(DB_PATH) as own_conn:

            dates = get_price_snapshot_dates(own_conn)

    else:

        dates = get_price_snapshot_dates(conn)

    return dates[0] if dates else "Unknown"





# True when the newest snapshot is missing or older than today.

def prices_are_outdated(

    conn: sqlite3.Connection | None = None,

    *,

    today: date | None = None,

) -> bool:

    last = load_last_updated_display(conn)

    if not last or last == "Unknown":

        return True

    try:

        last_date = date.fromisoformat(last)

    except ValueError:

        return True

    current = today or date.today()

    return last_date < current





def _float_or_none(value):

    if value is None or pd.isna(value):

        return None

    return float(value)





# Build total owned portfolio value for each snapshot date.

def compute_portfolio_history(

    conn: sqlite3.Connection,

    owned_df: pd.DataFrame,

    *,

    snapshot_cache: PriceSnapshotCache | None = None,

) -> list[dict]:

    if owned_df.empty:

        return []



    cache = snapshot_cache or load_price_snapshot_cache(conn)

    dates = cache.dates

    if not dates:

        return []



    owned_rows = []

    for _, row in owned_df.iterrows():

        owned_rows.append({

            "key": card_price_key(row["set_code"], row["collector_number"], row["finish"]),

            "current_value": row["current_value"],

        })



    invested = _float_or_none(owned_df["purchase_value"].sum(min_count=1))

    history: list[dict] = []



    for price_date in sorted(dates):

        price_map = cache.snapshots.get(price_date, {})



        total = 0.0

        has_value = False

        for card in owned_rows:

            if price_date == dates[0]:

                value = card["current_value"]

            else:

                value = price_map.get(card["key"])



            numeric_value = _float_or_none(value)

            if numeric_value is None:

                continue

            total += numeric_value

            has_value = True



        if not has_value:

            continue



        point = {"date": price_date, "value": round(total, 2)}

        if invested is not None:

            point["invested"] = round(invested, 2)

        history.append(point)



    return history


