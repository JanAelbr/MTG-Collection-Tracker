import { describe, expect, it } from "vitest";
import {
  favoriteArtStyleKey,
  favoriteCardKey,
  cardFavoriteKeyFromCard,
} from "./favorites.js";

describe("favorites keys", () => {
  it("builds card keys from set, number, and finish", () => {
    expect(favoriteCardKey("ltr", "1", 1)).toBe("LTR|1|1");
    expect(cardFavoriteKeyFromCard({ setCode: "LTR", collectorNumber: "2", finish: 0 })).toBe(
      "LTR|2|0",
    );
  });

  it("builds art style keys", () => {
    expect(favoriteArtStyleKey("mb2", "Showcase")).toBe("MB2|Showcase");
    expect(favoriteArtStyleKey("", "Showcase")).toBe("");
  });
});
