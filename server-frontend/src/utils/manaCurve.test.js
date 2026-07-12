import { describe, expect, it } from "vitest";
import {
  buildManaCurveChartData,
  cmcToBucket,
  filterCardsByManaBucket,
  IDEAL_MANA_CURVE_PERCENT,
  manaBucketLabel,
} from "./manaCurve.js";

describe("manaCurve helpers", () => {
  it("maps cmc values into curve buckets", () => {
    expect(cmcToBucket(1)).toBe(1);
    expect(cmcToBucket(6.5)).toBe(6);
    expect(cmcToBucket(7)).toBe(7);
    expect(cmcToBucket(12)).toBe(7);
  });

  it("builds actual and ideal bucket counts", () => {
    const chart = buildManaCurveChartData([
      { cardName: "Sol Ring", cmc: 1, qty: 1 },
      { cardName: "Rampant Growth", cmc: 2, qty: 1 },
      { cardName: "Cultivate", cmc: 3, qty: 1 },
      { cardName: "Craterhoof", cmc: 8, qty: 1 },
      { cardName: "Forest", cmc: 0, qty: 10 },
    ]);

    expect(chart.total).toBe(4);
    expect(chart.buckets.find((bucket) => bucket.id === 1)?.actual).toBe(1);
    expect(chart.buckets.find((bucket) => bucket.id === 2)?.actual).toBe(1);
    expect(chart.buckets.find((bucket) => bucket.id === 3)?.actual).toBe(1);
    expect(chart.buckets.find((bucket) => bucket.id === 7)?.actual).toBe(1);
    expect(chart.buckets.find((bucket) => bucket.id === 0)?.actual).toBe(0);
    expect(chart.averageCmc).toBe(3.5);
    expect(chart.buckets[0].idealPercent).toBe(Math.round(IDEAL_MANA_CURVE_PERCENT[0] * 100));
  });

  it("returns empty state when no resolvable cmc values exist", () => {
    const chart = buildManaCurveChartData([
      { cardName: "Unknown", cmc: 0, qty: 1 },
    ]);
    expect(chart.hasData).toBe(false);
    expect(chart.total).toBe(0);
  });

  it("filters cards by mana curve bucket", () => {
    const cards = [
      { cardName: "Sol Ring", cmc: 1, qty: 1 },
      { cardName: "Rampant Growth", cmc: 2, qty: 1 },
      { cardName: "Craterhoof", cmc: 8, qty: 1 },
    ];
    expect(filterCardsByManaBucket(cards, 1).map((card) => card.cardName)).toEqual(["Sol Ring"]);
    expect(filterCardsByManaBucket(cards, 7).map((card) => card.cardName)).toEqual(["Craterhoof"]);
    expect(manaBucketLabel(7)).toBe("CMC 7+");
  });
});
