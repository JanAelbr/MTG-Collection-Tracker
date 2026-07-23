import { describe, expect, it } from "vitest";
import {
  isManaCostToken,
  nameMatchScore,
  normalizeCardTitle,
  stripTrailingManaCost,
  titleHintIsUsable,
  titlesLikelyMatch,
  tokensFuzzyEqual,
} from "./cardTitle";

describe("cardTitle matching", () => {
  it("normalizes titles", () => {
    expect(normalizeCardTitle("  Lightning  Bolt! ")).toBe("LIGHTNING BOLT");
  });

  it("strips trailing mana cost OCR", () => {
    expect(stripTrailingManaCost("Lightning Bolt 1R")).toBe("Lightning Bolt");
    expect(stripTrailingManaCost("Counterspell UU")).toBe("Counterspell");
    expect(stripTrailingManaCost("Sol Ring 1")).toBe("Sol Ring");
    expect(stripTrailingManaCost("Birds of Paradise G")).toBe("Birds of Paradise");
    expect(stripTrailingManaCost("Cryptic Command 1UUU")).toBe("Cryptic Command");
    expect(stripTrailingManaCost("Sacred Foundry2WR")).toBe("Sacred Foundry");
    expect(normalizeCardTitle("Lightning Bolt IR")).toBe("LIGHTNING BOLT");
  });

  it("strips edge punctuation noise from OCR titles", () => {
    expect(normalizeCardTitle(". Bloodthirsty Aerialis -")).toBe("BLOODTHIRSTY AERIALIS");
    expect(stripTrailingManaCost(". Bloodthirsty Aerialis -")).toBe("Bloodthirsty Aerialis");
  });

  it("fuzzy-matches truncated OCR tokens", () => {
    expect(tokensFuzzyEqual("AERIALIS", "AERIALIST")).toBe(true);
    expect(titlesLikelyMatch(". Bloodthirsty Aerialis -", "Bloodthirsty Aerialist")).toBe(true);
    expect(nameMatchScore(". Bloodthirsty Aerialis -", "Bloodthirsty Aerialist")).toBeGreaterThan(0.75);
  });

  it("detects mana cost tokens", () => {
    expect(isManaCostToken("1R")).toBe(true);
    expect(isManaCostToken("UU")).toBe(true);
    expect(isManaCostToken("Bolt")).toBe(false);
  });

  it("treats empty OCR titles as non-blocking", () => {
    expect(titleHintIsUsable("")).toBe(false);
    expect(titlesLikelyMatch("", "Lightning Bolt")).toBe(true);
  });

  it("matches close OCR titles to catalog names", () => {
    expect(titlesLikelyMatch("LIGHTNING BOLT", "Lightning Bolt")).toBe(true);
    expect(titlesLikelyMatch("Sacred Foundry", "Sacred Foundry")).toBe(true);
    expect(titlesLikelyMatch("SOL RING", "Sol Ring")).toBe(true);
    expect(titlesLikelyMatch("Lightning Bolt 1R", "Lightning Bolt")).toBe(true);
  });

  it("rejects clearly different titles", () => {
    expect(titlesLikelyMatch("Counterspell", "Lightning Bolt")).toBe(false);
    expect(titlesLikelyMatch("Birds of Paradise", "Sol Ring")).toBe(false);
  });
});
