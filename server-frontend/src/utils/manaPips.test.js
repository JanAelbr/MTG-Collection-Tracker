import { describe, expect, it } from "vitest";
import {
  buildColorPipBreakdown,
  buildManaSourceStack,
  countPipsFromManaCost,
  filterCardsByPipColor,
  filterManaSourcesByColor,
  cardManaProduction,
  manaSourceCategory,
  pipWeightForSymbol,
} from "./manaPips.js";

describe("pipWeightForSymbol", () => {
  it("counts single colors and phyrexian", () => {
    expect(pipWeightForSymbol("U")).toEqual([{ color: "U", weight: 1 }]);
    expect(pipWeightForSymbol("W/P")).toEqual([{ color: "W", weight: 1 }]);
  });

  it("splits hybrid pips evenly", () => {
    expect(pipWeightForSymbol("W/U")).toEqual([
      { color: "W", weight: 0.5 },
      { color: "U", weight: 0.5 },
    ]);
  });

  it("ignores generic mana but counts colorless pips", () => {
    expect(pipWeightForSymbol("2")).toEqual([]);
    expect(pipWeightForSymbol("X")).toEqual([]);
    expect(pipWeightForSymbol("C")).toEqual([{ color: "C", weight: 1 }]);
  });
});

describe("countPipsFromManaCost", () => {
  it("tallies colored symbols across a cost", () => {
    expect(countPipsFromManaCost("{2}{U}{U}{R}")).toEqual({
      W: 0,
      U: 2,
      B: 0,
      R: 1,
      G: 0,
      C: 0,
    });
  });

  it("handles hybrid as half pips", () => {
    expect(countPipsFromManaCost("{W/U}{G}")).toEqual({
      W: 0.5,
      U: 0.5,
      B: 0,
      R: 0,
      G: 1,
      C: 0,
    });
  });

  it("counts colorless pips", () => {
    expect(countPipsFromManaCost("{1}{C}{C}")).toEqual({
      W: 0,
      U: 0,
      B: 0,
      R: 0,
      G: 0,
      C: 2,
    });
  });
});

describe("buildColorPipBreakdown", () => {
  it("weights by qty and skips lands and sideboard", () => {
    const { total, rows, counts } = buildColorPipBreakdown([
      { section: "main", cardType: "creature", manaCost: "{1}{U}{U}", qty: 2 },
      { section: "commander", cardType: "creature", manaCost: "{2}{U}{R}", qty: 1 },
      { section: "main", cardType: "land", manaCost: "", typeLine: "Basic Land — Island", qty: 10 },
      { section: "sideboard", cardType: "instant", manaCost: "{R}{R}{R}", qty: 3 },
    ]);
    expect(counts.U).toBe(5);
    expect(counts.R).toBe(1);
    expect(total).toBe(6);
    expect(rows.map((row) => row.id)).toEqual(["U", "R"]);
  });

  it("filters cards that contain a pip color", () => {
    const cards = [
      { section: "main", cardType: "instant", manaCost: "{U}", cardName: "Counter", qty: 1 },
      { section: "main", cardType: "sorcery", manaCost: "{R}", cardName: "Bolt", qty: 1 },
    ];
    expect(filterCardsByPipColor(cards, "U").map((card) => card.cardName)).toEqual(["Counter"]);
  });
});

describe("cardManaProduction", () => {
  it("reads basic land types from the type line", () => {
    expect(cardManaProduction({
      typeLine: "Basic Land — Island",
      oracleText: "({T}: Add {U}.)",
    })).toEqual({
      colors: ["U"],
      anyColor: false,
      hasColorless: false,
    });
  });

  it("reads dual land types and oracle choices", () => {
    expect(cardManaProduction({
      typeLine: "Land — Plains Island",
      oracleText: "{T}: Add {W} or {U}.",
    }).colors).toEqual(["W", "U"]);
  });

  it("detects any-color lands", () => {
    expect(cardManaProduction({
      typeLine: "Land",
      oracleText: "{T}: Add one mana of any color in your commander's color identity.",
      cardName: "Command Tower",
    })).toMatchObject({
      colors: [],
      anyColor: true,
    });
  });

  it("detects creature and artifact mana makers", () => {
    expect(cardManaProduction({
      cardType: "creature",
      typeLine: "Creature — Elf Druid",
      oracleText: "{T}: Add {G}.",
    }).colors).toEqual(["G"]);

    expect(cardManaProduction({
      cardType: "artifact",
      typeLine: "Artifact",
      oracleText: "{T}: Add one mana of any color in your commander's color identity.",
    }).anyColor).toBe(true);
  });

  it("detects colorless-only lands", () => {
    expect(cardManaProduction({
      typeLine: "Land",
      oracleText: "{T}: Add {C}{C}.",
    })).toMatchObject({
      colors: ["C"],
      anyColor: false,
      hasColorless: true,
    });
  });
});

