import { describe, expect, it } from "vitest";
import { COLLECTION_TYPE_ORDER } from "./collectionTypes";
import { POWER_COMPONENTS } from "./deckPower";
import {
  CARD_TYPE_COLORS,
  MANA_COLOR_HEX,
  RARITY_COLORS,
  ROLE_CHART_COLORS,
  TYPE_CHART_COLORS,
  rarityColor,
  typeChartColorIndex,
} from "./mtgTheme";

describe("mtgTheme", () => {
  it("exposes WUBRG mana hexes", () => {
    expect(MANA_COLOR_HEX.W).toMatch(/^#/);
    expect(MANA_COLOR_HEX.U).toMatch(/^#/);
    expect(MANA_COLOR_HEX.B).toMatch(/^#/);
    expect(MANA_COLOR_HEX.R).toMatch(/^#/);
    expect(MANA_COLOR_HEX.G).toMatch(/^#/);
  });

  it("maps rarity keys to metal palette", () => {
    expect(rarityColor("common")).toBe(RARITY_COLORS.common);
    expect(rarityColor("mythic")).toBe(RARITY_COLORS.mythic);
    expect(rarityColor("")).toBe(RARITY_COLORS.unknown);
  });

  it("keeps type chart colors aligned with collection type order", () => {
    expect(TYPE_CHART_COLORS).toHaveLength(COLLECTION_TYPE_ORDER.length + 1);
    COLLECTION_TYPE_ORDER.forEach((type, index) => {
      expect(typeChartColorIndex(type)).toBe(index);
      expect(TYPE_CHART_COLORS[index]).toBe(CARD_TYPE_COLORS[type] || CARD_TYPE_COLORS.other);
    });
    expect(typeChartColorIndex("other")).toBe(TYPE_CHART_COLORS.length - 1);
  });

  it("keeps role chart colors aligned with power components", () => {
    expect(ROLE_CHART_COLORS).toHaveLength(POWER_COMPONENTS.length);
  });
});
