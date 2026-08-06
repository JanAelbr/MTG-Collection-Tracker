import { describe, expect, it } from "vitest";
import {
  buildDeckGalleryItems,
  filterDecksForGallery,
  getGalleryCommanders,
  sortDecksForGallery,
} from "./deckBrowse.js";

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

  it("filters decks by name and commander", () => {
    const decks = [
      { id: "1", name: "Atraxa Counters" },
      { id: "2", name: "Budget Tokens" },
      { id: "3", name: "Mill" },
    ];
    const pages = {
      1: { previewCards: [{ section: "commander", cardName: "Atraxa, Praetors' Voice" }] },
      2: { previewCards: [{ section: "commander", cardName: "Baylen, the Haymaker" }] },
      3: { previewCards: [{ section: "commander", cardName: "Phenax, God of Deception" }] },
    };
    expect(filterDecksForGallery(decks, pages, "atraxa").map((deck) => deck.id)).toEqual(["1"]);
    expect(filterDecksForGallery(decks, pages, "baylen").map((deck) => deck.id)).toEqual(["2"]);
    expect(filterDecksForGallery(decks, pages, "token").map((deck) => deck.id)).toEqual(["2"]);
    expect(filterDecksForGallery(decks, pages, "").map((deck) => deck.id)).toEqual(["1", "2", "3"]);
  });

  it("sorts favourites first, then mono before dual, WUBRG within each band", () => {
    const decks = [
      { id: "wu", name: "Azorius", favorite: false },
      { id: "r", name: "Red", favorite: false },
      { id: "w", name: "White", favorite: false },
      { id: "fav", name: "Favourite Blue", favorite: true },
      { id: "u", name: "Blue", favorite: false },
      { id: "c", name: "Colorless", favorite: false },
    ];
    const pages = {
      wu: { previewCards: [{ section: "commander", colorIdentity: ["W", "U"] }] },
      r: { previewCards: [{ section: "commander", colorIdentity: ["R"] }] },
      w: { previewCards: [{ section: "commander", colorIdentity: ["W"] }] },
      fav: { previewCards: [{ section: "commander", colorIdentity: ["U"] }] },
      u: { previewCards: [{ section: "commander", colorIdentity: ["U"] }] },
      c: { previewCards: [{ section: "commander", colorIdentity: [] }] },
    };
    expect(sortDecksForGallery(decks, pages).map((deck) => deck.id)).toEqual([
      "fav",
      "w",
      "u",
      "r",
      "wu",
      "c",
    ]);
  });

  it("builds favourite divider and colour pip markers beside each group", () => {
    const decks = [
      { id: "fav", name: "Favourite", favorite: true },
      { id: "w", name: "White", favorite: false },
      { id: "wu", name: "Azorius", favorite: false },
    ];
    const pages = {
      fav: { previewCards: [{ section: "commander", colorIdentity: ["B"] }] },
      w: { previewCards: [{ section: "commander", colorIdentity: ["W"] }] },
      wu: { previewCards: [{ section: "commander", colorIdentity: ["W", "U"] }] },
    };
    const items = buildDeckGalleryItems(decks, pages);
    expect(items.map((item) => item.type)).toEqual([
      "deck",
      "separator",
      "color",
      "deck",
      "separator",
      "color",
      "deck",
    ]);
    expect(items[2].colors).toEqual(["W"]);
    expect(items[5].colors).toEqual(["W", "U"]);
  });
});
