import { describe, expect, it } from "vitest";
import {
  mergeStorageBreakdownPayloads,
  mergeStorageCardPayloads,
} from "./storageMerge";

describe("mergeStorageCardPayloads", () => {
  it("returns empty payload for no inputs", () => {
    expect(mergeStorageCardPayloads([])).toEqual({
      location: null,
      cards: [],
      totalCopies: 0,
      uniquePrints: 0,
    });
  });

  it("passes through a single payload", () => {
    const payload = {
      location: { slug: "storage:a" },
      cards: [{ setCode: "LTR", collectorNumber: "1", finish: 0, copyCount: 2, instanceIds: [1, 2] }],
      totalCopies: 2,
      uniquePrints: 1,
    };
    expect(mergeStorageCardPayloads([payload])).toBe(payload);
  });

  it("merges matching prints across locations", () => {
    const merged = mergeStorageCardPayloads([
      {
        cards: [
          {
            setCode: "LTR",
            collectorNumber: "1",
            finish: 0,
            copyCount: 1,
            instanceIds: [1],
            name: "A",
          },
        ],
        totalCopies: 1,
      },
      {
        cards: [
          {
            setCode: "LTR",
            collectorNumber: "1",
            finish: 0,
            copyCount: 2,
            instanceIds: [2, 3],
            name: "A",
          },
          {
            setCode: "LTR",
            collectorNumber: "2",
            finish: 1,
            copyCount: 1,
            instanceIds: [4],
            name: "B",
          },
        ],
        totalCopies: 3,
      },
    ]);
    expect(merged.totalCopies).toBe(4);
    expect(merged.uniquePrints).toBe(2);
    expect(merged.cards).toEqual([
      {
        setCode: "LTR",
        collectorNumber: "1",
        finish: 0,
        copyCount: 3,
        instanceIds: [1, 2, 3],
        name: "A",
      },
      {
        setCode: "LTR",
        collectorNumber: "2",
        finish: 1,
        copyCount: 1,
        instanceIds: [4],
        name: "B",
      },
    ]);
  });
});

describe("mergeStorageBreakdownPayloads", () => {
  it("sums totals and finish buckets", () => {
    const merged = mergeStorageBreakdownPayloads([
      {
        totals: {
          copies: 2,
          uniquePrints: 1,
          current: 10,
          invested: 4,
          pricedCopies: 2,
          unpricedCopies: 0,
        },
        byFinish: [{ id: 0, label: "Non-foil", copies: 2, count: 2, current: 10 }],
        bySet: [{ setCode: "LTR", copies: 2, uniquePrints: 1, current: 10 }],
        topCards: [
          {
            setCode: "LTR",
            collectorNumber: "1",
            finish: 0,
            name: "A",
            copyCount: 2,
            current: 10,
          },
        ],
      },
      {
        totals: {
          copies: 1,
          uniquePrints: 1,
          current: 5,
          invested: 2,
          pricedCopies: 1,
          unpricedCopies: 0,
        },
        byFinish: [{ id: 0, label: "Non-foil", copies: 1, count: 1, current: 5 }],
        bySet: [{ setCode: "LTR", copies: 1, uniquePrints: 1, current: 5 }],
        topCards: [
          {
            setCode: "LTR",
            collectorNumber: "1",
            finish: 0,
            name: "A",
            copyCount: 1,
            current: 5,
          },
        ],
      },
    ]);
    expect(merged.totals.copies).toBe(3);
    expect(merged.totals.current).toBe(15);
    expect(merged.totals.invested).toBe(6);
    expect(merged.totals.profit).toBe(9);
    expect(merged.byFinish[0].copies).toBe(3);
    expect(merged.bySet[0].copies).toBe(3);
    expect(merged.topCards[0].copyCount).toBe(3);
    expect(merged.topCards[0].current).toBe(15);
  });
});
