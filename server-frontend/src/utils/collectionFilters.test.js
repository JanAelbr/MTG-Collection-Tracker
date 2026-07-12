import { describe, expect, it } from "vitest";
import { cardMatchesSearchQuery, filterCollectionCards } from "./collectionFilters.js";

const sampleCards = [
  { setCode: "LTR", collectorNumber: "1", name: "Frodo", finish: 0, owned: 1 },
  { setCode: "LTR", collectorNumber: "245", name: "Sauron", finish: 0, owned: 0 },
  { setCode: "LTR", collectorNumber: "750", name: "Mount Doom", finish: 1, owned: 0 },
];

describe("collectionFilters search", () => {
  it("matches collector numbers and names", () => {
    expect(cardMatchesSearchQuery(sampleCards[0], "frodo")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[1], "245")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[2], "#750")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[0], "sauron")).toBe(false);
  });

  it("filters cards by search query", () => {
    const filtered = filterCollectionCards(sampleCards, {
      setCode: "LTR",
      ownedFilter: "all",
      searchQuery: "mount",
    });
    expect(filtered).toHaveLength(1);
    expect(filtered[0].name).toBe("Mount Doom");
  });
});
