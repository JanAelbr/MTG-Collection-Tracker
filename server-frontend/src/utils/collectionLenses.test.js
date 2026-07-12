import { describe, expect, it } from "vitest";
import { detectActiveLens, lensDefinition } from "./collectionLenses.js";

describe("collectionLenses", () => {
  it("returns lens definition by id", () => {
    expect(lensDefinition("missing")?.ownedFilter).toBe("unowned");
    expect(lensDefinition("foils")?.foilFilter).toBe("foil");
  });

  it("detects active lens from filters", () => {
    expect(detectActiveLens({
      ownedFilter: "unowned",
      foilFilter: "all",
      sort: "value",
      sortDir: "desc",
      typeFilter: "all",
      colorFilters: [],
      searchQuery: "",
    })).toBe("missing");
  });
});
