from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, GUIDE_PRICE_GROUPS, is_etched_only_print
from util.cardmarket_prices import (
    _nonfoil_low_is_reliable,
    load_price_guide_index,
    parse_id_product,
)
from util.cardmarket_urls import cardmarket_url_for_finish, coerce_cardmarket_url, normalize_cardmarket_url_columns

PRICE_STRATEGIES: list[dict[str, str]] = [
    {"id": "trend", "label": "Trend"},
    {"id": "avg", "label": "Average"},
    {"id": "avg7", "label": "Avg 7 days"},
    {"id": "avg30", "label": "Avg 30 days"},
    {"id": "avg1", "label": "Avg 1 day"},
    {"id": "low", "label": "Low"},
]

STRATEGY_KEY_MAP = {
    "trend": ("trend", "trend-foil"),
    "avg": ("avg", "avg-foil"),
    "avg7": ("avg7", "avg7-foil"),
    "avg30": ("avg30", "avg30-foil"),
    "avg1": ("avg1", "avg1-foil"),
    "low": ("low", "low-foil"),
}

_guide_index: dict[int, dict] | None = None


def list_price_strategies() -> list[dict[str, str]]:
    return list(PRICE_STRATEGIES)


def normalize_strategy(strategy: str | None) -> str:
    normalized = (strategy or "trend").strip().lower()
    if normalized not in STRATEGY_KEY_MAP:
        return "trend"
    return normalized


def _load_guide() -> dict[int, dict]:
    global _guide_index
    if _guide_index is None:
        _guide_index = load_price_guide_index()
    return _guide_index


def refresh_guide_cache() -> None:
    global _guide_index
    _guide_index = None


def _cardmarket_row(
    cardmarket_url: str | None,
    cardmarket_url_foil: str | None = None,
) -> dict[str, str | None]:
    return {
        "cardmarket_url": cardmarket_url,
        "cardmarket_url_foil": cardmarket_url_foil,
    }


def guide_prices_for_url(cardmarket_url: str | None) -> dict[str, float | None]:
    cardmarket_url = coerce_cardmarket_url(cardmarket_url)
    if not cardmarket_url:
        return {}
    product_id = parse_id_product(cardmarket_url)
    if product_id is None:
        return {}
    entry = _load_guide().get(product_id)
    if not entry:
        return {}
    result: dict[str, float | None] = {}
    for strategy_id, (nonfoil_key, foil_key) in STRATEGY_KEY_MAP.items():
        result[f"{strategy_id}_nonfoil"] = _value_from_entry(entry, nonfoil_key, foil=False)
        result[f"{strategy_id}_foil"] = _value_from_entry(entry, foil_key, foil=True)
    return result


def all_guide_prices_for_card(
    cardmarket_url: str | None,
    cardmarket_url_foil: str | None = None,
) -> dict[str, dict]:
    cardmarket_url = coerce_cardmarket_url(cardmarket_url)
    cardmarket_url_foil = coerce_cardmarket_url(cardmarket_url_foil)
    guide = _load_guide()
    cardmarket_url, cardmarket_url_foil = normalize_cardmarket_url_columns(
        cardmarket_url,
        cardmarket_url_foil,
        guide,
    )
    nonfoil_prices = guide_prices_for_url(cardmarket_url)
    foil_lookup_url = cardmarket_url_foil
    if not foil_lookup_url and cardmarket_url:
        foil_lookup_url = cardmarket_url_for_finish(
            _cardmarket_row(cardmarket_url, cardmarket_url_foil),
            FINISH_FOIL,
            _load_guide(),
        )
    foil_prices = guide_prices_for_url(foil_lookup_url)
    grouped = {"nonfoil": {}, "foil": {}, "etched": {}}
    for strategy in STRATEGY_KEY_MAP:
        grouped["nonfoil"][strategy] = nonfoil_prices.get(f"{strategy}_nonfoil")
        foil_value = foil_prices.get(f"{strategy}_foil")
        if foil_value is None:
            foil_value = nonfoil_prices.get(f"{strategy}_foil")
        grouped["foil"][strategy] = foil_value
    return grouped


