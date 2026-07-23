import {
  defaultCollectionSortDir,
  normalizeCollectionSort,
  normalizeCollectionSortDir,
} from "./collectionSort.js";

const FINISH_FILTERS = new Set(["nonfoil", "foil", "etched"]);

export function storageLocationFromRoute(route) {
  const location = route.query?.location;
  return typeof location === "string" ? location.trim() : "";
}

export function storageFiltersFromRoute(route) {
  const finishParam = route.query?.finish;
  const foilFilter = FINISH_FILTERS.has(finishParam) ? finishParam : "all";

  const sort = normalizeCollectionSort(route.query?.sort, { allowSet: true });
  const sortDir = normalizeCollectionSortDir(sort, route.query?.dir, { allowSet: true });

  const searchParam = route.query?.q;
  const searchQuery = typeof searchParam === "string" ? searchParam.trim() : "";

  const setParam = route.query?.set;
  const setFilter =
    typeof setParam === "string" && setParam.trim() && setParam.trim().toLowerCase() !== "all"
      ? setParam.trim().toUpperCase()
      : "";

  const viewParam = route.query?.view;
  const viewMode = viewParam === "table" || viewParam === "breakdown"
    ? viewParam
    : "gallery";

  const groupParam = String(route.query?.group || "").trim().toLowerCase();
  const groupBySet = groupParam !== "off" && groupParam !== "none" && groupParam !== "0";

  return {
    foilFilter,
    sort,
    sortDir,
    searchQuery,
    setFilter,
    viewMode,
    groupBySet,
  };
}

export function storageRouteQuery({
  location = "",
  foilFilter = "all",
  sort = "value",
  sortDir = "",
  searchQuery = "",
  setFilter = "",
  viewMode = "gallery",
  groupBySet = true,
} = {}) {
  const query = {};
  const slug = String(location || "").trim();
  if (slug) {
    query.location = slug;
  }

  const normalizedSort = normalizeCollectionSort(sort, { allowSet: true });
  const normalizedDir = normalizeCollectionSortDir(normalizedSort, sortDir, { allowSet: true });
  const defaultDir = defaultCollectionSortDir(normalizedSort);

  if (normalizedSort !== "value") {
    query.sort = normalizedSort;
  }
  if (normalizedDir !== defaultDir) {
    query.dir = normalizedDir;
  }

  const finish = String(foilFilter || "all");
  if (FINISH_FILTERS.has(finish)) {
    query.finish = finish;
  }

  const q = String(searchQuery || "").trim();
  if (q) {
    query.q = q;
  }

  const setCode = String(setFilter || "").trim().toUpperCase();
  if (setCode && setCode !== "ALL") {
    query.set = setCode;
  }

  if (viewMode === "table" || viewMode === "breakdown") {
    query.view = viewMode;
  }

  if (!groupBySet) {
    query.group = "off";
  }

  return query;
}
