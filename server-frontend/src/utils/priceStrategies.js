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