def all_guide_prices_for_url(cardmarket_url: str | None) -> dict[str, dict]:
    return all_guide_prices_for_card(cardmarket_url)


def price_from_strategy(
    cardmarket_url: str | None,
    finish: int,
    strategy: str,
    *,
    cardmarket_url_foil: str | None = None,
    market_value: float | None = None,
    market_value_foil: float | None = None,
    market_value_etched: float | None = None,
) -> float | None:
    values = values_by_strategy_for_finish(
        {
            "cardmarket_url": cardmarket_url,
            "cardmarket_url_foil": cardmarket_url_foil,
            "market_value": market_value,
            "market_value_foil": market_value_foil,
            "market_value_etched": market_value_etched,
        },
        finish,
    )
    return value_from_strategy_map(
        values,
        strategy,
        finish=finish,
        market_value=market_value,
        market_value_foil=market_value_foil,
        market_value_etched=market_value_etched,
    )


def values_by_strategy_for_finish(card: dict, finish: int) -> dict[str, float | None]:
    finish_id = int(finish)
    if finish_id == FINISH_ETCHED:
        etched = card.get("market_value_etched") or card.get("marketValueEtched")
        if etched is not None and not (isinstance(etched, float) and etched != etched):
            etched_value = float(etched) if etched else None
            return {strategy_id: etched_value for strategy_id in STRATEGY_KEY_MAP}

        guide_prices = all_guide_prices_for_card(
            coerce_cardmarket_url(card.get("cardmarket_url") or card.get("cardmarketUrl")),
            coerce_cardmarket_url(card.get("cardmarket_url_foil") or card.get("cardmarketUrlFoil")),
        )
        if is_etched_only_print(card):
            strategy_values = dict(guide_prices.get("foil", {}))
        else:
            strategy_values = dict(guide_prices.get("etched", {}))
        if any(value is not None for value in strategy_values.values()):
            return strategy_values
        return {strategy_id: None for strategy_id in STRATEGY_KEY_MAP}

    guide_prices = all_guide_prices_for_card(
        coerce_cardmarket_url(card.get("cardmarket_url") or card.get("cardmarketUrl")),
        coerce_cardmarket_url(card.get("cardmarket_url_foil") or card.get("cardmarketUrlFoil")),
    )
    group = GUIDE_PRICE_GROUPS.get(finish_id, "nonfoil")
    strategy_values = dict(guide_prices.get(group, {}))

    market_value = card.get("market_value") if card.get("market_value") is not None else card.get("marketValue")
    market_value_foil = (
        card.get("market_value_foil")
        if card.get("market_value_foil") is not None
        else card.get("marketValueFoil")
    )
    fallback = market_value_foil if finish_id == FINISH_FOIL else market_value

    for strategy_id in STRATEGY_KEY_MAP:
        if strategy_values.get(strategy_id) is None and fallback is not None:
            strategy_values[strategy_id] = float(fallback) if fallback else None

    return strategy_values


def value_from_strategy_map(
    values_by_strategy: dict[str, float | None],
    strategy: str,
    *,
    finish: int,
    market_value: float | None = None,
    market_value_foil: float | None = None,
    market_value_etched: float | None = None,
) -> float | None:
    normalized = normalize_strategy(strategy)
    value = values_by_strategy.get(normalized)
    if value is not None:
        return value
    finish_id = int(finish)
    if finish_id == FINISH_ETCHED:
        return market_value_etched
    return market_value_foil if finish_id == FINISH_FOIL else market_value


def _value_from_entry(entry: dict, key: str, *, foil: bool) -> float | None:
    value = entry.get(key)
    if value is None or value <= 0:
        return None
    if key in ("low", "low-foil") and not foil and not _nonfoil_low_is_reliable(entry, float(value)):
        return None
    return float(value)
