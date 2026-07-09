export function setScopeFromRoute(route) {
  const set = route.query?.set;
  if (typeof set === "string" && set.trim()) {
    return set.trim();
  }
  return "All";
}

export function artStyleFromRoute(route) {
  const art = route.query?.art;
  if (typeof art === "string" && art.trim()) {
    return art.trim();
  }
  return "";
}

export function collectionScopeFromRoute(route) {
  return {
    setCode: setScopeFromRoute(route),
    artStyle: artStyleFromRoute(route),
  };
}

const ALL_CARDS_SORT_FIELDS = new Set(["number", "value", "changeEuro", "changePct"]);
const ALL_CARDS_OWNED_FILTERS = new Set(["owned", "all", "unowned"]);
const ALL_CARDS_FINISH_FILTERS = new Set(["nonfoil", "foil", "etched"]);
import { COLLECTION_TYPE_FILTER_VALUES } from "./collectionTypes";

const ALL_CARDS_TYPE_FILTERS = COLLECTION_TYPE_FILTER_VALUES;
const ALL_CARDS_COLOR_FILTERS = new Set(["W", "U", "B", "R", "G", "C"]);

export function defaultAllCardsSortDirForField(sort) {
  return sort === "number" ? "asc" : "desc";
}

export function allCardsFiltersFromRoute(route) {
  const owned = route.query?.owned;
  const ownedFilter = ALL_CARDS_OWNED_FILTERS.has(owned) ? owned : "owned";

  const finish = route.query?.finish;
  const foilFilter = ALL_CARDS_FINISH_FILTERS.has(finish) ? finish : "all";

  const sortParam = route.query?.sort;
  const sort = typeof sortParam === "string" && ALL_CARDS_SORT_FIELDS.has(sortParam)
    ? sortParam
    : "value";

  const dirParam = route.query?.dir;
  const sortDir = dirParam === "asc" || dirParam === "desc"
    ? dirParam
    : defaultAllCardsSortDirForField(sort);

  const pageParam = Number(route.query?.page);
  const page = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;

  const typeParam = route.query?.type;
  const typeFilter = typeof typeParam === "string" && ALL_CARDS_TYPE_FILTERS.has(typeParam)
    ? typeParam
    : "all";

  const colorsParam = route.query?.colors;
  const colorFilters = typeof colorsParam === "string"
    ? colorsParam
      .split(",")
      .map((value) => value.trim().toUpperCase())
      .filter((value) => ALL_CARDS_COLOR_FILTERS.has(value))
    : [];

  return { ownedFilter, foilFilter, sort, sortDir, page, typeFilter, colorFilters };
}

export function allCardsRouteQuery({
  setCode,
  artStyle = "",
  ownedFilter = "owned",
  foilFilter = "all",
  typeFilter = "all",
  colorFilters = [],
  sort = "value",
  sortDir = "desc",
  page = 1,
} = {}) {
  const query = collectionScopeToQuery(setCode, artStyle);
  if (ownedFilter !== "owned") {
    query.owned = ownedFilter;
  }
  if (foilFilter !== "all") {
    query.finish = foilFilter;
  }
  if (typeFilter !== "all") {
    query.type = typeFilter;
  }
  if (colorFilters.length) {
    query.colors = colorFilters.join(",");
  }
  if (sort !== "value") {
    query.sort = sort;
  }
  const defaultDir = defaultAllCardsSortDirForField(sort);
  if (sortDir !== defaultDir) {
    query.dir = sortDir;
  }
  if (page > 1) {
    query.page = String(page);
  }
  return query;
}

export function setScopeToQuery(setCode) {
  if (!setCode || String(setCode).toLowerCase() === "all") {
    return {};
  }
  return { set: String(setCode) };
}

export function collectionScopeToQuery(setCode, artStyle = "") {
  const query = setScopeToQuery(setCode);
  if (artStyle) {
    query.art = artStyle;
  }
  return query;
}

export function collectionRouteForSet(setCode, artStyle = "") {
  const code = String(setCode || "").trim();
  if (!code || code.toLowerCase() === "all") {
    return { path: "/collection/all" };
  }
  return {
    path: "/collection/all",
    query: collectionScopeToQuery(code, artStyle),
  };
}

export function searchNavQuery(route) {
  const query = {};
  if (route.path === "/collection/search") {
    const q = route.query?.q;
    if (typeof q === "string" && q.trim()) {
      query.q = q.trim();
    }
    const page = route.query?.page;
    const parsedPage = Number(page);
    if (Number.isFinite(parsedPage) && parsedPage > 1) {
      query.page = String(parsedPage);
    }
  }
  const owned = route.query?.owned;
  if (owned === "owned" || owned === "unowned") {
    query.owned = owned;
  }
  const finish = route.query?.finish;
  if (finish === "nonfoil" || finish === "foil" || finish === "etched") {
    query.finish = finish;
  }
  return query;
}

export function collectionNavQuery(route, targetPath) {
  const { setCode, artStyle } = collectionScopeFromRoute(route);
  if (targetPath === "/collection/search") {
    return searchNavQuery(route);
  }
  if (targetPath === "/collection/all") {
    const filters = route.path === "/collection/all"
      ? allCardsFiltersFromRoute(route)
      : {
        ownedFilter: "owned",
        foilFilter: "all",
        typeFilter: "all",
        colorFilters: [],
        sort: "value",
        sortDir: "desc",
        page: 1,
      };
    return allCardsRouteQuery({ setCode, artStyle, ...filters });
  }
  return collectionScopeToQuery(setCode, artStyle);
}

export function setScopeQueryFromRoute(route) {
  if (route.path === "/collection/all") {
    const { setCode, artStyle } = collectionScopeFromRoute(route);
    return allCardsRouteQuery({
      setCode,
      artStyle,
      ...allCardsFiltersFromRoute(route),
    });
  }
  const { setCode, artStyle } = collectionScopeFromRoute(route);
  return collectionScopeToQuery(setCode, artStyle);
}

export function managerArtStylesEditorRoute(setCode) {
  const code = String(setCode || "").trim();
  if (!code || code.toLowerCase() === "all") {
    return { path: "/manager" };
  }
  return {
    path: "/manager",
    query: { set: code, editArtStyles: "1" },
  };
}

export function shouldOpenManagerArtStyleEditor(route) {
  const value = route.query?.editArtStyles;
  return value === "1" || value === "true" || value === "";
}
