import { describe, expect, it } from "vitest";
import {
  cardSubtypeLabel,
  colorIdentityPipsFromKey,
  displayCardValue,
  formatPowerToughness,
  formatRarityLabel,
  formatTypeLabel,
  groupSearchCards,
  normalizeGroupByLevels,
} from "./searchResults.js";

describe("searchResults helpers", () => {
  it("formats power/toughness with fallbacks", () => {
    expect(formatPowerToughness({ power: "3", toughness: "2" })).toBe("3/2");
    expect(formatPowerToughness({ power: "3" })).toBe("3/—");
    expect(formatPowerToughness({ toughness: "4" })).toBe("—/4");
    expect(formatPowerToughness({})).toBe("—");
  });

  it("splits color identity group keys into mana pips", () => {
    expect(colorIdentityPipsFromKey("WU")).toEqual(["W", "U"]);
    expect(colorIdentityPipsFromKey("C")).toEqual([]);
    expect(colorIdentityPipsFromKey("")).toEqual([]);
  });

  it("prefers cardType over typeLine", () => {
    expect(formatTypeLabel({
      cardType: "instant",
      typeLine: "Instant — Damage",
    })).toBe("Instant");
    expect(formatTypeLabel({ typeLine: "Creature — Human Wizard" })).toBe("Creature");
    expect(formatTypeLabel({})).toBe("—");
  });

  it("maps rarity labels", () => {
    expect(formatRarityLabel("mythic")).toBe("Mythic");
    expect(formatRarityLabel("")).toBe("—");
  });

  it("displays gallery price pair without currentValue fallback", () => {
    const card = {
      currentValue: 1.25,
      valuesByStrategy: { trend: 2.5, low: 1.0, avg: 3.0 },
    };
    expect(displayCardValue(card)).toBe("€1.00 ~ €2.50");
    expect(displayCardValue({
      valuesByStrategy: { low: 5, trend: 4 },
    })).toBe("€5.00");
    expect(displayCardValue(null)).toBe("—");
  });

  it("normalizes nested group-by levels", () => {
    expect(normalizeGroupByLevels("role,colorIdentity,rarity")).toEqual([
      "role",
      "colorIdentity",
      "rarity",
    ]);
    expect(normalizeGroupByLevels("role,role,set")).toEqual(["role", "set"]);
    expect(normalizeGroupByLevels("type,subtypes")).toEqual(["type", "subtype"]);
    expect(normalizeGroupByLevels("manavalue")).toEqual(["cmc"]);
    expect(normalizeGroupByLevels("none")).toEqual([]);
  });

  it("reads subtype text from type lines", () => {
    expect(cardSubtypeLabel({ typeLine: "Creature — Elf Druid" })).toBe("Elf Druid");
    expect(cardSubtypeLabel({ typeLine: "Enchantment — Aura" })).toBe("Aura");
    expect(cardSubtypeLabel({ typeLine: "Artifact — Equipment" })).toBe("Equipment");
    expect(cardSubtypeLabel({ typeLine: "Instant" })).toBe("");
    expect(cardSubtypeLabel({
      typeLine: "Creature — Human Wizard // Creature – Spirit",
    })).toBe("Human Wizard");
  });
});

describe("groupSearchCards", () => {
  it("returns a single bucket when grouping is off", () => {
    const cards = [{ name: "A" }, { name: "B" }];
    expect(groupSearchCards(cards, "none")).toMatchObject([
      { key: "all", label: "All", cards, groups: [] },
    ]);
  });

  it("groups by type, subtype, role, color identity, rarity, cmc, and set", () => {
    const cards = [
      {
        name: "Bolt",
        cardType: "instant",
        typeLine: "Instant",
        roles: ["removal"],
        colorIdentity: ["R"],
        rarity: "common",
        cmc: 1,
        setCode: "M21",
      },
      {
        name: "Bear",
        cardType: "creature",
        typeLine: "Creature — Bear",
        roles: ["ramp"],
        colorIdentity: ["G"],
        rarity: "common",
        cmc: 2,
        setCode: "M21",
      },
      {
        name: "Sol Ring",
        cardType: "artifact",
        typeLine: "Artifact",
        roles: [],
        colorIdentity: [],
        rarity: "uncommon",
        cmc: 1,
        setCode: "C21",
      },
      {
        name: "Sword",
        cardType: "artifact",
        typeLine: "Artifact — Equipment",
        roles: [],
        colorIdentity: [],
        rarity: "rare",
        cmc: 3,
        setCode: "C21",
      },
      {
        name: "Pacifism",
        cardType: "enchantment",
        typeLine: "Enchantment — Aura",
        roles: ["removal"],
        colorIdentity: ["W"],
        rarity: "common",
        cmc: 2,
        setCode: "M21",
      },
    ];

    expect(groupSearchCards(cards, "type").map((group) => group.key)).toEqual([
      "creature",
      "enchantment",
      "artifact",
      "instant",
    ]);
    expect(groupSearchCards(cards, "subtype").map((group) => group.label)).toEqual([
      "Aura",
      "Bear",
      "Equipment",
      "No subtype",
    ]);
    expect(groupSearchCards(cards, "role").map((group) => group.label)).toEqual([
      "Ramp",
      "Removal",
      "No role",
    ]);
    expect(groupSearchCards(cards, "colorIdentity").map((group) => group.label)).toEqual([
      "White",
      "Red",
      "Green",
      "Colorless",
    ]);
    expect(groupSearchCards(cards, "rarity").map((group) => group.label)).toEqual([
      "Common",
      "Uncommon",
      "Rare",
    ]);
    expect(groupSearchCards(cards, "cmc").map((group) => group.label)).toEqual([
      "CMC 1",
      "CMC 2",
      "CMC 3",
    ]);
    expect(groupSearchCards([
      { name: "Counterspell", colorIdentity: ["U", "B"] },
      { name: "Lightning Helix", colorIdentity: ["R", "W"] },
    ], "colorIdentity").map((group) => group.label)).toEqual([
      "Boros",
      "Dimir",
    ]);
    expect(groupSearchCards(cards, "set", {
      setLabelFor: (code) => (code === "M21" ? "Core 2021" : code),
    }).map((group) => group.label)).toEqual([
      "C21",
      "Core 2021",
    ]);
  });

  it("nests multiple group levels", () => {
    const cards = [
      { name: "A", roles: ["ramp"], colorIdentity: ["G"], rarity: "common" },
      { name: "B", roles: ["ramp"], colorIdentity: ["G"], rarity: "rare" },
      { name: "C", roles: ["removal"], colorIdentity: ["R"], rarity: "common" },
    ];
    const groups = groupSearchCards(cards, ["role", "colorIdentity", "rarity"]);
    expect(groups.map((group) => group.label)).toEqual(["Ramp", "Removal"]);
    expect(groups[0].groups).toHaveLength(1);
    expect(groups[0].groups[0].label).toBe("Green");
    expect(groups[0].groups[0].groups.map((group) => group.label)).toEqual([
      "Common",
      "Rare",
    ]);
    expect(groups[0].groups[0].groups[0].cards.map((card) => card.name)).toEqual(["A"]);
  });
});
