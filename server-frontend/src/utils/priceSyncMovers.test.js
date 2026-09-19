import { describe, expect, it } from "vitest";
import {
  aggregateArtStyleMovers,
  cardsForArtStyle,
  collectPriceSyncCards,
  collectPriceSyncStyleRows,
  moverRowToTileCard,
  rankMoverRows,
} from "./priceSyncMovers";

describe("aggregateArtStyleMovers", () => {
  it("groups card moves by set and art style", () => {
    const styles = aggregateArtStyleMovers([
      {
        setCode: "LTR",
        artStyle: "Showcase",
        previous: 10,
        current: 16,
        delta: 6,
      },
      {
        setCode: "LTR",
        artStyle: "Showcase",
        previous: 4,
        current: 2,
        delta: -2,
      },
      {
        setCode: "MOM",
        artStyle: "Regular",
        previous: 8,
        current: 8.2,
        delta: 0.2,
      },
    ]);
    expect(styles).toHaveLength(1);
    expect(styles[0].artStyle).toBe("Showcase");
    expect(styles[0].delta).toBe(4);
  });
});

describe("cardsForArtStyle", () => {
  it("filters card rows for one art style", () => {
    const cards = [
      { setCode: "LTR", artStyle: "Showcase", collectorNumber: "1", label: "A" },
      { setCode: "LTR", artStyle: "Regular", collectorNumber: "2", label: "B" },
      { setCode: "LTR", artStyle: "Showcase", label: "style total" },
    ];
    expect(cardsForArtStyle(cards, { setCode: "ltr", artStyle: "Showcase" })).toEqual([
      cards[0],
    ]);
  });
});

describe("collectPriceSyncCards", () => {
  it("ignores art-style totals when collecting cards", () => {
    expect(collectPriceSyncCards({
      cards: [
        { setCode: "LTR", artStyle: "Showcase", collectorNumber: "1", label: "A" },
        { setCode: "LTR", artStyle: "Showcase", label: "style total" },
      ],
    })).toEqual([
      { setCode: "LTR", artStyle: "Showcase", collectorNumber: "1", label: "A" },
    ]);
  });
});

describe("collectPriceSyncStyleRows", () => {
  it("builds art styles from stored card diffs only", () => {
    const rows = collectPriceSyncStyleRows({
      cards: [
        {
          setCode: "LTR",
          artStyle: "Showcase",
          collectorNumber: "1",
          previous: 10,
          current: 16,
        },
      ],
      movers: {
        absolute: {
          risers: [{ id: "LTR|Poster", setCode: "LTR", artStyle: "Poster", delta: 37 }],
          fallers: [],
        },
      },
    });
    expect(rows).toHaveLength(1);
    expect(rows[0].artStyle).toBe("Showcase");
    expect(rows[0].delta).toBe(6);
  });
});

describe("moverRowToTileCard", () => {
  it("maps a stored card diff onto a collection tile card", () => {
    const card = moverRowToTileCard({
      name: "Gandalf",
      label: "Gandalf (Foil)",
      setCode: "ltr",
      collectorNumber: "1",
      finish: "Foil",
      imageUri: "https://example.com/gandalf.jpg",
    });
    expect(card).toEqual({
      name: "Gandalf",
      cardName: "Gandalf",
      setCode: "LTR",
      collectorNumber: "1",
      imageUri: "https://example.com/gandalf.jpg",
      finish: "Foil",
    });
  });
});

describe("rankMoverRows", () => {
  it("ranks relative movers by percent", () => {
    const ranked = rankMoverRows([
      { delta: 10, percent: 5 },
      { delta: 2, percent: 40 },
      { delta: -8, percent: -4 },
      { delta: -3, percent: -30 },
    ], { scale: "relative", limit: 25 });
    expect(ranked.risers.map((row) => row.percent)).toEqual([40, 5]);
    expect(ranked.fallers.map((row) => row.percent)).toEqual([-30, -4]);
  });
});
