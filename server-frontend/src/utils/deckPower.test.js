import { describe, expect, it } from "vitest";
import {
  bracketDescription,
  bracketLabel,
  componentScoreClass,
  formatComponentCount,
  groupProposalCards,
  powerCardRoute,
  slotLabel,
} from "./deckPower.js";

describe("deckPower helpers", () => {
  it("labels brackets and descriptions", () => {
    expect(bracketLabel(3)).toBe("Bracket 3");
    expect(bracketDescription(3)).toContain("Upgraded");
  });

  it("maps component scores to classes", () => {
    expect(componentScoreClass(90)).toBe("power-score-high");
    expect(componentScoreClass(60)).toBe("power-score-mid");
    expect(componentScoreClass(20)).toBe("power-score-low");
  });

  it("groups owned and suggested proposal cards", () => {
    const grouped = groupProposalCards([
      { name: "A", suggested: false },
      { name: "B", suggested: true },
    ]);
    expect(grouped.owned).toHaveLength(1);
    expect(grouped.suggested).toHaveLength(1);
  });

  it("labels generation slots", () => {
    expect(slotLabel("ramp")).toBe("Ramp");
    expect(slotLabel("unknown")).toBe("unknown");
  });

  it("formats component counts for display", () => {
    expect(formatComponentCount("tutors", { tutors: 0 })).toBe("0 cards");
    expect(formatComponentCount("tutors", { tutors: 1 })).toBe("1 card");
    expect(formatComponentCount("tutors", { tutors: 3 })).toBe("3 cards");
    expect(formatComponentCount("curve", {})).toBe("");
  });

  it("builds card detail routes for power previews", () => {
    expect(
      powerCardRoute({
        setCode: "LTR",
        collectorNumber: "1",
        finish: 0,
      }, "12"),
    ).toEqual({
      name: "card",
      params: { setCode: "LTR", collectorNumber: "1" },
      query: { finish: "0", deck: "12" },
    });
  });
});
