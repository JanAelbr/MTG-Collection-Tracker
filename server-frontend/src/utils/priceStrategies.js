const PRICE_STRATEGY_DESCRIPTIONS = {
  trend: "Cardmarket trend price — estimated fair value based on recent marketplace activity.",
  avg: "Average sale price across all tracked Cardmarket sales.",
  avg7: "Average sale price over the last 7 days.",
  avg30: "Average sale price over the last 30 days.",
  avg1: "Average sale price over the last 24 hours.",
  low: "Lowest current listing. Non-foil low is shown only when Cardmarket marks it reliable.",
};

export function priceStrategyDescription(strategyId) {
  return PRICE_STRATEGY_DESCRIPTIONS[strategyId] || "";
}

export function valueForStrategy(card, strategyId) {
  if (!card) {
    return null;
  }
  const values = card.valuesByStrategy;
  if (values && strategyId in values && values[strategyId] != null) {
    return values[strategyId];
  }
  return card.currentValue ?? card.current_value ?? null;
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

export function hasStrategyPrices(card) {
  const values = card?.valuesByStrategy;
  if (!values || typeof values !== "object") {
    return false;
  }
  return Object.values(values).some((value) => value != null);
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
