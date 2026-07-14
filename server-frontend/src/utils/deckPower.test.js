import { describe, expect, it } from "vitest";
import {
  bracketDescription,
  bracketLabel,
  componentScoreClass,
  formatBasicLandSummary,
  formatComponentCount,
  groupProposalBySlot,
  groupProposalByType,
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

  it("groups owned, suggested, and infinite basic lands", () => {
    const grouped = groupProposalCards([
      { name: "A", suggested: false },
      { name: "B", suggested: true },
      { name: "Island", infiniteBasic: true, qty: 12 },
    ]);
    expect(grouped.owned).toHaveLength(1);
    expect(grouped.suggested).toHaveLength(1);
    expect(grouped.basicLands).toHaveLength(1);
  });

  it("groups proposal cards by slot and summarizes basics", () => {
    const { slotGroups, basicLandSummary } = groupProposalBySlot([
      { name: "Ramp Rock", slot: "ramp", suggested: false },
      { name: "Read Card", slot: "draw", suggested: true },
      { name: "Island", infiniteBasic: true, qty: 10 },
      { name: "Plains", infiniteBasic: true, qty: 8 },
    ]);
    expect(slotGroups.map((group) => group.slot)).toEqual(["ramp", "draw"]);
    expect(slotGroups[0].cards).toHaveLength(1);
    expect(basicLandSummary).toEqual([
      { name: "Island", qty: 10 },
      { name: "Plains", qty: 8 },
    ]);
    expect(formatBasicLandSummary(basicLandSummary)).toBe("Island ×10, Plains ×8 (18 total)");
  });

  it("groups proposal cards by card type", () => {
    const { typeGroups } = groupProposalByType([
      { name: "Birds", cardType: "creature", suggested: false },
      { name: "Counterspell", cardType: "instant", suggested: true },
      { name: "Command Tower", cardType: "land", suggested: false },
      { name: "Island", infiniteBasic: true, qty: 10 },
    ]);
    expect(typeGroups.map((group) => group.type)).toEqual(["creature", "instant", "land"]);
    expect(typeGroups[0].cards).toHaveLength(1);
    expect(typeGroups[1].cards[0].name).toBe("Counterspell");
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