describe("manaSourceCategory", () => {
  it("splits basic lands from other lands and nonland types", () => {
    expect(manaSourceCategory({
      cardType: "land",
      typeLine: "Basic Land — Forest",
      isBasicLand: true,
    })).toBe("basic");
    expect(manaSourceCategory({
      cardType: "land",
      typeLine: "Land",
    })).toBe("land");
    expect(manaSourceCategory({
      cardType: "creature",
      typeLine: "Creature — Elf Druid",
    })).toBe("creature");
    expect(manaSourceCategory({
      cardType: "artifact",
      typeLine: "Artifact",
    })).toBe("artifact");
  });
});

describe("buildManaSourceStack", () => {
  it("stacks basic lands, other lands, and nonland sources", () => {
    const stack = buildManaSourceStack([
      { section: "main", cardType: "creature", manaCost: "{W}{U}{G}", qty: 1 },
      {
        section: "main",
        cardType: "land",
        typeLine: "Basic Land — Plains",
        oracleText: "({T}: Add {W}.)",
        isBasicLand: true,
        qty: 2,
      },
      {
        section: "main",
        cardType: "land",
        typeLine: "Land",
        oracleText: "{T}: Add one mana of any color.",
        cardName: "Command Tower",
        qty: 1,
      },
      {
        section: "main",
        cardType: "creature",
        typeLine: "Creature — Elf Druid",
        oracleText: "{T}: Add {G}.",
        cardName: "Llanowar Elves",
        qty: 1,
      },
      {
        section: "main",
        cardType: "artifact",
        typeLine: "Artifact",
        oracleText: "{T}: Add one mana of any color in your commander's color identity.",
        cardName: "Arcane Signet",
        qty: 1,
      },
    ]);

    expect(stack.rows.map((row) => row.label)).toEqual(["White", "Blue", "Green"]);
    const white = stack.rows.find((row) => row.id === "W");
    const green = stack.rows.find((row) => row.id === "G");
    expect(white.stacks).toEqual([
      { id: "basic", label: "Basic lands", count: 2, fixed: 2, any: 0 },
      { id: "land", label: "Other lands", count: 1, fixed: 0, any: 1 },
      { id: "artifact", label: "Artifacts", count: 1, fixed: 0, any: 1 },
    ]);
    expect(green.stacks.find((item) => item.id === "creature").count).toBe(1);
    expect(stack.anyColorCount).toBe(2);
    expect(white.pipPercent).toBe(33);
    expect(white.sourcePercent).toBeGreaterThan(0);
    expect(white.ratio).toBeTypeOf("number");
  });

  it("does not spread any-color sources onto unused colors", () => {
    const stack = buildManaSourceStack([
      { section: "main", cardType: "creature", manaCost: "{R}{R}", qty: 1 },
      {
        section: "main",
        cardType: "land",
        typeLine: "Land",
        oracleText: "{T}: Add one mana of any color.",
        qty: 1,
      },
      {
        section: "main",
        cardType: "land",
        typeLine: "Basic Land — Mountain",
        oracleText: "({T}: Add {R}.)",
        isBasicLand: true,
        qty: 1,
      },
    ]);
    expect(stack.rows.map((row) => row.id)).toEqual(["R"]);
    expect(stack.rows[0].total).toBe(2);
  });

  it("filters stacked sources for drill-down", () => {
    const stack = buildManaSourceStack([
      { section: "main", cardType: "creature", manaCost: "{G}", qty: 1 },
      {
        section: "main",
        cardType: "land",
        cardName: "Forest",
        setCode: "LTR",
        collectorNumber: "1",
        finish: 0,
        typeLine: "Basic Land — Forest",
        oracleText: "({T}: Add {G}.)",
        isBasicLand: true,
        qty: 1,
      },
      {
        section: "main",
        cardType: "creature",
        cardName: "Llanowar Elves",
        setCode: "LTR",
        collectorNumber: "2",
        finish: 0,
        typeLine: "Creature — Elf Druid",
        oracleText: "{T}: Add {G}.",
        qty: 1,
      },
    ]);
    expect(filterManaSourcesByColor(stack, "G", "creature").map((card) => card.cardName)).toEqual([
      "Llanowar Elves",
    ]);
  });
});
