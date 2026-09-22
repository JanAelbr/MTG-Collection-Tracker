import { describe, expect, it } from "vitest";
import {
  aggregateArtStyleMovers,
  cardsForArtStyle,
  collectPriceSyncCards,
  collectPriceSyncStyleRows,
  firstPriceSyncCards,
  favoriteArtStyleDayRows,
  favoriteSetDayRows,
  favoriteCardDayRows,
  moverRowToTileCard,
  rankMoverRows,
  signedDayChange,
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
    expect(styles).toHaveLength(2);
    expect(styles[0].artStyle).toBe("Showcase");
    expect(styles[0].delta).toBe(4);
    expect(styles[1].artStyle).toBe("Regular");
    expect(styles[1].delta).toBeCloseTo(0.2);
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

describe("firstPriceSyncCards", () => {
  it("skips empty status cards and uses the completed outcome", () => {
    const moved = [{ setCode: "LTR", collectorNumber: "1", previous: 2, current: 5 }];
    expect(firstPriceSyncCards(
      { cards: [] },
      { cards: [], lastSync: { cards: [] } },
      { cards: moved },
    )).toEqual(moved);
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
      owned: true,
      ownedQty: 1,
    });
  });
});

describe("signedDayChange", () => {
  it("splits owned risers and fallers for the day", () => {
    expect(signedDayChange([
      { previous: 10, current: 16, delta: 6 },
      { previous: 8, current: 5, delta: -3 },
    ])).toEqual({
      up: 6,
      down: -3,
      previous: 18,
      current: 21,
      delta: 3,
    });
  });
});

describe("favoriteSetDayRows", () => {
  it("sums owned movers for one favourite set", () => {
    const rows = favoriteSetDayRows(
      [{ setCode: "ltr", label: "The Lord of the Rings (LTR)" }],
      [
        { setCode: "LTR", collectorNumber: "1", previous: 10, current: 16, delta: 6 },
        { setCode: "LTR", collectorNumber: "2", previous: 8, current: 5, delta: -3 },
        { setCode: "MOM", collectorNumber: "3", previous: 4, current: 9, delta: 5 },
      ],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].setCode).toBe("LTR");
    expect(rows[0].up).toBe(6);
    expect(rows[0].down).toBe(-3);
    expect(rows[0].memberCodes).toEqual(["LTR"]);
  });

  it("rolls up catalog-visible family sets and skips hidden subsets", () => {
    const catalogSets = [
      { setCode: "LTR", setType: "draft_innovation", familyRoot: "LTR", familyMembers: ["LTR", "LTC", "TLTR", "PLTR"] },
      { setCode: "LTC", setType: "commander", familyRoot: "LTR", familyMembers: ["LTR", "LTC", "TLTR", "PLTR"] },
      { setCode: "TLTR", setType: "token", familyRoot: "LTR", familyMembers: ["LTR", "LTC", "TLTR", "PLTR"] },
    ];
    const cards = [
      { setCode: "LTR", collectorNumber: "1", previous: 10, current: 16, delta: 6 },
      { setCode: "LTC", collectorNumber: "2", previous: 8, current: 5, delta: -3 },
      { setCode: "TLTR", collectorNumber: "9", previous: 4, current: 20, delta: 16 },
      { setCode: "PLTR", collectorNumber: "4", previous: 2, current: 7, delta: 5 },
      { setCode: "MOM", collectorNumber: "3", previous: 4, current: 9, delta: 5 },
    ];
    const rows = favoriteSetDayRows(
      [{ setCode: "LTR", familyRoot: "LTR", familyMembers: ["LTR", "LTC", "TLTR", "PLTR"] }],
      cards,
      { catalogSets },
    );
    expect(rows[0].memberCodes).toEqual(["LTR", "LTC"]);
    expect(rows[0].up).toBe(6);
    expect(rows[0].down).toBe(-3);

    const withSubsets = favoriteSetDayRows(
      [{ setCode: "LTR", familyRoot: "LTR", familyMembers: ["LTR", "LTC", "TLTR", "PLTR"] }],
      cards,
      { catalogSets, includeHiddenSubsets: true },
    );
    expect(withSubsets[0].memberCodes).toEqual(["LTR", "LTC", "TLTR"]);
    expect(withSubsets[0].up).toBe(22);
  });
});

describe("favoriteArtStyleDayRows", () => {
  it("builds a +/− tile per favourite art style", () => {
    const rows = favoriteArtStyleDayRows(
      [{ setCode: "LTR", artStyle: "Showcase" }],
      [
        { setCode: "LTR", artStyle: "Showcase", collectorNumber: "1", previous: 10, current: 16, delta: 6 },
        { setCode: "LTR", artStyle: "Showcase", collectorNumber: "2", previous: 4, current: 2, delta: -2 },
        { setCode: "LTR", artStyle: "Regular", collectorNumber: "3", previous: 8, current: 20, delta: 12 },
      ],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].up).toBe(6);
    expect(rows[0].down).toBe(-2);
  });
});

describe("favoriteCardDayRows", () => {
  it("matches last-sync owned diffs onto favourite cards", () => {
    const rows = favoriteCardDayRows(
      [{ setCode: "LTR", collectorNumber: "1", finish: 0, name: "Gandalf" }],
      [{
        setCode: "LTR",
        collectorNumber: "1",
        finishId: 0,
        previous: 11,
        current: 18,
        delta: 7,
        imageUri: "https://example.com/g.jpg",
      }],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].up).toBe(7);
    expect(rows[0].down).toBe(0);
    expect(rows[0].imageUri).toBe("https://example.com/g.jpg");
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
