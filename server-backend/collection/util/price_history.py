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

def load_price_snapshot_cache(conn: sqlite3.Connection) -> PriceSnapshotCache:

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





# Add previous_value, price_change, and previous_date for one snapshot date.

def enrich_with_compare_date(

    conn: sqlite3.Connection,

    cards_df: pd.DataFrame,

    compare_date: str,

) -> pd.DataFrame:

    enriched = cards_df.copy()

    previous_df = load_snapshot_prices(conn, compare_date)

    if previous_df.empty:

        enriched["previous_value"] = None

        enriched["price_change"] = None

        enriched["previous_date"] = compare_date

        return enriched



    enriched = enriched.merge(

        previous_df,

        on=["set_code", "collector_number", "finish"],

        how="left",

    )

    enriched["price_change"] = enriched.apply(

        lambda row: row["current_value"] - row["previous_value"]

        if pd.notna(row["current_value"]) and pd.notna(row["previous_value"])

        else None,

        axis=1,

    )

    enriched["previous_date"] = compare_date

    return enriched





# Add previous_value, price_change, and previous_date from the prior snapshot.

def enrich_with_previous_prices(

    conn: sqlite3.Connection,

    cards_df: pd.DataFrame,

) -> pd.DataFrame:

    dates = get_price_snapshot_dates(conn)

    compare_date = default_compare_date(dates)

    if not compare_date:

        enriched = cards_df.copy()

        enriched["previous_value"] = None

        enriched["price_change"] = None

        enriched["previous_date"] = None

        return enriched



    return enrich_with_compare_date(conn, cards_df, compare_date)





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





# Load compare dates and snapshot price maps for client-side reports.

def load_price_snapshot_payload(conn: sqlite3.Connection) -> dict:

    dates = get_price_snapshot_dates(conn)

    compare_dates = get_compare_dates(dates)

    snapshots: dict[str, dict[str, float]] = {}



    for compare_date in compare_dates:

        price_df = load_snapshot_prices(conn, compare_date)

        snapshots[compare_date] = {

            card_price_key(row["set_code"], row["collector_number"], row["finish"]): float(

                row["previous_value"],

            )

            for _, row in price_df.iterrows()

        }



    return {

        "compareDates": compare_dates,

        "currentDate": dates[0] if dates else None,

        "defaultCompareDate": default_compare_date(dates),

        "snapshots": snapshots,

    }





# Return the newest price snapshot date for display in reports.

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


