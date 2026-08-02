const PRICE_STRATEGY_DESCRIPTIONS = {
  trend: "Cardmarket trend price — estimated fair value based on recent marketplace activity.",
  avg: "Average sale price across all tracked Cardmarket sales.",
  avg7: "Average sale price over the last 7 days.",
  avg30: "Average sale price over the last 30 days.",
  avg1: "Average sale price over the last 24 hours.",
  low: "Lowest current listing. Non-foil low is shown only when Cardmarket marks it reliable.",
};

export const LOWEST_STRATEGY_ID = "low";

export function priceStrategyDescription(strategyId) {
  return PRICE_STRATEGY_DESCRIPTIONS[strategyId] || "";
}

export function valueForStrategy(card, strategyId) {
  if (!card) {
    return null;
  }
  const values = card.valuesByStrategy ?? card.values_by_strategy;
  if (!values || typeof values !== "object") {
    return null;
  }
  if (!(strategyId in values)) {
    return null;
  }
  const value = values[strategyId];
  return value == null ? null : value;
}

function numericStrategyEntries(card) {
  const values = card?.valuesByStrategy ?? card?.values_by_strategy;
  if (!values || typeof values !== "object") {
    return [];
  }
  const entries = [];
  for (const [id, value] of Object.entries(values)) {
    if (value == null || Number.isNaN(Number(value))) {
      continue;
    }
    entries.push({ id, value: Number(value) });
  }
  return entries;
}

/**
 * Gallery price pair: lowest listing first, then the highest of the other strategies.
 * If lowest is missing, or it is already the highest value, secondary is null (single number).
 */
export function galleryPricePair(card) {
  const entries = numericStrategyEntries(card);
  if (!entries.length) {
    const fallback = card?.currentValue ?? card?.current_value ?? null;
    if (fallback == null || Number.isNaN(Number(fallback))) {
      return { low: null, high: null };
    }
    const n = Number(fallback);
    return { low: n, high: null };
  }

  const lowestEntry = entries.find((entry) => entry.id === LOWEST_STRATEGY_ID);
  const others = entries.filter((entry) => entry.id !== LOWEST_STRATEGY_ID);
  const otherHigh = others.length
    ? Math.max(...others.map((entry) => entry.value))
    : null;

  if (lowestEntry == null) {
    return { low: otherHigh, high: null };
  }

  const lowest = lowestEntry.value;
  if (otherHigh == null || lowest >= otherHigh) {
    return { low: lowest, high: null };
  }
  return { low: lowest, high: otherHigh };
}

/** Single number for totals/sorting: secondary (high) when shown, else the lone displayed value. */
export function galleryDisplayValue(card) {
  const { low, high } = galleryPricePair(card);
  return high ?? low;
}

export function applyStrategyToCard(card, strategyId) {
  if (!card) {
    return card;
  }
  const currentValue = valueForStrategy(card, strategyId);
  const purchaseValue = card.purchaseValue ?? card.purchase_value ?? null;
  let profitLoss = card.profitLoss ?? card.profit_loss ?? null;
  if (purchaseValue != null && purchaseValue !== 0 && currentValue != null) {
    profitLoss = currentValue - purchaseValue;
  }
  const previousValue = card.previousValue ?? card.previous_value ?? null;
  let priceChange = card.priceChange ?? card.price_change ?? null;
  if (currentValue != null && previousValue != null) {
    priceChange = currentValue - previousValue;
  }
  return {
    ...card,
    currentValue,
    profitLoss,
    priceChange,
  };
}

export function applyStrategyToCards(cards, strategyId) {
  return (cards || []).map((card) => applyStrategyToCard(card, strategyId));
}

/** Apply gallery display value (range high side) as currentValue for totals/sorting. */
export function applyGalleryDisplayToCard(card) {
  if (!card) {
    return card;
  }
  const currentValue = galleryDisplayValue(card);
  const purchaseValue = card.purchaseValue ?? card.purchase_value ?? null;
  let profitLoss = card.profitLoss ?? card.profit_loss ?? null;
  if (purchaseValue != null && purchaseValue !== 0 && currentValue != null) {
    profitLoss = currentValue - purchaseValue;
  }
  const previousValue = card.previousValue ?? card.previous_value ?? null;
  let priceChange = card.priceChange ?? card.price_change ?? null;
  if (currentValue != null && previousValue != null) {
    priceChange = currentValue - previousValue;
  }
  return {
    ...card,
    currentValue,
    profitLoss,
    priceChange,
  };
}

export function applyGalleryDisplayToCards(cards) {
  return (cards || []).map((card) => applyGalleryDisplayToCard(card));
}

export function hasStrategyPrices(card) {
  const values = card?.valuesByStrategy ?? card?.values_by_strategy;
  if (!values || typeof values !== "object") {
    return false;
  }
  return Object.values(values).some((value) => value != null);
}

/** Min/max across strategy prices; nulls when none are available. */
export function strategyPriceBounds(card) {
  const entries = numericStrategyEntries(card);
  if (!entries.length) {
    return { low: null, high: null };
  }
  const nums = entries.map((entry) => entry.value);
  return { low: Math.min(...nums), high: Math.max(...nums) };
}

export function strategyPriceRows(card, strategies, activeStrategyId) {
  return (strategies || []).map((strategy) => ({
    id: strategy.id,
    label: strategy.label,
    description: priceStrategyDescription(strategy.id),
    value: valueForStrategy(card, strategy.id),
    isActive: strategy.id === activeStrategyId,
  }));
}
