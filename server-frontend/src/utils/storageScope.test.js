import { describe, expect, it } from "vitest";
import {
  storageFiltersFromRoute,
  storageLocationFromRoute,
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
        finish: "foil",
        set: "LTR",
        view: "table",
      },
    };
    expect(storageLocationFromRoute(route)).toBe("storage:general");
    expect(storageFiltersFromRoute(route)).toEqual({
      foilFilter: "foil",
      sort: "set",
      sortDir: "asc",
      searchQuery: "nazgul",
      setFilter: "LTR",
      viewMode: "table",
      groupBySet: true,
    });
  });

  it("applies defaults when query params are missing", () => {
    expect(storageFiltersFromRoute({ query: {} })).toEqual({
      foilFilter: "all",
      sort: "value",
      sortDir: "desc",
      searchQuery: "",
      setFilter: "",
      viewMode: "gallery",
      groupBySet: true,
    });
  });

  it("reads group=off from the route", () => {
    expect(storageFiltersFromRoute({ query: { group: "off" } }).groupBySet).toBe(false);
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
      foilFilter: "etched",
      sort: "name",
      sortDir: "desc",
      searchQuery: "ring",
      setFilter: "LTC",
      viewMode: "table",
      groupBySet: false,
    });
    expect(query).toEqual({
      location: "binder:1",
      finish: "etched",
      sort: "name",
      dir: "desc",
      q: "ring",
      set: "LTC",
      view: "table",
      group: "off",
    });
    expect(storageFiltersFromRoute({ query })).toEqual({
      foilFilter: "etched",
      sort: "name",
      sortDir: "desc",
      searchQuery: "ring",
      setFilter: "LTC",
      viewMode: "table",
      groupBySet: false,
    });
  });

  it("omits default gallery/value/all finish/group from the query", () => {
    expect(
      storageRouteQuery({
        location: "storage:general",
        foilFilter: "all",
        sort: "value",
        sortDir: "desc",
        searchQuery: "",
        setFilter: "",
        viewMode: "gallery",
        groupBySet: true,
      }),
    ).toEqual({ location: "storage:general" });
  });
});
