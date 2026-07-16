import { describe, expect, it } from "vitest";
import {
  cardMatchesCollectionCmcFilter,
  cardMatchesCollectionRarityFilter,
  cardMatchesCollectionStorageFilter,
  cardMatchesSearchQuery,
  filterCollectionCards,
} from "./collectionFilters.js";

const sampleCards = [
  {
    setCode: "LTR",
    collectorNumber: "1",
    name: "Frodo",
    finish: 0,
    owned: 1,
    cardType: "creature",
    rarity: "rare",
    cmc: 3,
    power: "2",
    toughness: "2",
    oracleText: "When Frodo enters, scry 1.",
  },
  {
    setCode: "LTR",
    collectorNumber: "245",
    name: "Counterspell",
    finish: 0,
    owned: 0,
    cardType: "instant",
    rarity: "uncommon",
    cmc: 2,
    oracleText: "Counter target spell.",
  },
  {
    setCode: "LTR",
    collectorNumber: "750",
    name: "Mount Doom",
    finish: 1,
    owned: 0,
    cardType: "land",
    rarity: "common",
    cmc: 0,
  },
];

describe("collectionFilters search", () => {
  it("matches collector numbers, names, and oracle text", () => {
    expect(cardMatchesSearchQuery(sampleCards[0], "frodo")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[1], "245")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[1], "counter target")).toBe(true);
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

  it("filters by rarity and cmc", () => {
    expect(cardMatchesCollectionRarityFilter(sampleCards[0], "rare")).toBe(true);
    expect(cardMatchesCollectionCmcFilter(sampleCards[1], { cmcMin: 2, cmcMax: 2 })).toBe(true);
    const filtered = filterCollectionCards(sampleCards, {
      rarityFilter: "uncommon",
      cmcMax: 2,
    });
    expect(filtered).toHaveLength(1);
    expect(filtered[0].name).toBe("Counterspell");
  });

  it("filters by storage location", () => {
    const cards = [
      {
        ...sampleCards[0],
        locations: [{ slug: "storage:general", label: "General", count: 1 }],
      },
      {
        ...sampleCards[1],
        locations: [{ slug: "binder:lotr", label: "LOTR Binder", count: 1 }],
      },
    ];
    expect(cardMatchesCollectionStorageFilter(cards[0], ["storage:general"])).toBe(true);
    expect(cardMatchesCollectionStorageFilter(cards[1], ["storage:general"])).toBe(false);
    const filtered = filterCollectionCards(cards, {
      storageFilters: ["binder:lotr"],
    });
    expect(filtered).toHaveLength(1);
    expect(filtered[0].name).toBe("Counterspell");
  });
});
