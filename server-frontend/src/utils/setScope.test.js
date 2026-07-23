import { describe, expect, it } from "vitest";
import {
  collectionScopeFromRoute,
  collectionScopeToQuery,
  familyFromRoute,
  searchFiltersFromRoute,
  searchRouteQuery,
  setScopeToQuery,
} from "./setScope.js";

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

  it("defaults ownership to owned and maps legacy unowned to all", () => {
    expect(searchFiltersFromRoute({ query: {} }).ownedFilter).toBe("owned");
    expect(searchFiltersFromRoute({ query: { owned: "all" } }).ownedFilter).toBe("all");
    expect(searchFiltersFromRoute({ query: { owned: "unowned" } }).ownedFilter).toBe("all");
    expect(searchRouteQuery({ ownedFilter: "owned", searchQuery: "x" })).toEqual({ q: "x" });
    expect(searchRouteQuery({ ownedFilter: "all", searchQuery: "x" })).toEqual({
      q: "x",
      owned: "all",
    });
  });
});

describe("family scope helpers", () => {
  it("reads family=1 from the route", () => {
    expect(familyFromRoute({ query: { set: "LTR", family: "1" } })).toBe(true);
    expect(familyFromRoute({ query: { set: "LTR" } })).toBe(false);
    expect(familyFromRoute({ query: { family: "1" } })).toBe(false);
  });

  it("round-trips family in collection scope query", () => {
    expect(setScopeToQuery("LTR", true)).toEqual({ set: "LTR", family: "1" });
    expect(collectionScopeToQuery("LTR", "Borderless", true)).toEqual({
      set: "LTR",
      family: "1",
    });
    expect(collectionScopeFromRoute({ query: { set: "LTR", family: "1", art: "X" } })).toEqual({
      setCode: "LTR",
      family: true,
      artStyle: "",
    });
  });
});
