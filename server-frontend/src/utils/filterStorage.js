export const FOIL_FILTER_KEY = "reportFoilFilter";

export function getStoredFoilFilter() {
  const stored = localStorage.getItem(FOIL_FILTER_KEY);
  if (stored === "foil" || stored === "nonfoil" || stored === "etched") {
    return stored;
  }
  return "all";
}

export function storeFoilFilter(value) {
  localStorage.setItem(FOIL_FILTER_KEY, value);
}

export const ALL_CARDS_SORT_KEY = "collectionAllCardsSort";

const ALL_CARDS_SORT_FIELDS = new Set(["number", "value", "name", "artStyle"]);

function normalizeAllCardsSort(sort) {
  if (sort === "change" || sort === "changeEuro" || sort === "changePct") {
    return "value";
  }
  return ALL_CARDS_SORT_FIELDS.has(sort) ? sort : "number";
}

export function defaultAllCardsSortDir(sort) {
  return sort === "number" ? "asc" : "desc";
}

export function getStoredAllCardsSort() {
  const stored = localStorage.getItem(ALL_CARDS_SORT_KEY);
  if (!stored) {
    return { sort: "value", dir: "desc" };
  }
  if (stored === "value") {
    return { sort: "value", dir: "desc" };
  }
  if (stored === "number") {
    return { sort: "number", dir: "asc" };
  }
  try {
    const parsed = JSON.parse(stored);
    const sort = normalizeAllCardsSort(parsed.sort);
    const dir = parsed.dir === "desc" ? "desc" : "asc";
    return { sort, dir };
  } catch {
    return { sort: "number", dir: "asc" };
  }
}

export function storeAllCardsSort(sort, dir) {
  localStorage.setItem(
    ALL_CARDS_SORT_KEY,
    JSON.stringify({
      sort: normalizeAllCardsSort(sort),
      dir: dir === "desc" ? "desc" : "asc",
    }),
  );
}

export const FILTER_SIDEBAR_PREFS_KEY = "filterSidebarPrefs";

const FILTER_SIDEBAR_WIDTHS = {
  narrow: 220,
  wide: 300,
};

export function getFilterSidebarPrefs() {
  try {
    const parsed = JSON.parse(localStorage.getItem(FILTER_SIDEBAR_PREFS_KEY) || "{}");
    return {
      collapsed: Boolean(parsed.collapsed),
      wide: Boolean(parsed.wide),
    };
  } catch {
    return { collapsed: false, wide: false };
  }
}

export function storeFilterSidebarPrefs(prefs) {
  localStorage.setItem(
    FILTER_SIDEBAR_PREFS_KEY,
    JSON.stringify({
      collapsed: Boolean(prefs.collapsed),
      wide: Boolean(prefs.wide),
    }),
  );
}

export function filterSidebarWidthPx(wide) {
  return wide ? FILTER_SIDEBAR_WIDTHS.wide : FILTER_SIDEBAR_WIDTHS.narrow;
}
