import { describe, expect, it } from "vitest";
import { searchFiltersFromRoute, searchRouteQuery } from "./setScope.js";

describe("search route helpers", () => {
  it("reads creature type from route query", () => {
    const filters = searchFiltersFromRoute({
      query: {
        q: "Frodo",
        creature: "Halfling",
        text: "scry",
      },
    });
    expect(filters.searchQuery).toBe("Frodo");
    expect(filters.creatureTypeQuery).toBe("Halfling");
    expect(filters.textSearchQuery).toBe("scry");
  });

  it("writes creature type to route query", () => {
    const query = searchRouteQuery({
      searchQuery: "Frodo",
      creatureTypeQuery: "Halfling",
      textSearchQuery: "scry",
    });
    expect(query).toEqual({
      q: "Frodo",
      creature: "Halfling",
      text: "scry",
    });
  });
});
