import { describe, expect, it } from "vitest";
import { getGalleryCommanders } from "./deckBrowse.js";

describe("deckBrowse gallery helpers", () => {
  it("reads commanders from previewCards-style payloads", () => {
    const previewCards = [
      {
        section: "commander",
        cardName: "Atraxa",
        imageUri: "https://example.com/atraxa.jpg",
      },
      {
        section: "main",
        cardName: "Sol Ring",
        imageUri: "https://example.com/sol-ring.jpg",
      },
    ];
    expect(getGalleryCommanders(previewCards).map((card) => card.cardName)).toEqual([
      "Atraxa",
    ]);
  });
});
