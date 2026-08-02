import { describe, expect, it } from "vitest";
import { cardMatchesColorFilter, cardMatchesOwnershipFilter, isDeckCardMissing } from "./deckCards.js";

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
