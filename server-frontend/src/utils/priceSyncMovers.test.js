import { describe, expect, it } from "vitest";
import {
  aggregateArtStyleMovers,
  cardsForArtStyle,
  cardsForDeckPrints,
  changeMoveCounts,
  deckImpactRows,
  deckImpactTotals,
  deckUnchangedCount,
  collectPriceSyncCards,
  collectPriceSyncStyleRows,
  firstPriceSyncCards,
  favoriteArtStyleDayRows,
  familySetCounts,
  favoriteSetDayRows,
  favoriteSetsDayTotal,
  favoriteCardDayRows,
  moverRowToTileCard,
  priceChangeStrength,
  priceChangeStyle,
  priceChangeTinted,
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

describe("cardsForDeckPrints", () => {
  it("keeps sync rows for owned deck prints and ignores the rest", () => {
    const cards = [
      { setCode: "LTR", collectorNumber: "10", finishId: 0, delta: 0.5, name: "Sol Ring" },
      { setCode: "LTR", collectorNumber: "11", finishId: 1, delta: -0.2, name: "Arcane Signet" },
      { setCode: "MH3", collectorNumber: "1", finishId: 0, delta: 1, name: "Other" },
    ];
    const prints = [
      { setCode: "ltr", collectorNumber: "10", finish: 0, ownedQty: 1 },
    ];
    expect(cardsForDeckPrints(cards, prints)).toEqual([
      expect.objectContaining({ name: "Sol Ring", ownedQty: 1 }),
    ]);
  });

  it("scales a print's move by the copies the deck owns", () => {
    const rows = deckImpactRows(
      [{
        setCode: "LTR",
        collectorNumber: "10",
        finishId: 0,
        previous: 1,
        current: 1.5,
        delta: 0.5,
        name: "Sol Ring",
      }],
      [{ setCode: "LTR", collectorNumber: "10", finish: 0, ownedQty: 2 }],
    );
    expect(rows).toEqual([
      expect.objectContaining({
        name: "Sol Ring",
        ownedQty: 2,
        unitDelta: 0.5,
        previous: 1,
        current: 1.5,
        delta: 1,
      }),
    ]);
    expect(deckImpactTotals(rows)).toEqual({ up: 1, down: 0, delta: 1 });
  });

  it("counts prints that did not move", () => {
    const prints = [
      { setCode: "LTR", collectorNumber: "10", finish: 0 },
      { setCode: "LTR", collectorNumber: "11", finish: 0 },
      { setCode: "LTR", collectorNumber: "12", finish: 0 },
    ];
    const rows = [
      { setCode: "LTR", collectorNumber: "10", finishId: 0, delta: 0.5 },
      { setCode: "LTR", collectorNumber: "11", finishId: 0, delta: -0.2 },
    ];
    expect(changeMoveCounts(rows)).toMatchObject({ upCount: 1, downCount: 1 });
    expect(deckUnchangedCount(prints, rows)).toBe(1);
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

describe("familySetCounts", () => {
  it("sums owned and catalog counts across the visible family", () => {
    const counts = familySetCounts(
      ["LTR", "LTC"],
      [
        { setCode: "LTR", ownedCount: 831, catalogCount: 834 },
        { setCode: "LTC", ownedCount: 40, catalogCount: 50 },
        { setCode: "TLTR", ownedCount: 9, catalogCount: 9 },
      ],
    );
    expect(counts).toEqual({ ownedCount: 871, catalogCount: 884 });
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
    expect(rows[0].upCount).toBe(1);
    expect(rows[0].downCount).toBe(1);
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

describe("favoriteSetsDayTotal", () => {
  it("sums each owned card once when favourite sets share a family", () => {
    const total = favoriteSetsDayTotal(
      [
        { setCode: "LTR", memberCodes: ["LTR", "LTC"] },
        { setCode: "LTC", memberCodes: ["LTR", "LTC"] },
      ],
      [
        { setCode: "LTR", collectorNumber: "1", finish: 0, previous: 1, current: 3, delta: 2 },
        { setCode: "LTC", collectorNumber: "2", finish: 0, previous: 5, current: 4, delta: -1 },
        { setCode: "LTR", collectorNumber: "1", finish: 0, previous: 1, current: 3, delta: 2 },
        { setCode: "MOM", collectorNumber: "3", finish: 0, previous: 2, current: 9, delta: 7 },
      ],
    );
    expect(total.up).toBe(2);
    expect(total.down).toBe(-1);
    expect(total.delta).toBe(1);
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
      [{
        setCode: "LTR",
        collectorNumber: "1",
        finish: 0,
        name: "Gandalf",
        cardmarketUrl: "https://www.cardmarket.com/en/Magic/Products?idProduct=1",
      }],
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
    expect(rows[0].current).toBe(18);
    expect(rows[0].imageUri).toBe("https://example.com/g.jpg");
    expect(rows[0].cardmarketUrl).toBe("https://www.cardmarket.com/en/Magic/Products?idProduct=1");
  });

  it("keeps the collection price when a favourite card did not move", () => {
    const rows = favoriteCardDayRows(
      [{ setCode: "LTR", collectorNumber: "2", finish: 0, name: "Sam", currentValue: 4.5 }],
      [],
    );
    expect(rows[0].current).toBe(4.5);
    expect(rows[0].delta).toBe(0);
  });
});

describe("priceChangeStrength", () => {
  it("grows with the size of the move and caps at one", () => {
    expect(priceChangeStrength(0)).toBe(0);
    expect(priceChangeStrength(1)).toBeGreaterThan(priceChangeStrength(0.2));
    expect(priceChangeStrength(20)).toBeGreaterThan(priceChangeStrength(1));
    expect(priceChangeStrength(-40)).toBe(1);
    expect(priceChangeStrength(2)).toBe(priceChangeStrength(-2));
  });

  it("skips a home background for moves under 20 cents", () => {
    expect(priceChangeTinted(0.19, 0.2)).toBe(false);
    expect(priceChangeTinted(-0.2, 0.2)).toBe(true);
    expect(priceChangeStyle(0.19, { floor: 0.2 })).toBeUndefined();
    expect(priceChangeStyle(0.2, { floor: 0.2 })).toEqual({
      "--change-strength": priceChangeStrength(0.2).toFixed(2),
    });
  });
});

describe("rankMoverRows", () => {
  it("keeps every move over one euro, or the top 25 when fewer qualify", () => {
    const many = [
      ...Array.from({ length: 30 }, (_, index) => ({ delta: 31 - index, percent: 1 })),
      ...Array.from({ length: 28 }, (_, index) => ({ delta: -(31 - index), percent: -1 })),
    ];
    const ranked = rankMoverRows(many, { limit: 25, minChange: 1 });
    expect(ranked.risers.map((row) => row.delta)).toEqual(
      Array.from({ length: 30 }, (_, index) => 31 - index),
    );
    expect(ranked.fallers.map((row) => row.delta)).toEqual(
      Array.from({ length: 28 }, (_, index) => -(31 - index)),
    );

    const few = [
      { delta: 4, percent: 1 },
      { delta: 1, percent: 1 },
      ...Array.from({ length: 30 }, () => ({ delta: 0.4, percent: 1 })),
      { delta: -3, percent: -1 },
      { delta: -1, percent: -1 },
      ...Array.from({ length: 30 }, () => ({ delta: -0.2, percent: -1 })),
    ];
    const padded = rankMoverRows(few, { limit: 25, minChange: 1 });
    expect(padded.risers).toHaveLength(25);
    expect(padded.risers[0].delta).toBe(4);
    expect(padded.risers[1].delta).toBe(1);
    expect(padded.fallers).toHaveLength(25);
    expect(padded.fallers[0].delta).toBe(-3);
    expect(padded.fallers[1].delta).toBe(-1);
  });

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
