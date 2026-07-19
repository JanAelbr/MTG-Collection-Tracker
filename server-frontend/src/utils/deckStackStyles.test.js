import { describe, expect, it } from "vitest";
import {
  manaSymbolUrl,
  parseManaCostSymbols,
  scryfallSymbolSlug,
} from "./deckStackStyles.js";

describe("parseManaCostSymbols", () => {
  it("returns empty array for blank costs", () => {
    expect(parseManaCostSymbols("")).toEqual([]);
    expect(parseManaCostSymbols(null)).toEqual([]);
  });

  it("extracts single and generic mana symbols", () => {
    expect(parseManaCostSymbols("{W}{U}{2}")).toEqual(["W", "U", "2"]);
  });

  it("extracts hybrid and phyrexian tokens intact", () => {
    expect(parseManaCostSymbols("{W/U}{2/W}{U/B/R}{W/P}")).toEqual([
      "W/U",
      "2/W",
      "U/B/R",
      "W/P",
    ]);
  });
});

describe("scryfallSymbolSlug", () => {
  it("removes slashes from hybrid and phyrexian tokens", () => {
    expect(scryfallSymbolSlug("W/U")).toBe("WU");
    expect(scryfallSymbolSlug("2/W")).toBe("2W");
    expect(scryfallSymbolSlug("W/P")).toBe("WP");
    expect(scryfallSymbolSlug("P/W")).toBe("PW");
    expect(scryfallSymbolSlug("U/B/R")).toBe("UBR");
  });

  it("leaves simple symbols unchanged", () => {
    expect(scryfallSymbolSlug("W")).toBe("W");
    expect(scryfallSymbolSlug("2")).toBe("2");
    expect(scryfallSymbolSlug("X")).toBe("X");
  });
});

describe("manaSymbolUrl", () => {
  it("builds Scryfall CDN URLs for hybrid symbols", () => {
    expect(manaSymbolUrl("W/U")).toBe("https://svgs.scryfall.io/card-symbols/WU.svg");
    expect(manaSymbolUrl("2/W")).toBe("https://svgs.scryfall.io/card-symbols/2W.svg");
    expect(manaSymbolUrl("W/P")).toBe("https://svgs.scryfall.io/card-symbols/WP.svg");
  });

  it("builds Scryfall CDN URLs for simple symbols", () => {
    expect(manaSymbolUrl("W")).toBe("https://svgs.scryfall.io/card-symbols/W.svg");
    expect(manaSymbolUrl("2")).toBe("https://svgs.scryfall.io/card-symbols/2.svg");
  });
});
