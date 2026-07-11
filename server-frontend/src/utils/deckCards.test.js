import { describe, expect, it } from "vitest";
import { cardMatchesOwnershipFilter, isDeckCardMissing } from "./deckCards.js";

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
