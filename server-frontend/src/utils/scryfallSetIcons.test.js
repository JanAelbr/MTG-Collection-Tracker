import { describe, expect, it } from "vitest";
import { mtgVectorsSetIconUri, mtgVectorsSymbolCode } from "./mtgVectors.js";
import { scryfallSetIconCode, scryfallSetIconUri } from "./scryfall.js";

describe("Secret Lair set icons", () => {
  it("maps SLD to the STAR mtg-vectors symbol", () => {
    expect(mtgVectorsSymbolCode("SLD")).toBe("STAR");
    expect(mtgVectorsSetIconUri("SLD", "common")).toContain("/STAR/C.svg");
  });

  it("maps SLD to Scryfall star.svg (there is no sld.svg)", () => {
    expect(scryfallSetIconCode("SLD")).toBe("star");
    expect(scryfallSetIconUri("SLD")).toBe("https://svgs.scryfall.io/sets/star.svg");
  });
});
