import { describe, expect, it } from "vitest";
import {
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
    expect(normalizeGroupByLevels("none")).toEqual([]);
  });
});

describe("groupSearchCards", () => {
  it("returns a single bucket when grouping is off", () => {
    const cards = [{ name: "A" }, { name: "B" }];
    expect(groupSearchCards(cards, "none")).toMatchObject([
      { key: "all", label: "All", cards, groups: [] },
    ]);
  });

  it("groups by type, role, color identity, rarity, and set", () => {
    const cards = [
      {
        name: "Bolt",
        cardType: "instant",
        roles: ["removal"],
        colorIdentity: ["R"],
        rarity: "common",
        setCode: "M21",
      },
      {
        name: "Bear",
        cardType: "creature",
        roles: ["ramp"],
        colorIdentity: ["G"],
        rarity: "common",
        setCode: "M21",
      },
      {
        name: "Sol Ring",
        cardType: "artifact",
        roles: [],
        colorIdentity: [],
        rarity: "uncommon",
        setCode: "C21",
      },
    ];

    expect(groupSearchCards(cards, "type").map((group) => group.key)).toEqual([
      "creature",
      "artifact",
      "instant",
    ]);
    expect(groupSearchCards(cards, "role").map((group) => group.label)).toEqual([
      "Ramp",
      "Removal",
      "No role",
    ]);
    expect(groupSearchCards(cards, "colorIdentity").map((group) => group.label)).toEqual([
      "Red",
      "Green",
      "Colorless",
    ]);
    expect(groupSearchCards(cards, "rarity").map((group) => group.label)).toEqual([
      "Common",
      "Uncommon",
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
