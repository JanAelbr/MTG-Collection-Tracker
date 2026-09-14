import { describe, expect, it } from "vitest";
import {
  attachCatalogGroupPricing,
  catalogColorGroupKey,
  catalogColorPips,
  catalogGroupValueBandCounts,
  catalogValueGroupKey,
  catalogValueGroupKeyForCard,
  formatCatalogGroupMeta,
  groupCatalogCards,
  shouldApplyPriceTileTint,
  UNPRICED_KEY,
} from "./catalogGroups.js";

describe("catalogColorGroupKey", () => {
  it("maps mono, gold, and empty casting colors", () => {
    expect(catalogColorGroupKey({ colors: ["G"] })).toBe("G");
    expect(catalogColorGroupKey({ colors: ["R", "U"] })).toBe("M");
    expect(catalogColorGroupKey({ colors: [] })).toBe("C");
    expect(catalogColorGroupKey({ colors: ["W", "U", "B", "R", "G"] })).toBe("M");
    expect(catalogColorGroupKey({})).toBe("C");
  });

  it("ignores color identity for lands", () => {
    expect(catalogColorGroupKey({ colors: [], colorIdentity: ["R"] })).toBe("C");
  });
});

describe("catalogColorPips", () => {
  it("returns WUBRG for multicolor and empty for colorless", () => {
    expect(catalogColorPips("M")).toEqual(["W", "U", "B", "R", "G"]);
    expect(catalogColorPips("C")).toEqual([]);
    expect(catalogColorPips("U")).toEqual(["U"]);
  });
});

describe("catalogValueGroupKey", () => {
  it("uses exclusive lower-bounded euro bands", () => {
    expect(catalogValueGroupKey(0)).toBe("0-25c");
    expect(catalogValueGroupKey(0.249)).toBe("0-25c");
    expect(catalogValueGroupKey(0.25)).toBe("25-50c");
    expect(catalogValueGroupKey(0.5)).toBe("50c-1");
    expect(catalogValueGroupKey(1)).toBe("1-5");
    expect(catalogValueGroupKey(5)).toBe("5-10");
    expect(catalogValueGroupKey(10)).toBe("10+");
    expect(catalogValueGroupKey(24.99)).toBe("10+");
    expect(catalogValueGroupKey(25)).toBe("25+");
    expect(catalogValueGroupKey(49.99)).toBe("25+");
    expect(catalogValueGroupKey(50)).toBe("50+");
    expect(catalogValueGroupKey(100)).toBe("100+");
    expect(catalogValueGroupKey(250)).toBe("250+");
    expect(catalogValueGroupKey(500)).toBe("500+");
    expect(catalogValueGroupKey(null)).toBe(UNPRICED_KEY);
    expect(catalogValueGroupKey(undefined)).toBe(UNPRICED_KEY);
  });

  it("uses gallery display value (trend when paired)", () => {
    expect(catalogValueGroupKeyForCard({
      currentValue: 0.1,
      valuesByStrategy: { low: 0.2, trend: 12 },
    })).toBe("10+");
  });
});

describe("shouldApplyPriceTileTint", () => {
  it("is off when the setting is off", () => {
    expect(shouldApplyPriceTileTint({ enabled: false, sort: "color" })).toBe(false);
  });

  it("is off when sorted or grouped by price", () => {
    expect(shouldApplyPriceTileTint({ enabled: true, sort: "value" })).toBe(false);
    expect(shouldApplyPriceTileTint({
      enabled: true,
      sort: "name",
      groupBy: ["set", "value"],
    })).toBe(false);
  });

  it("is on for other sorts and groups", () => {
    expect(shouldApplyPriceTileTint({ enabled: true, sort: "color" })).toBe(true);
    expect(shouldApplyPriceTileTint({
      enabled: true,
      sort: "name",
      groupBy: ["set", "color"],
    })).toBe(true);
  });
});

describe("groupCatalogCards", () => {
  it("keeps input order and repeats a color when runs are interrupted", () => {
    const cards = [
      { name: "White A", colors: ["W"] },
      { name: "White B", colors: ["W"] },
      { name: "Blue", colors: ["U"] },
      { name: "White C", colors: ["W"] },
    ];
    const groups = groupCatalogCards(cards, "number");
    expect(groups.map((group) => group.key)).toEqual(["W", "U", "W"]);
    expect(groups.map((group) => group.cards.map((card) => card.name))).toEqual([
      ["White A", "White B"],
      ["Blue"],
      ["White C"],
    ]);
  });

  it("sections value sort as consecutive price bands without reordering", () => {
    const cards = [
      { name: "Cheap", currentValue: 0.1 },
      { name: "Mid", currentValue: 3 },
      { name: "Also cheap", currentValue: 0.2 },
      { name: "None", currentValue: null },
    ];
    const groups = groupCatalogCards(cards, "value");
    expect(groups.map((group) => group.key)).toEqual(["0-25c", "1-5", "0-25c", UNPRICED_KEY]);
    expect(groups.flatMap((group) => group.cards.map((card) => card.name))).toEqual([
      "Cheap",
      "Mid",
      "Also cheap",
      "None",
    ]);
  });

  it("adds a gallery price total on each section", () => {
    const groups = groupCatalogCards([
      { name: "A", colors: ["W"], valuesByStrategy: { low: 1, trend: 2 } },
      { name: "B", colors: ["W"], valuesByStrategy: { low: 3, trend: 4 } },
    ], "number");
    expect(groups[0].metaText).toBe("2 cards · €4.00 ~ €6.00");
    expect(groups[0].valueBands).toEqual([]);
  });
});

describe("formatCatalogGroupMeta", () => {
  it("keeps count-only when nothing is priced", () => {
    expect(formatCatalogGroupMeta([{ currentValue: null }])).toBe("1 card");
  });

  it("uses a single euro amount when low and trend match", () => {
    expect(formatCatalogGroupMeta([
      { valuesByStrategy: { low: 1.5, trend: 1.5 } },
      { valuesByStrategy: { low: 2.5 } },
    ])).toBe("2 cards · €4.00");
  });
});

describe("catalogGroupValueBandCounts", () => {
  it("lists occupied bands in price order", () => {
    expect(catalogGroupValueBandCounts([
      { currentValue: 0.1 },
      { currentValue: 3 },
      { currentValue: 3 },
      { currentValue: null },
    ]).map((band) => `${band.key}:${band.count}`)).toEqual([
      "0-25c:1",
      "1-5:2",
      `${UNPRICED_KEY}:1`,
    ]);
  });
});

describe("attachCatalogGroupPricing", () => {
  it("hides band chips on value groups and single-band color groups", () => {
    const valueGroup = attachCatalogGroupPricing({
      groupBy: "value",
      cards: [{ currentValue: 3 }, { currentValue: 4 }],
    });
    expect(valueGroup.valueBands).toEqual([]);
    expect(valueGroup.metaText).toContain("2 cards");

    const monoBand = attachCatalogGroupPricing({
      groupBy: "color",
      cards: [{ currentValue: 3 }, { currentValue: 4 }],
    });
    expect(monoBand.valueBands).toEqual([]);
  });

  it("shows band chips when a color group spans prices", () => {
    const group = attachCatalogGroupPricing({
      groupBy: "colorIdentity",
      cards: [{ currentValue: 0.1 }, { currentValue: 80 }],
    });
    expect(group.valueBands.map((band) => band.key)).toEqual(["0-25c", "50+"]);
  });
});
