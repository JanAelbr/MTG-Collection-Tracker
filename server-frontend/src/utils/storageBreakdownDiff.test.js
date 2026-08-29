import { describe, expect, it } from "vitest";
import {
  diffStorageBreakdown,
  sliceSnapshotBreakdown,
} from "./storageBreakdownDiff";

const saved = {
  totals: {
    copies: 4,
    uniquePrints: 2,
    current: 10,
    invested: 6,
    profit: 4,
  },
  byFinish: [
    { id: 0, label: "Nonfoil", copies: 3, current: 6 },
    { id: 1, label: "Foil", copies: 1, current: 4 },
  ],
  bySet: [
    { setCode: "LTR", label: "LOTR", copies: 4, current: 10 },
  ],
  topCards: [
    {
      setCode: "LTR",
      collectorNumber: "1",
      finish: 0,
      name: "Card A",
      copyCount: 2,
      current: 8,
    },
    {
      setCode: "LTR",
      collectorNumber: "2",
      finish: 0,
      name: "Card B",
      copyCount: 2,
      current: 2,
    },
  ],
};

const current = {
  totals: {
    copies: 5,
    uniquePrints: 3,
    current: 16,
    invested: 8,
    profit: 8,
  },
  byFinish: [
    { id: 0, label: "Nonfoil", copies: 4, current: 10 },
    { id: 2, label: "Etched", copies: 1, current: 6 },
  ],
  bySet: [
    { setCode: "LTR", label: "LOTR", copies: 4, current: 10 },
    { setCode: "LTC", label: "Commander", copies: 1, current: 6 },
  ],
  topCards: [
    {
      setCode: "LTR",
      collectorNumber: "1",
      finish: 0,
      name: "Card A",
      copyCount: 3,
      current: 12,
    },
    {
      setCode: "LTC",
      collectorNumber: "3",
      finish: 2,
      name: "Card C",
      copyCount: 1,
      current: 6,
    },
  ],
};

describe("sliceSnapshotBreakdown", () => {
  it("merges selected location slices from a frozen snapshot", () => {
    const snapshot = {
      locations: [
        {
          slug: "storage:a",
          totals: { copies: 1, uniquePrints: 1, current: 4 },
          byFinish: [{ id: 0, label: "Nonfoil", copies: 1, current: 4 }],
          bySet: [{ setCode: "LTR", copies: 1, current: 4 }],
          topCards: [{ setCode: "LTR", collectorNumber: "1", finish: 0, copyCount: 1, current: 4, name: "A" }],
        },
        {
          slug: "storage:b",
          totals: { copies: 2, uniquePrints: 1, current: 6 },
          byFinish: [{ id: 0, label: "Nonfoil", copies: 2, current: 6 }],
          bySet: [{ setCode: "LTR", copies: 2, current: 6 }],
          topCards: [{ setCode: "LTR", collectorNumber: "1", finish: 0, copyCount: 2, current: 6, name: "A" }],
        },
      ],
    };
    const merged = sliceSnapshotBreakdown(snapshot, ["storage:a", "storage:b"]);
    expect(merged.totals.copies).toBe(3);
    expect(merged.totals.current).toBe(10);
    expect(merged.topCards[0].copyCount).toBe(3);
  });

  it("keeps every set when merging snapshot locations", () => {
    const locations = Array.from({ length: 9 }, (_, index) => ({
      slug: `storage:${index}`,
      totals: { copies: 1, uniquePrints: 1, current: index + 1 },
      byFinish: [],
      bySet: [{ setCode: `S${index}`, copies: 1, current: index + 1 }],
      topCards: [],
    }));
    const merged = sliceSnapshotBreakdown({ locations }, locations.map((row) => row.slug));
    expect(merged.bySet).toHaveLength(9);
  });
});

describe("diffStorageBreakdown", () => {
  it("computes signed totals, mix presence, and top-card entered/left", () => {
    const diff = diffStorageBreakdown(saved, current);

    expect(diff.totals.copies).toEqual({ saved: 4, current: 5, delta: 1 });
    expect(diff.totals.current.delta).toBe(6);
    expect(diff.totals.profit.delta).toBe(4);

    const foil = diff.byFinish.find((row) => row.id === 1);
    expect(foil.presence).toBe("saved-only");
    expect(foil.copiesDelta).toBe(-1);

    const etched = diff.byFinish.find((row) => row.id === 2);
    expect(etched.presence).toBe("current-only");
    expect(etched.copiesDelta).toBe(1);

    const ltc = diff.bySet.find((row) => row.setCode === "LTC");
    expect(ltc.presence).toBe("current-only");
    expect(ltc.valueDelta).toBe(6);

    expect(diff.topCards.entered.map((row) => row.name)).toEqual(["Card C"]);
    expect(diff.topCards.left.map((row) => row.name)).toEqual(["Card B"]);
    const cardA = diff.topCards.rows.find((row) => row.name === "Card A");
    expect(cardA.copiesDelta).toBe(1);
    expect(cardA.valueDelta).toBe(4);
  });
});
