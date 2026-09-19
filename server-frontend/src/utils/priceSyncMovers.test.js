import { describe, expect, it } from "vitest";
import {
  aggregateArtStyleMovers,
  cardsForArtStyle,
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
  it("filters cards for one art style", () => {
    const cards = [
      { setCode: "LTR", artStyle: "Showcase", label: "A" },
      { setCode: "LTR", artStyle: "Regular", label: "B" },
    ];
    expect(cardsForArtStyle(cards, { setCode: "ltr", artStyle: "Showcase" })).toEqual([
      cards[0],
    ]);
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
