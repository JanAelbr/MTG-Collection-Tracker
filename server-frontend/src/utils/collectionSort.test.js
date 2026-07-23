import { describe, expect, it } from "vitest";
import {
  defaultCollectionSortDir,
  groupCollectionCardsBySet,
  normalizeCollectionSort,
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
    expect(normalizeCollectionSort("set", { allowSet: true })).toBe("set");
    expect(normalizeCollectionSort("set")).toBe("value");
    expect(normalizeCollectionSort("nope")).toBe("value");
    expect(defaultCollectionSortDir("number")).toBe("asc");
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
});
