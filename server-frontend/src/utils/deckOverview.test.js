import { describe, expect, it } from "vitest";
import {
  buildDonutSegments,
  buildRoleBreakdown,
  buildTypeBreakdown,
  filterCardsByType,
  overviewTopCards,
} from "./deckOverview.js";

describe("deckOverview helpers", () => {
  it("builds type breakdown excluding commanders", () => {
    const { total, rows } = buildTypeBreakdown([
      { section: "commander", cardType: "creature", qty: 1 },
      { section: "main", cardType: "creature", qty: 20 },
      { section: "main", cardType: "land", qty: 36 },
      { section: "main", cardType: "instant", qty: 8 },
    ]);
    expect(total).toBe(64);
    expect(rows.map((row) => row.id)).toEqual(["creature", "instant", "land"]);
    expect(rows.find((row) => row.id === "land").count).toBe(36);
  });

  it("builds role breakdown from power counts", () => {
    const { total, rows } = buildRoleBreakdown({
      ramp: 10,
      draw: 8,
      interaction: 9,
      tutors: 2,
      fastMana: 1,
      gameChangers: 0,
      comboDensity: 0,
      curve: 50,
    });
    expect(total).toBe(30);
    expect(rows.map((row) => row.id)).toEqual([
      "ramp",
      "draw",
      "interaction",
      "tutors",
      "fastMana",
    ]);
    expect(rows[0].label).toBe("Ramp");
  });

  it("builds donut segments that cover the full ring", () => {
    const segments = buildDonutSegments([
      { id: "a", label: "A", count: 1 },
      { id: "b", label: "B", count: 1 },
    ]);
    expect(segments).toHaveLength(2);
    const covered = segments.reduce((sum, segment) => {
      const [drawn] = segment.dasharray.split(" ").map(Number);
      return sum + drawn;
    }, 0);
    expect(covered).toBeCloseTo(segments[0].circumference, 5);
  });

  it("filters main-deck cards by type for breakdown drill-down", () => {
    const cards = [
      { section: "commander", cardType: "creature", cardName: "Cmd", qty: 1 },
      { section: "main", cardType: "creature", cardName: "Bear", qty: 1 },
      { section: "main", cardType: "land", cardName: "Forest", qty: 1 },
      { section: "main", cardType: "creature", cardName: "Elf", qty: 1 },
    ];
    expect(filterCardsByType(cards, "creature").map((card) => card.cardName)).toEqual([
      "Bear",
      "Elf",
    ]);
    expect(filterCardsByType(cards, "land")).toHaveLength(1);
  });

  it("returns top five valued cards", () => {
    const cards = Array.from({ length: 8 }, (_, index) => ({
      section: "main",
      inCatalog: true,
      imageUri: `https://example.com/${index}.jpg`,
      currentValue: 10 - index,
      cardName: `Card ${index}`,
      setCode: "LTR",
      collectorNumber: String(index + 1),
    }));
    const top = overviewTopCards(cards);
    expect(top).toHaveLength(5);
    expect(top[0].cardName).toBe("Card 0");
    expect(top[4].cardName).toBe("Card 4");
  });
});
