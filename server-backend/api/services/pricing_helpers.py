import pandas as pd

from api.services.pricing_service import price_from_strategy
from util.card_finishes import resolve_valuation_finish
from util.cardmarket_urls import coerce_cardmarket_url


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
