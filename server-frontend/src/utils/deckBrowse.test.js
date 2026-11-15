import { describe, expect, it } from "vitest";
import {
  buildDeckGalleryItems,
  deckDayRows,
  filterDecksForGallery,
  getGalleryCommanders,
  sortDecksForGallery,
} from "./deckBrowse.js";

describe("deck day changes", () => {
  it("multiplies the sync move by owned copies", () => {
    const decks = [
      { id: 1, name: "Tokens" },
      { id: 2, name: "Mill" },
    ];
    const pages = {
      1: {
        ownedCurrent: 12,
        previewCards: [{ section: "commander", cardName: "Baylen" }],
        ownedPrints: [
          { setCode: "ltr", collectorNumber: "10", finish: 0, ownedQty: 2 },
        ],
      },
      2: {
        ownedCurrent: 4,
        ownedPrints: [
          { setCode: "MH3", collectorNumber: "1", finish: 1, ownedQty: 1 },
        ],
      },
    };
    const syncCards = [
      { setCode: "LTR", collectorNumber: "10", finishId: 0, delta: 0.5 },
      { setCode: "MH3", collectorNumber: "1", finishId: 1, previous: 2, current: 1.25 },
    ];
    expect(deckDayRows(decks, pages, syncCards)).toEqual([
      {
        id: 2,
        name: "Mill",
        commanders: "",
        commanderName: "",
        imageUri: "",
        setCode: "",
        collectorNumber: "",
        finish: null,
        colors: [],
        favorite: false,
        current: 4,
        up: 0,
        down: -0.75,
        delta: -0.75,
      },
      {
        id: 1,
        name: "Tokens",
        commanders: "Baylen",
        commanderName: "Baylen",
        imageUri: "",
        setCode: "",
        collectorNumber: "",
        finish: null,
        colors: [],
        favorite: false,
        current: 12,
        up: 1,
        down: 0,
        delta: 1,
      },
    ]);
  });

  it("orders favourites first, then colour identity, then name", () => {
    const decks = [
      { id: 1, name: "Zedruu" },
      { id: 2, name: "Azorius" },
      { id: 3, name: "Heliod", favorite: true },
      { id: 4, name: "Krenko" },
    ];
    const pages = {
      1: { previewCards: [{ section: "commander", cardName: "Zedruu", colorIdentity: ["U", "R", "W"] }] },
      2: { previewCards: [{ section: "commander", cardName: "Shorikai", colorIdentity: ["U", "W"] }] },
      3: { previewCards: [{ section: "commander", cardName: "Heliod", colorIdentity: ["W"] }] },
      4: { previewCards: [{ section: "commander", cardName: "Krenko", colorIdentity: ["R"] }] },
    };
    expect(deckDayRows(decks, pages, []).map((deck) => deck.name)).toEqual([
      "Heliod",
      "Krenko",
      "Azorius",
      "Zedruu",
    ]);
  });
});

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
