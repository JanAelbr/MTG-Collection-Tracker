import { describe, expect, it } from "vitest";
import {
  displayCardValue,
  formatPowerToughness,
  formatRarityLabel,
  formatTypeLabel,
} from "./searchResults.js";

describe("searchResults helpers", () => {
  it("formats power/toughness with fallbacks", () => {
    expect(formatPowerToughness({ power: "3", toughness: "2" })).toBe("3/2");
    expect(formatPowerToughness({ power: "3" })).toBe("3/—");
    expect(formatPowerToughness({ toughness: "4" })).toBe("—/4");
    expect(formatPowerToughness({})).toBe("—");
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
});
