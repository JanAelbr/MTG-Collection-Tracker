import { describe, expect, it } from "vitest";
import {
  normalizeStorageGroupBy,
  storageFiltersFromRoute,
  storageLocationFromRoute,
  storageLocationsFromRoute,
  storageRouteQuery,
} from "./storageScope";

describe("storageScope", () => {
  it("reads location and filters from the route", () => {
    const route = {
      query: {
        location: "storage:general",
        q: "nazgul",
        sort: "set",
        dir: "asc",
        set: "LTR",
        view: "table",
      },
    };
    expect(storageLocationFromRoute(route)).toBe("storage:general");
    expect(storageFiltersFromRoute(route)).toEqual({
      sort: "set",
      sortDir: "asc",
      searchQuery: "nazgul",
      setFilter: "LTR",
      viewMode: "table",
      groupByLevels: ["set"],
      groupBy: "set",
      colorFilters: [],
      colorMode: "exact",
    });
  });

  it("applies defaults when query params are missing", () => {
    expect(storageFiltersFromRoute({ query: {} })).toEqual({
      sort: "value",
      sortDir: "desc",
      searchQuery: "",
      setFilter: "",
      viewMode: "gallery",
      groupByLevels: ["set"],
      groupBy: "set",
      colorFilters: [],
      colorMode: "exact",
    });
  });

  it("reads and writes color identity filters", () => {
    expect(storageFiltersFromRoute({
      query: { colors: "W,U,C", colorMode: "includes" },
    })).toMatchObject({
      colorFilters: ["W", "U", "C"],
      colorMode: "includes",
    });
    expect(storageRouteQuery({
      colorFilters: ["R", "G"],
      colorMode: "includes",
    })).toEqual({
      colors: "R,G",
      colorMode: "includes",
    });
    expect(storageRouteQuery({
      colorFilters: ["B"],
      colorMode: "exact",
    })).toEqual({ colors: "B" });
  });

  it("ignores legacy finish query params", () => {
    expect(storageFiltersFromRoute({
      query: { finish: "foil" },
    }).finish).toBeUndefined();
    expect(storageRouteQuery({ foilFilter: "etched" }).finish).toBeUndefined();
  });

  it("reads and writes multiple locations", () => {
    expect(storageLocationsFromRoute({
      query: { location: "storage:a,binder:1,storage:a" },
    })).toEqual(["storage:a", "binder:1"]);
    expect(storageLocationFromRoute({
      query: { location: "storage:a,binder:1" },
    })).toBe("storage:a");
    expect(storageRouteQuery({
      location: ["storage:a", "binder:1"],
    })).toEqual({ location: "storage:a,binder:1" });
  });

  it("reads group=off from the route as none", () => {
    expect(storageFiltersFromRoute({ query: { group: "off" } }).groupByLevels).toEqual([]);
    expect(storageFiltersFromRoute({ query: { group: "off" } }).groupBy).toBe("none");
  });

  it("reads group modes from the route", () => {
    expect(storageFiltersFromRoute({ query: { group: "type" } }).groupByLevels).toEqual(["type"]);
    expect(storageFiltersFromRoute({ query: { group: "subtype" } }).groupByLevels).toEqual([
      "subtype",
    ]);
    expect(storageFiltersFromRoute({ query: { group: "role" } }).groupByLevels).toEqual(["role"]);
    expect(storageFiltersFromRoute({ query: { group: "colorIdentity" } }).groupByLevels).toEqual([
      "colorIdentity",
    ]);
    expect(storageFiltersFromRoute({
      query: { group: "role,colorIdentity,rarity" },
    }).groupByLevels).toEqual(["role", "colorIdentity", "rarity"]);
  });

  it("normalizes legacy and alias group values", () => {
    expect(normalizeStorageGroupBy("")).toBe("set");
    expect(normalizeStorageGroupBy("off")).toBe("none");
    expect(normalizeStorageGroupBy("color")).toBe("colorIdentity");
    expect(normalizeStorageGroupBy("1")).toBe("set");
  });

  it("reads breakdown view from the route", () => {
    expect(storageFiltersFromRoute({ query: { view: "breakdown" } }).viewMode).toBe("breakdown");
  });

  it("round-trips breakdown view", () => {
    expect(storageRouteQuery({ viewMode: "breakdown" })).toEqual({ view: "breakdown" });
  });

  it("round-trips non-default query values", () => {
    const query = storageRouteQuery({
      location: "binder:1",
      sort: "name",
      sortDir: "desc",
      searchQuery: "ring",
      setFilter: "LTC",
      viewMode: "table",
      groupBy: "none",
    });
    expect(query).toEqual({
      location: "binder:1",
      sort: "name",
      dir: "desc",
      q: "ring",
      set: "LTC",
      view: "table",
      group: "off",
    });
    expect(storageFiltersFromRoute({ query })).toEqual({
      sort: "name",
      sortDir: "desc",
      searchQuery: "ring",
      setFilter: "LTC",
      viewMode: "table",
      groupByLevels: [],
      groupBy: "none",
      colorFilters: [],
      colorMode: "exact",
    });
  });

  it("writes non-default group modes to the query", () => {
    expect(storageRouteQuery({ groupBy: "type" })).toEqual({ group: "type" });
    expect(storageRouteQuery({ groupBy: "colorIdentity" })).toEqual({
      group: "colorIdentity",
    });
    expect(storageRouteQuery({
      groupByLevels: ["role", "colorIdentity", "rarity"],
    })).toEqual({ group: "role,colorIdentity,rarity" });
  });

  it("omits default gallery/value/group from the query", () => {
    expect(
      storageRouteQuery({
        location: "storage:general",
        sort: "value",
        sortDir: "desc",
        searchQuery: "",
        setFilter: "",
        viewMode: "gallery",
        groupByLevels: ["set"],
      }),
    ).toEqual({ location: "storage:general" });
  });
});
