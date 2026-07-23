import { describe, expect, it } from "vitest";
import { hasSelectableArtStyles } from "./format.js";

describe("hasSelectableArtStyles", () => {
  it("is false when empty", () => {
    expect(hasSelectableArtStyles([])).toBe(false);
    expect(hasSelectableArtStyles(null)).toBe(false);
  });

  it("is false when only the default All style exists", () => {
    expect(hasSelectableArtStyles(["All"])).toBe(false);
    expect(hasSelectableArtStyles([{ artStyle: "All" }])).toBe(false);
    expect(hasSelectableArtStyles([{ artStyle: "all" }])).toBe(false);
  });

  it("is true when additional styles exist", () => {
    expect(hasSelectableArtStyles(["All", "Showcase"])).toBe(true);
    expect(hasSelectableArtStyles([{ artStyle: "Showcase" }])).toBe(true);
  });
});
