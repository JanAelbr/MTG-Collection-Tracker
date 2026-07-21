import { describe, expect, it } from "vitest";
import {
  applyStrategyToCard,
  hasStrategyPrices,
  strategyPriceRows,
  valueForStrategy,
} from "./priceStrategies.js";

describe("priceStrategies", () => {
  const card = {
    currentValue: 1.5,
    valuesByStrategy: {
      trend: 1.5,
      avg: 1.8,
      low: 1.2,
    },
  };

  it("reads strategy-specific values without currentValue fallback", () => {
    expect(valueForStrategy(card, "avg")).toBe(1.8);
    expect(valueForStrategy(card, "missing")).toBeNull();
    expect(valueForStrategy({ currentValue: 1.5 }, "trend")).toBeNull();
  });

  it("detects strategy price maps", () => {
    expect(hasStrategyPrices(card)).toBe(true);
    expect(hasStrategyPrices({ currentValue: 1 })).toBe(false);
  });

  it("builds tooltip rows with active strategy", () => {
    const rows = strategyPriceRows(
      card,
      [
        { id: "trend", label: "Trend" },
        { id: "avg", label: "Avg" },
      ],
      "avg",
    );
    expect(rows).toHaveLength(2);
    expect(rows[1].isActive).toBe(true);
    expect(rows[1].value).toBe(1.8);
  });

  it("recomputes profit when switching strategy", () => {
    const next = applyStrategyToCard(
      { ...card, purchaseValue: 1.0, profitLoss: 0.5, previousValue: 1.4 },
      "low",
    );
    expect(next.currentValue).toBe(1.2);
    expect(next.profitLoss).toBeCloseTo(0.2);
    expect(next.priceChange).toBeCloseTo(-0.2);
  });
});
