import numpy as np
import pandas as pd

from api.services.pricing_service import (
    STRATEGY_KEY_MAP,
    normalize_strategy,
    price_from_strategy,
    value_from_strategy_map,
    values_by_strategy_for_finish,
)
from util.card_finishes import (
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    infer_finish_for_print,
    resolve_valuation_finish,
)
from util.cardmarket_urls import coerce_cardmarket_url

_FINISH_IDS = (FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED)
_STRATEGY_IDS = tuple(STRATEGY_KEY_MAP.keys())


def _price_column(finish_id: int, strategy_id: str) -> str:
    return f"price_{finish_id}_{strategy_id}"


def _has_price_columns(df: pd.DataFrame, strategy: str) -> bool:
    normalized = normalize_strategy(strategy)
    return _price_column(FINISH_NONFOIL, normalized) in df.columns


def _price_row_for_finish(row, finish: int, strategy: str) -> float | None:
    return price_from_strategy(
        coerce_cardmarket_url(row.get("cardmarket_url")),
        finish,
        strategy,
        cardmarket_url_foil=coerce_cardmarket_url(row.get("cardmarket_url_foil")),
        market_value=_nullable_float(row.get("market_value")),
        market_value_foil=_nullable_float(row.get("market_value_foil")),
        market_value_etched=_nullable_float(row.get("market_value_etched")),
    )


def _values_by_finish_for_row(row) -> dict[int, dict[str, float | None]]:
    row_dict = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    return {
        finish_id: values_by_strategy_for_finish(row_dict, finish_id)
        for finish_id in _FINISH_IDS
    }


def build_neutral_owned_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    neutral = df.drop(columns=["current_value", "profit_loss"], errors="ignore").copy()
    values_by_finish: list[dict[int, dict[str, float | None]]] = []
    price_columns = {
        _price_column(finish_id, strategy_id): []
        for finish_id in _FINISH_IDS
        for strategy_id in _STRATEGY_IDS
    }

    for _, row in neutral.iterrows():
        by_finish = _values_by_finish_for_row(row)
        values_by_finish.append(by_finish)
        for finish_id in _FINISH_IDS:
            strategy_values = by_finish.get(finish_id, {})
            for strategy_id in _STRATEGY_IDS:
                price_columns[_price_column(finish_id, strategy_id)].append(
                    strategy_values.get(strategy_id),
                )

    neutral["values_by_finish"] = values_by_finish
    for column, values in price_columns.items():
        neutral[column] = values
    return neutral


def _value_from_finish_map(
    row,
    by_finish: dict,
    finish_id: int,
    strategy: str,
) -> float | None:
    values = by_finish.get(finish_id) or by_finish.get(int(finish_id)) or {}
    return value_from_strategy_map(
        values,
        strategy,
        finish=finish_id,
        market_value=_nullable_float(row.get("market_value")),
        market_value_foil=_nullable_float(row.get("market_value_foil")),
        market_value_etched=_nullable_float(row.get("market_value_etched")),
    )


def _resolve_valuation_finish_array(
    stored: np.ndarray,
    has_nonfoil: np.ndarray,
    has_foil: np.ndarray,
    has_etched: np.ndarray,
    prices: np.ndarray,
) -> np.ndarray:
    row_count = len(stored)
    valuation = stored.copy()
    row_indexes = np.arange(row_count)
    stored_prices = prices[row_indexes, stored]
    stored_has_price = ~np.isnan(stored_prices)

    for index in np.where(~stored_has_price)[0]:
        inferred = infer_finish_for_print(
            int(stored[index]),
            has_nonfoil=int(has_nonfoil[index]),
            has_foil=int(has_foil[index]),
            has_etched=int(has_etched[index]),
        )
        if inferred != stored[index] and not np.isnan(prices[index, inferred]):
            valuation[index] = inferred
        else:
            valuation[index] = stored[index]

    valuation = np.where(stored_has_price, stored, valuation)
    return valuation.astype(int)


