import { describe, expect, it } from "vitest";
import {
  cardMatchesCollectionCmcFilter,
  cardMatchesCollectionPriceFilter,
  cardMatchesCollectionRarityFilter,
  cardMatchesCollectionStorageFilter,
  cardMatchesSearchQuery,
  cardMatchesStorageSearchQuery,
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
    currentValue: 4.5,
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
    currentValue: 0.75,
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
    currentValue: null,
  },
];

describe("collectionFilters search", () => {
  it("matches collector numbers, names, and oracle text", () => {
    expect(cardMatchesSearchQuery(sampleCards[0], "frodo")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[1], "245")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[1], "counter target")).toBe(true);
    expect(cardMatchesSearchQuery(sampleCards[0], "sauron")).toBe(false);
  });

  it("AND-matches storage search tokens and treats special chars as wildcards", () => {
    const card = {
      name: "Jace, the Mind Sculptor",
      collectorNumber: "1",
      oracleText: "Draw cards.",
    };
    expect(cardMatchesStorageSearchQuery(card, "mind sculptor")).toBe(true);
    expect(cardMatchesStorageSearchQuery(card, "jace mind")).toBe(true);
    expect(cardMatchesStorageSearchQuery(card, "jace sauron")).toBe(false);

    expect(cardMatchesStorageSearchQuery(
      { name: "Ring's Path", collectorNumber: "2", oracleText: "" },
      "ring's",
    )).toBe(true);
    expect(cardMatchesStorageSearchQuery(
      { name: "Rings Path", collectorNumber: "2", oracleText: "" },
      "ring's",
    )).toBe(true);
    expect(cardMatchesStorageSearchQuery(
      { name: "Frodo Baggins", collectorNumber: "3", oracleText: "" },
      "frodo-baggins",
    )).toBe(true);
    expect(cardMatchesStorageSearchQuery(
      { name: "Frodobaggins", collectorNumber: "3", oracleText: "" },
      "frodo-baggins",
    )).toBe(true);
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

  it("uses storage search mode when requested", () => {
    const cards = [
      { name: "Mind Stone", collectorNumber: "1", oracleText: "" },
      { name: "Sculpting Steel", collectorNumber: "2", oracleText: "" },
      { name: "Jace, the Mind Sculptor", collectorNumber: "3", oracleText: "" },
    ];
    const filtered = filterCollectionCards(cards, {
      searchQuery: "mind sculptor",
      searchMode: "storage",
    });
    expect(filtered.map((card) => card.name)).toEqual(["Jace, the Mind Sculptor"]);
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

  it("filters by price range on currentValue", () => {
    expect(cardMatchesCollectionPriceFilter(sampleCards[0], { priceMin: 4 })).toBe(true);
    expect(cardMatchesCollectionPriceFilter(sampleCards[1], { priceMax: 1 })).toBe(true);
    expect(cardMatchesCollectionPriceFilter(sampleCards[2], { priceMin: 0 })).toBe(false);
    const filtered = filterCollectionCards(sampleCards, {
      priceMin: 1,
      priceMax: 5,
    });
    expect(filtered.map((card) => card.name)).toEqual(["Frodo"]);
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
