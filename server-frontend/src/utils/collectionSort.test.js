import { describe, expect, it } from "vitest";
import {
  defaultCollectionSortDir,
  groupCollectionCardsBySet,
  normalizeCollectionSort,
  sortCollectionCardGroups,
  sortCollectionCards,
} from "./collectionSort";

describe("collectionSort", () => {
  const cards = [
    { name: "Beta", setCode: "LTR", collectorNumber: "10", finish: 0, currentValue: 5, artStyle: "Standard" },
    { name: "Alpha", setCode: "LTR", collectorNumber: "2", finish: 1, currentValue: 12, artStyle: "Showcase" },
    { name: "Gamma", setCode: "M21", collectorNumber: "1", finish: 0, currentValue: 3, artStyle: "Standard" },
  ];

  it("normalizes sort fields and defaults", () => {
    expect(normalizeCollectionSort("name")).toBe("name");
    expect(normalizeCollectionSort("cmc")).toBe("cmc");
    expect(normalizeCollectionSort("rarity")).toBe("rarity");
    expect(normalizeCollectionSort("power")).toBe("power");
    expect(normalizeCollectionSort("toughness")).toBe("toughness");
    expect(normalizeCollectionSort("set", { allowSet: true })).toBe("set");
    expect(normalizeCollectionSort("set")).toBe("value");
    expect(normalizeCollectionSort("nope")).toBe("value");
    expect(defaultCollectionSortDir("number")).toBe("asc");
    expect(defaultCollectionSortDir("cmc")).toBe("asc");
    expect(defaultCollectionSortDir("rarity")).toBe("asc");
    expect(defaultCollectionSortDir("power")).toBe("desc");
    expect(defaultCollectionSortDir("toughness")).toBe("desc");
    expect(defaultCollectionSortDir("value")).toBe("desc");
  });

  it("sorts by value descending by default", () => {
    const sorted = sortCollectionCards(cards, { sort: "value", dir: "desc" });
    expect(sorted.map((card) => card.name)).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  it("sorts by name ascending", () => {
    const sorted = sortCollectionCards(cards, { sort: "name", dir: "asc" });
    expect(sorted.map((card) => card.name)).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  it("sorts by collector number numerically", () => {
    const sameSet = cards.filter((card) => card.setCode === "LTR");
    const sorted = sortCollectionCards(sameSet, { sort: "number", dir: "asc" });
    expect(sorted.map((card) => card.collectorNumber)).toEqual(["2", "10"]);
  });

  it("sorts by set then number when allowSet", () => {
    const sorted = sortCollectionCards(cards, { sort: "set", dir: "asc", allowSet: true });
    expect(sorted.map((card) => `${card.setCode}-${card.collectorNumber}`)).toEqual([
      "LTR-2",
      "LTR-10",
      "M21-1",
    ]);
  });

  it("sorts by finish and copies", () => {
    const withCopies = cards.map((card, index) => ({
      ...card,
      copyCount: index + 1,
    }));
    expect(
      sortCollectionCards(withCopies, { sort: "finish", dir: "asc" }).map((card) => card.finish),
    ).toEqual([0, 0, 1]);
    expect(
      sortCollectionCards(withCopies, { sort: "copies", dir: "desc" }).map((card) => card.copyCount),
    ).toEqual([3, 2, 1]);
  });

  it("sorts by cmc ascending with missing last", () => {
    const withCmc = [
      { name: "Bolt", setCode: "M21", collectorNumber: "1", finish: 0, cmc: 1 },
      { name: "Beast", setCode: "M21", collectorNumber: "2", finish: 0, cmc: 3 },
      { name: "Unknown", setCode: "M21", collectorNumber: "3", finish: 0 },
      { name: "Cantrip", setCode: "M21", collectorNumber: "4", finish: 0, cmc: 1 },
    ];
    expect(
      sortCollectionCards(withCmc, { sort: "cmc", dir: "asc" }).map((card) => card.name),
    ).toEqual(["Bolt", "Cantrip", "Beast", "Unknown"]);
  });

  it("sorts by rarity, power, and toughness", () => {
    const withStats = [
      { name: "Common", setCode: "M21", collectorNumber: "1", finish: 0, rarity: "common", power: "1", toughness: "1" },
      { name: "Mythic", setCode: "M21", collectorNumber: "2", finish: 0, rarity: "mythic", power: "5", toughness: "4" },
      { name: "Rare", setCode: "M21", collectorNumber: "3", finish: 0, rarity: "rare", power: "*", toughness: "3" },
      { name: "Instant", setCode: "M21", collectorNumber: "4", finish: 0, rarity: "uncommon" },
    ];
    expect(
      sortCollectionCards(withStats, { sort: "rarity", dir: "asc" }).map((card) => card.name),
    ).toEqual(["Common", "Instant", "Rare", "Mythic"]);
    expect(
      sortCollectionCards(withStats, { sort: "power", dir: "desc" }).map((card) => card.name),
    ).toEqual(["Mythic", "Common", "Rare", "Instant"]);
    expect(
      sortCollectionCards(withStats, { sort: "toughness", dir: "desc" }).map((card) => card.name),
    ).toEqual(["Mythic", "Rare", "Common", "Instant"]);
  });

  it("does not mutate the input list", () => {
    const original = [...cards];
    sortCollectionCards(cards, { sort: "name", dir: "asc" });
    expect(cards).toEqual(original);
  });

  it("groups cards by set and sorts within each group", () => {
    const groups = groupCollectionCardsBySet(cards, { sort: "value", dir: "desc", allowSet: true });
    expect(groups.map((group) => group.setCode)).toEqual(["LTR", "M21"]);
    expect(groups[0].cards.map((card) => card.name)).toEqual(["Alpha", "Beta"]);
    expect(groups[1].cards.map((card) => card.name)).toEqual(["Gamma"]);
  });

  it("orders set groups by set sort direction", () => {
    const groups = groupCollectionCardsBySet(cards, { sort: "set", dir: "desc", allowSet: true });
    expect(groups.map((group) => group.setCode)).toEqual(["M21", "LTR"]);
  });

  it("orders set groups by total value", () => {
    const mixed = [
      { name: "Cheap", setCode: "AAA", collectorNumber: "1", finish: 0, currentValue: 1, copyCount: 1 },
      { name: "Pricey", setCode: "ZZZ", collectorNumber: "1", finish: 0, currentValue: 40, copyCount: 1 },
    ];
    const groups = groupCollectionCardsBySet(mixed, { sort: "value", dir: "desc", allowSet: true });
    expect(groups.map((group) => group.setCode)).toEqual(["ZZZ", "AAA"]);
  });

  it("sorts nested groups by the active field", () => {
    const groups = sortCollectionCardGroups([
      {
        key: "aaa",
        label: "Alpha set",
        groupBy: "set",
        totalValue: 5,
        copyCount: 2,
        cards: [{ name: "A", currentValue: 5, power: "1" }],
        groups: [
          {
            key: "common",
            label: "Common",
            groupBy: "rarity",
            cards: [{ name: "A", rarity: "common", currentValue: 1 }],
            groups: [],
          },
          {
            key: "rare",
            label: "Rare",
            groupBy: "rarity",
            cards: [{ name: "B", rarity: "rare", currentValue: 9 }],
            groups: [],
          },
        ],
      },
      {
        key: "zzz",
        label: "Zed set",
        groupBy: "set",
        totalValue: 20,
        copyCount: 1,
        cards: [{ name: "Z", currentValue: 20, power: "5" }],
        groups: [],
      },
    ], { sort: "value", dir: "desc", allowSet: true });

    expect(groups.map((group) => group.key)).toEqual(["zzz", "aaa"]);
    expect(groups[1].groups.map((group) => group.key)).toEqual(["rare", "common"]);
  });

  it("reverses canonical group order when sorting by that field", () => {
    const groups = sortCollectionCardGroups([
      { key: "1", label: "CMC 1", groupBy: "cmc", cards: [{ cmc: 1 }], groups: [] },
      { key: "3", label: "CMC 3", groupBy: "cmc", cards: [{ cmc: 3 }], groups: [] },
      { key: "__none__", label: "Unknown CMC", groupBy: "cmc", cards: [{}], groups: [] },
    ], { sort: "cmc", dir: "desc" });
    expect(groups.map((group) => group.key)).toEqual(["3", "1", "__none__"]);
  });
});
