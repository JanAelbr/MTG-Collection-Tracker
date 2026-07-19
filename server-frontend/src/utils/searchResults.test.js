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

  it("displays strategy value with fallback", () => {
    const card = {
      currentValue: 1.25,
      valuesByStrategy: { trend: 2.5 },
    };
    expect(displayCardValue(card, "trend")).toBe("€ 2.50");
    expect(displayCardValue(card, "avg")).toBe("€ 1.25");
    expect(displayCardValue(null, "trend")).toBe("—");
  });
});
