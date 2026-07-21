import { describe, expect, it } from "vitest";
import {
  compareCollectorNumbers,
  compareManagerCardPrices,
  expandCardFinishRows,
  finishRowKey,
  formatLocationsSummary,
  managerCardPrice,
  sortManagerCards,
} from "./useManagerSetTable";
import { FINISH_FOIL, FINISH_NONFOIL } from "../utils/finishes";

describe("useManagerSetTable helpers", () => {
  it("builds stable finish row keys", () => {
    const card = { collectorNumber: "42" };
    expect(finishRowKey(card, FINISH_NONFOIL)).toBe("42:0");
    expect(finishRowKey(card, FINISH_FOIL)).toBe("42:1");
  });

  it("formats comma-separated storage summaries", () => {
    expect(formatLocationsSummary([
      { label: "Binder A", count: 2 },
      { label: "Deck box", count: 1 },
    ])).toBe("Binder A ×2, Deck box");
  });

  it("expands cards into finish rows without repeating card info flags", () => {
    const card = {
      collectorNumber: "1",
      name: "Test",
      hasNonfoil: true,
      hasFoil: true,
      hasEtched: false,
      marketValue: 1,
      marketValueFoil: 2,
    };
    const rows = expandCardFinishRows([card]);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      finish: FINISH_NONFOIL,
      isFirstFinishRow: true,
      finishRowCount: 2,
    });
    expect(rows[1]).toMatchObject({
      finish: FINISH_FOIL,
      isFirstFinishRow: false,
      finishRowCount: 2,
    });
  });

  it("compares collector numbers numerically when possible", () => {
    expect(compareCollectorNumbers("2", "10")).toBeLessThan(0);
    expect(compareCollectorNumbers("10a", "2")).toBeGreaterThan(0);
  });

  it("reads manager card prices from strategy maps only", () => {
    expect(managerCardPrice({
      marketValue: 1.5,
      valuesByStrategy: { trend: 2.25 },
    }, "trend")).toBe(2.25);
    expect(managerCardPrice({
      marketValue: 1.5,
      valuesByFinish: {
        0: { trend: 2.0 },
        1: { trend: 4.0 },
      },
    }, "trend", FINISH_FOIL)).toBe(4.0);
    expect(managerCardPrice({ marketValue: 1.5 }, "trend")).toBeNull();
    expect(managerCardPrice({ marketValue: null }, "trend")).toBeNull();
  });

  it("sorts unknown prices last regardless of direction", () => {
    const priced = { valuesByStrategy: { trend: 5 } };
    const unknown = { valuesByStrategy: { trend: null } };
    expect(compareManagerCardPrices(priced, unknown, "trend")).toBeLessThan(0);
    expect(compareManagerCardPrices(unknown, priced, "trend")).toBeGreaterThan(0);

    const cards = [
      { collectorNumber: "1", name: "Unknown", valuesByStrategy: { trend: null } },
      { collectorNumber: "2", name: "Cheap", valuesByStrategy: { trend: 1 } },
      { collectorNumber: "3", name: "Pricey", valuesByStrategy: { trend: 10 } },
    ];
    const asc = sortManagerCards(cards, { sort: "value", sortDir: "asc", priceStrategy: "trend" });
    expect(asc.map((card) => card.name)).toEqual(["Cheap", "Pricey", "Unknown"]);
    const desc = sortManagerCards(cards, { sort: "value", sortDir: "desc", priceStrategy: "trend" });
    expect(desc.map((card) => card.name)).toEqual(["Pricey", "Cheap", "Unknown"]);
  });

  it("sorts cards by name, number, and art style", () => {
    const cards = [
      { collectorNumber: "10", name: "Zebra", artStyle: "Showcase" },
      { collectorNumber: "2", name: "Alpha", artStyle: "Borderless" },
      { collectorNumber: "1", name: "Beta", artStyle: "Standard" },
    ];
    expect(sortManagerCards(cards, { sort: "name", sortDir: "asc" }).map((card) => card.name))
      .toEqual(["Alpha", "Beta", "Zebra"]);
    expect(sortManagerCards(cards, { sort: "number", sortDir: "asc" }).map((card) => card.collectorNumber))
      .toEqual(["1", "2", "10"]);
    expect(sortManagerCards(cards, { sort: "artStyle", sortDir: "asc" }).map((card) => card.artStyle))
      .toEqual(["Borderless", "Showcase", "Standard"]);
  });
});
