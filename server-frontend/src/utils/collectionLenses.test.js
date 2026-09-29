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

  it("keeps Unique active when a finish filter is also set", () => {
    expect(detectActiveLens({
      lensId: "unique",
      ownedFilter: "missing-number",
      foilFilter: "foil",
      sort: "number",
      sortDir: "asc",
      typeFilter: "all",
      colorFilters: [],
      searchQuery: "",
    })).toBe("unique");
    expect(detectActiveLens({
      ownedFilter: "missing-number",
      foilFilter: "nonfoil",
      sort: "number",
      sortDir: "asc",
      typeFilter: "all",
      colorFilters: [],
      searchQuery: "",
    })).toBe("unique");
  });
});
