from util.cardmarket_prices import (
    _nonfoil_low_is_reliable,
    load_price_guide_index,
    parse_id_product,
)

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


def guide_prices_for_url(cardmarket_url: str | None) -> dict[str, float | None]:
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


def price_from_strategy(
    cardmarket_url: str | None,
    finish: int,
    strategy: str,
    *,
    market_value: float | None = None,
    market_value_foil: float | None = None,
    market_value_etched: float | None = None,
) -> float | None:
    normalized = normalize_strategy(strategy)
    if cardmarket_url:
        product_id = parse_id_product(cardmarket_url)
        if product_id is not None:
            entry = _load_guide().get(product_id)
            if entry:
                nonfoil_key, foil_key = STRATEGY_KEY_MAP[normalized]
                key = foil_key if int(finish) == 1 else nonfoil_key
                value = _value_from_entry(entry, key, foil=bool(int(finish) == 1))
                if value is not None:
                    return value
    if int(finish) == 2:
        return market_value_etched
    return market_value_foil if int(finish) == 1 else market_value


def _value_from_entry(entry: dict, key: str, *, foil: bool) -> float | None:
    value = entry.get(key)
    if value is None or value <= 0:
        return None
    if key in ("low", "low-foil") and not foil and not _nonfoil_low_is_reliable(entry, float(value)):
        return None
    return float(value)


def all_guide_prices_for_url(cardmarket_url: str | None) -> dict[str, dict]:
    prices = guide_prices_for_url(cardmarket_url)
    grouped = {"nonfoil": {}, "foil": {}, "etched": {}}
    for strategy in STRATEGY_KEY_MAP:
        grouped["nonfoil"][strategy] = prices.get(f"{strategy}_nonfoil")
        grouped["foil"][strategy] = prices.get(f"{strategy}_foil")
        grouped["etched"][strategy] = prices.get(f"{strategy}_nonfoil")
    return grouped
