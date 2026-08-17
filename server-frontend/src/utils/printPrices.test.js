import { describe, expect, it } from "vitest";

import {
  allArtStyleKeys,
  artStyleSelectionKey,
  buildArtStyleGroups,
  buildPrintPriceRows,
  groupPrintPriceRows,
  mapWithConcurrency,
  stepPreviewSetIndex,
} from "./printPrices";

const card = {
  setCode: "LTR",
  setName: "The Lord of the Rings",
  collectorNumber: "10a",
  name: "A Card",
  artStyle: "Main",
  ownedNonfoil: true,
  ownedFoil: true,
  valuesByFinish: {
    0: { trend: 1.5 },
    1: { trend: 3.5 },
  },
};

describe("print prices", () => {
  it("expands owned finishes and applies strategy minimum price", () => {
    expect(buildPrintPriceRows([card], { strategy: "trend", minimumPrice: 2 })).toEqual([
      expect.objectContaining({ finish: 1, price: 3.5 }),
    ]);
  });

  it("groups by set and art style and uses collector ordering", () => {
    const rows = buildPrintPriceRows([
      card,
      {
        ...card,
        collectorNumber: "2",
        name: "Earlier Card",
        ownedFoil: false,
      },
    ]);

    expect(groupPrintPriceRows(rows)[0].rows.map((row) => row.collectorNumber)).toEqual([
      "2",
      "10a",
      "10a",
    ]);
  });

  it("includes catalog finishes when ownedOnly is false", () => {
    const unowned = {
      ...card,
      ownedNonfoil: false,
      ownedFoil: false,
      hasNonfoil: true,
      valuesByFinish: { 0: { trend: 4 } },
    };
    expect(buildPrintPriceRows([unowned], { ownedOnly: false })).toEqual([
      expect.objectContaining({ finish: 0, price: 4 }),
    ]);
    expect(buildPrintPriceRows([unowned], { ownedOnly: true })).toEqual([]);
  });

  it("groups art style checkboxes by set", () => {
    const groups = buildArtStyleGroups([
      card,
      { ...card, setCode: "LTC", setName: "Tales of Middle-earth Commander", artStyle: "Main" },
      { ...card, artStyle: "Showcase" },
    ]);
    expect(groups.map((group) => group.setCode)).toEqual(["LTC", "LTR"]);
    expect(groups[1].styles.map((style) => style.key)).toEqual([
      artStyleSelectionKey("LTR", "Main"),
      artStyleSelectionKey("LTR", "Showcase"),
    ]);
    expect(allArtStyleKeys(groups)).toHaveLength(3);
  });

  it("steps preview to the first art style of the next set", () => {
    const groups = [
      { setCode: "LTR", artStyle: "Main" },
      { setCode: "LTR", artStyle: "Showcase" },
      { setCode: "LTC", artStyle: "Main" },
    ];
    expect(stepPreviewSetIndex(groups, 0, 1)).toBe(2);
    expect(stepPreviewSetIndex(groups, 1, 1)).toBe(2);
    expect(stepPreviewSetIndex(groups, 2, 1)).toBe(0);
    expect(stepPreviewSetIndex(groups, 2, -1)).toBe(0);
    expect(stepPreviewSetIndex(groups, 0, -1)).toBe(2);
  });

  it("maps with a concurrency cap", async () => {
    let active = 0;
    let maxActive = 0;
    const values = await mapWithConcurrency([1, 2, 3, 4], 2, async (value) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await Promise.resolve();
      active -= 1;
      return value * 2;
    });
    expect(values).toEqual([2, 4, 6, 8]);
    expect(maxActive).toBeLessThanOrEqual(2);
  });
});
