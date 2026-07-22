import { describe, expect, it } from "vitest";
import {
  createEmptyArtStyleRuleRow,
  moveArtStyleRule,
  nextArtStyleLabelPrefix,
  reorderArtStyleRules,
} from "./artStyleRules.js";

describe("artStyleRules helpers", () => {
  it("builds the next numbered label prefix", () => {
    expect(nextArtStyleLabelPrefix([])).toBe("01. ");
    expect(nextArtStyleLabelPrefix([
      { name: "01. Main set" },
      { name: "All" },
      { name: "03. Showcase" },
    ])).toBe("04. ");
    expect(nextArtStyleLabelPrefix([{ name: "9. Promo" }])).toBe("10. ");
  });

  it("reorders rules by drag indices", () => {
    const rows = [
      createEmptyArtStyleRuleRow({ name: "01. A" }),
      createEmptyArtStyleRuleRow({ name: "02. B" }),
      createEmptyArtStyleRuleRow({ name: "03. C" }),
    ];
    const moved = reorderArtStyleRules(rows, 0, 2);
    expect(moved.map((row) => row.name)).toEqual(["02. B", "03. C", "01. A"]);
    expect(reorderArtStyleRules(rows, 1, 1)).toBe(rows);
  });

  it("moves rules one step with moveArtStyleRule", () => {
    const rows = [
      createEmptyArtStyleRuleRow({ name: "01. A" }),
      createEmptyArtStyleRuleRow({ name: "02. B" }),
    ];
    expect(moveArtStyleRule(rows, 0, 1).map((row) => row.name)).toEqual(["02. B", "01. A"]);
    expect(moveArtStyleRule(rows, 0, -1)).toBe(rows);
  });
});