def _apply_strategy_from_price_columns(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    normalized = normalize_strategy(strategy)
    row_count = len(df)
    if row_count == 0:
        return df.copy()

    stored = df["finish"].fillna(0).astype(int).to_numpy()
    has_nonfoil = df["has_nonfoil"].fillna(0).astype(int).to_numpy()
    has_foil = df["has_foil"].fillna(0).astype(int).to_numpy()
    has_etched = df["has_etched"].fillna(0).astype(int).to_numpy()

    price_matrix = np.column_stack([
        pd.to_numeric(df[_price_column(finish_id, normalized)], errors="coerce").to_numpy(dtype=float)
        for finish_id in _FINISH_IDS
    ])
    valuation = _resolve_valuation_finish_array(
        stored,
        has_nonfoil,
        has_foil,
        has_etched,
        price_matrix,
    )
    current = price_matrix[np.arange(row_count), valuation]

    updated = df.copy()
    updated["current_value"] = [
        None if value is None or np.isnan(value) else float(value)
        for value in current
    ]
    purchase = pd.to_numeric(df["purchase_value"], errors="coerce").to_numpy(dtype=float)
    profit_values = []
    for index, value in enumerate(current):
        purchase_value = purchase[index]
        if (
            value is None
            or np.isnan(value)
            or purchase_value is None
            or np.isnan(purchase_value)
            or purchase_value == 0
        ):
            profit_values.append(None)
        else:
            profit_values.append(float(value) - float(purchase_value))
    updated["profit_loss"] = profit_values
    return updated


def _apply_strategy_from_values_by_finish(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    updated = df.copy()
    for idx, row in updated.iterrows():
        by_finish = row["values_by_finish"]
        stored_finish = int(row["finish"]) if pd.notna(row.get("finish")) else 0
        valuation_finish = resolve_valuation_finish(
            row,
            stored_finish,
            price_lookup=lambda finish_id: _value_from_finish_map(
                row,
                by_finish,
                finish_id,
                strategy,
            ),
        )
        current = _value_from_finish_map(row, by_finish, valuation_finish, strategy)
        updated.at[idx, "current_value"] = current
        purchase = row.get("purchase_value")
        if purchase is not None and not pd.isna(purchase) and current is not None:
            updated.at[idx, "profit_loss"] = current - float(purchase)
        else:
            updated.at[idx, "profit_loss"] = None
    return updated


def apply_strategy_to_neutral_owned_df(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    if _has_price_columns(df, strategy):
        return _apply_strategy_from_price_columns(df, strategy)

    if "values_by_finish" in df.columns:
        return _apply_strategy_from_values_by_finish(df, strategy)

    return apply_strategy_to_owned_df(df, strategy)


def apply_strategy_to_owned_df(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    updated = df.copy()
    for idx, row in updated.iterrows():
        stored_finish = int(row["finish"]) if pd.notna(row.get("finish")) else 0
        valuation_finish = resolve_valuation_finish(
            row,
            stored_finish,
            price_lookup=lambda finish_id: _price_row_for_finish(row, finish_id, strategy),
        )
        current = _price_row_for_finish(row, valuation_finish, strategy)
        updated.at[idx, "current_value"] = current
        purchase = row.get("purchase_value")
        if purchase is not None and not pd.isna(purchase) and current is not None:
            updated.at[idx, "profit_loss"] = current - float(purchase)
        else:
            updated.at[idx, "profit_loss"] = None
    return updated


def apply_strategy_to_deck_df(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    updated = df.copy()
    in_catalog = updated["in_catalog"].fillna(0).astype(int) == 1
    for idx in updated.index:
        if not in_catalog.loc[idx]:
            continue
        row = updated.loc[idx]
        finish = int(row["finish"]) if pd.notna(row.get("finish")) else 0
        unit = price_from_strategy(
            coerce_cardmarket_url(row.get("cardmarket_url")),
            finish,
            strategy,
            cardmarket_url_foil=coerce_cardmarket_url(row.get("cardmarket_url_foil")),
            market_value=_nullable_float(row.get("market_value")),
            market_value_foil=_nullable_float(row.get("market_value_foil")),
            market_value_etched=_nullable_float(row.get("market_value_etched")),
        )
        qty = int(row["qty"])
        owned_qty = int(row["owned_qty"])
        updated.at[idx, "unit_value"] = unit
        if unit is None:
            updated.at[idx, "current_value"] = None
            updated.at[idx, "profit_loss"] = None
            continue
        current_value = unit * qty
        updated.at[idx, "current_value"] = current_value
        purchase = row.get("purchase_value")
        if purchase is not None and not pd.isna(purchase) and owned_qty > 0:
            invested = float(purchase) * owned_qty
            updated.at[idx, "invested"] = invested
            updated.at[idx, "profit_loss"] = current_value - invested
        else:
            updated.at[idx, "profit_loss"] = None
    return updated


def _nullable_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
