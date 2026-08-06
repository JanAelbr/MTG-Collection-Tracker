import { describe, expect, it } from "vitest";
import {
  cardMatchesColorFilter,
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
