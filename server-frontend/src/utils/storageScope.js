import {
  defaultCollectionSortDir,
  normalizeCollectionSort,
  normalizeCollectionSortDir,
} from "./collectionSort.js";
import {
  formatGroupByLevels,
  normalizeGroupByLevels,
  SEARCH_GROUP_BY_OPTIONS,
} from "./searchResults.js";

export const STORAGE_GROUP_BY_OPTIONS = SEARCH_GROUP_BY_OPTIONS;

const STORAGE_COLOR_FILTERS = new Set(["W", "U", "B", "R", "G", "C"]);
const STORAGE_COLOR_MODES = new Set(["exact", "includes"]);

export function normalizeStorageColorFilters(value) {
  const raw = Array.isArray(value)
    ? value
    : String(value || "").split(",");
  const seen = new Set();
  const colors = [];
  for (const part of raw) {
    const color = String(part || "").trim().toUpperCase();
    if (!STORAGE_COLOR_FILTERS.has(color) || seen.has(color)) {
      continue;
    }
    seen.add(color);
    colors.push(color);
  }
  return colors;
}

export function normalizeStorageColorMode(value, { fallback = "exact" } = {}) {
  const mode = String(value || "").trim().toLowerCase();
  return STORAGE_COLOR_MODES.has(mode) ? mode : fallback;
}

/**
 * Storage defaults to grouping by set. Accepts legacy `off`/`none`/`0`,
 * single modes, and nested `role,colorIdentity,rarity`.
 */
export function normalizeStorageGroupByLevels(value) {
  if (value == null || (typeof value === "string" && !value.trim())) {
    return ["set"];
  }
  if (Array.isArray(value) && !value.length) {
    return [];
  }
  const raw = Array.isArray(value) ? value.join(",") : String(value).trim();
  const lower = raw.toLowerCase();
  if (lower === "off" || lower === "none" || lower === "0" || lower === "false") {
    return [];
  }
  if (lower === "1" || lower === "true" || lower === "on") {
    return ["set"];
  }
  return normalizeGroupByLevels(value, { emptyDefault: ["set"] });
}

/** @deprecated Prefer normalizeStorageGroupByLevels; returns first level or "none". */
export function normalizeStorageGroupBy(value) {
  const levels = normalizeStorageGroupByLevels(value);
  return levels[0] || "none";
}

export function storageLocationsFromRoute(route) {
  const raw = route.query?.location;
  const parts = [];
  if (Array.isArray(raw)) {
    for (const value of raw) {
      if (typeof value === "string") {
        parts.push(...value.split(","));
      }
    }
  } else if (typeof raw === "string") {
    parts.push(...raw.split(","));
  }
  const seen = new Set();
  const slugs = [];
  for (const part of parts) {
    const slug = String(part || "").trim();
    if (!slug || seen.has(slug)) {
      continue;
    }
    seen.add(slug);
    slugs.push(slug);
  }
  return slugs;
}

export function storageLocationFromRoute(route) {
  return storageLocationsFromRoute(route)[0] || "";
}

export function storageFiltersFromRoute(route, { colorModeFallback = "exact" } = {}) {
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

  const groupByLevels = normalizeStorageGroupByLevels(route.query?.group);
  const colorFilters = normalizeStorageColorFilters(route.query?.colors);
  const colorModeParam = route.query?.colorMode;
  const colorMode = typeof colorModeParam === "string" && STORAGE_COLOR_MODES.has(colorModeParam)
    ? colorModeParam
    : normalizeStorageColorMode(colorModeFallback);

  return {
    sort,
    sortDir,
    searchQuery,
    setFilter,
    viewMode,
    groupByLevels,
    groupBy: groupByLevels[0] || "none",
    colorFilters,
    colorMode,
  };
}

export function storageRouteQuery({
  location = "",
  sort = "value",
  sortDir = "",
  searchQuery = "",
  setFilter = "",
  viewMode = "gallery",
  groupBy = undefined,
  groupByLevels = undefined,
  colorFilters = [],
  colorMode = "exact",
} = {}) {
  const query = {};
  const slugs = Array.isArray(location)
    ? location.map((slug) => String(slug || "").trim()).filter(Boolean)
    : String(location || "")
      .split(",")
      .map((slug) => slug.trim())
      .filter(Boolean);
  const uniqueSlugs = [...new Set(slugs)];
  if (uniqueSlugs.length) {
    query.location = uniqueSlugs.join(",");
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

  const colors = normalizeStorageColorFilters(colorFilters);
  if (colors.length) {
    query.colors = colors.join(",");
  }
  const mode = normalizeStorageColorMode(colorMode);
  if (mode === "includes") {
    query.colorMode = "includes";
  }

  const levels = normalizeStorageGroupByLevels(
    groupByLevels !== undefined ? groupByLevels : groupBy,
  );
  if (!levels.length) {
    query.group = "off";
  } else if (!(levels.length === 1 && levels[0] === "set")) {
    query.group = formatGroupByLevels(levels);
  }

  return query;
}
