import { describe, expect, it } from "vitest";
import { COLLECTION_TYPE_ORDER } from "./collectionTypes.js";
import {
  buildDeckCardGroups,
  buildEmptyDeckCardGroups,
  cardMatchesColorFilter,
  cardMatchesDeckSearchQuery,
  cardMatchesOwnershipFilter,
  cardWithinColorIdentity,
  isDeckCardMissing,
  visibleColorPipsForIdentity,
} from "./deckCards.js";

describe("deckCards ownership filter", () => {
  it("detects partially and fully missing deck slots", () => {
    expect(isDeckCardMissing({ qty: 2, ownedQty: 1 })).toBe(true);
    expect(isDeckCardMissing({ qty: 1, ownedQty: 1 })).toBe(false);
    expect(isDeckCardMissing({ qty: 1, ownedQty: 0 })).toBe(true);
  });

  it("filters missing and owned cards", () => {
    const cards = [
      { qty: 1, ownedQty: 1, cardName: "A" },
      { qty: 1, ownedQty: 0, cardName: "B" },
    ];
    expect(cardMatchesOwnershipFilter(cards[1], "missing")).toBe(true);
    expect(cardMatchesOwnershipFilter(cards[0], "owned")).toBe(true);
    expect(
      cards.filter((card) => cardMatchesOwnershipFilter(card, "missing")),
    ).toHaveLength(1);
  });
});

describe("cardMatchesDeckSearchQuery", () => {
  it("matches name, type, and set fields", () => {
    const card = {
      cardName: "Sol Ring",
      setCode: "LTC",
      collectorNumber: "284",
      typeLine: "Artifact",
      cardType: "artifact",
    };
    expect(cardMatchesDeckSearchQuery(card, "")).toBe(true);
    expect(cardMatchesDeckSearchQuery(card, "sol")).toBe(true);
    expect(cardMatchesDeckSearchQuery(card, "artifact")).toBe(true);
    expect(cardMatchesDeckSearchQuery(card, "ltc")).toBe(true);
    expect(cardMatchesDeckSearchQuery(card, "284")).toBe(true);
    expect(cardMatchesDeckSearchQuery(card, "lightning")).toBe(false);
  });
});

describe("cardMatchesColorFilter", () => {
  it("matches exact color identity by default", () => {
    expect(cardMatchesColorFilter({ colors: ["R"], colorIdentity: ["R"] }, ["R"])).toBe(true);
    expect(cardMatchesColorFilter({ colors: [], colorIdentity: ["R"] }, ["R"])).toBe(true);
    expect(cardMatchesColorFilter({ colors: ["R", "G"], colorIdentity: ["R", "G"] }, ["R"])).toBe(false);
    expect(cardMatchesColorFilter({ colors: ["R", "G"], colorIdentity: ["R", "G"] }, ["R", "G"])).toBe(true);
  });

  it("supports inclusive casting-color matching", () => {
    expect(cardMatchesColorFilter(
      { colors: ["R", "G"], colorIdentity: ["R", "G"] },
      ["R"],
      { mode: "includes" },
    )).toBe(true);
  });
});

describe("cardWithinColorIdentity", () => {
  it("allows subset and colorless cards for a multicolor commander", () => {
    expect(cardWithinColorIdentity({ colorIdentity: ["U"] }, ["U", "R"])).toBe(true);
    expect(cardWithinColorIdentity({ colorIdentity: ["U", "R"] }, ["U", "R"])).toBe(true);
    expect(cardWithinColorIdentity({ colorIdentity: [] }, ["U", "R"])).toBe(true);
    expect(cardWithinColorIdentity({ colorIdentity: ["G"] }, ["U", "R"])).toBe(false);
  });

  it("restricts colorless commanders to colorless cards", () => {
    expect(cardWithinColorIdentity({ colorIdentity: [] }, [])).toBe(true);
    expect(cardWithinColorIdentity({ colorIdentity: ["R"] }, [])).toBe(false);
  });

  it("skips filtering when identity is null", () => {
    expect(cardWithinColorIdentity({ colorIdentity: ["G"] }, null)).toBe(true);
  });
});

describe("visibleColorPipsForIdentity", () => {
  it("shows commander colors plus colorless", () => {
    expect(visibleColorPipsForIdentity(["U", "R"])).toEqual(["U", "R", "C"]);
    expect(visibleColorPipsForIdentity([])).toEqual(["C"]);
    expect(visibleColorPipsForIdentity(null)).toEqual(["W", "U", "B", "R", "G", "C"]);
  });
});

describe("buildDeckCardGroups", () => {
  it("includes empty type groups for types not yet in the deck", () => {
    const groups = buildDeckCardGroups([
      { section: "main", cardType: "creature", cardName: "Bear", qty: 1 },
    ]);
    const typeGroups = groups.filter((group) => group.kind === "type");
    expect(typeGroups.map((group) => group.type)).toEqual([...COLLECTION_TYPE_ORDER]);
    const creatures = typeGroups.find((group) => group.type === "creature");
    const instants = typeGroups.find((group) => group.type === "instant");
    const lands = typeGroups.find((group) => group.type === "land");
    expect(creatures.cards).toHaveLength(1);
    expect(creatures.count).toBe(1);
    expect(instants.cards).toEqual([]);
    expect(instants.count).toBe(0);
    expect(lands.cards).toEqual([]);
    expect(lands.count).toBe(0);
  });

  it("keeps extra types after the standard order", () => {
    const groups = buildDeckCardGroups([
      { section: "main", cardType: "creature", cardName: "Bear", qty: 1 },
      { section: "main", cardType: "dungeon", cardName: "Undercity", qty: 1 },
    ]);
    const types = groups.filter((group) => group.kind === "type").map((group) => group.type);
    expect(types.at(-1)).toBe("dungeon");
    expect(types.slice(0, -1)).toEqual([...COLLECTION_TYPE_ORDER]);
  });
});

describe("buildEmptyDeckCardGroups", () => {
  it("uses the standard type list instead of a generic cards group", () => {
    const groups = buildEmptyDeckCardGroups();
    const typeGroups = groups.filter((group) => group.kind === "type");
    expect(typeGroups.map((group) => group.type)).toEqual([...COLLECTION_TYPE_ORDER]);
    expect(typeGroups.every((group) => group.cards.length === 0)).toBe(true);
  });
});
