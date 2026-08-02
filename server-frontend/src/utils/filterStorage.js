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

export const COLOR_FILTER_MODE_KEY = "collectionColorFilterMode";

export function getStoredColorFilterMode() {
  const stored = localStorage.getItem(COLOR_FILTER_MODE_KEY);
  return stored === "includes" ? "includes" : "exact";
}

export function storeColorFilterMode(mode) {
  localStorage.setItem(
    COLOR_FILTER_MODE_KEY,
    mode === "includes" ? "includes" : "exact",
  );
}

export function filterSidebarWidthPx(wide) {
  return wide ? FILTER_SIDEBAR_WIDTHS.wide : FILTER_SIDEBAR_WIDTHS.narrow;
}

/** Collapsible filter groups in CollectionAllFilters (Search + Collection). */
export const FILTER_SECTION_PREFS_KEY = "collectionFilterSectionPrefs";

export const FILTER_SECTION_IDS = Object.freeze([
  "card",
  "role",
  "storage",
  "details",
]);

/** Default: all filter groups collapsed. */
export function defaultFilterSectionPrefs() {
  return Object.fromEntries(FILTER_SECTION_IDS.map((id) => [id, false]));
}

/**
 * @returns {Record<string, boolean>} map of section id → expanded
 */
export function getFilterSectionPrefs() {
  const defaults = defaultFilterSectionPrefs();
  try {
    const parsed = JSON.parse(localStorage.getItem(FILTER_SECTION_PREFS_KEY) || "{}");
    if (!parsed || typeof parsed !== "object") {
      return defaults;
    }
    const next = { ...defaults };
    for (const id of FILTER_SECTION_IDS) {
      if (Object.prototype.hasOwnProperty.call(parsed, id)) {
        next[id] = Boolean(parsed[id]);
      }
    }
    return next;
  } catch {
    return defaults;
  }
}

export function storeFilterSectionPrefs(prefs) {
  const defaults = defaultFilterSectionPrefs();
  const next = { ...defaults };
  if (prefs && typeof prefs === "object") {
    for (const id of FILTER_SECTION_IDS) {
      if (Object.prototype.hasOwnProperty.call(prefs, id)) {
        next[id] = Boolean(prefs[id]);
      }
    }
  }
  localStorage.setItem(FILTER_SECTION_PREFS_KEY, JSON.stringify(next));
  return next;
}

export function setFilterSectionExpanded(id, expanded) {
  if (!FILTER_SECTION_IDS.includes(id)) {
    return getFilterSectionPrefs();
  }
  return storeFilterSectionPrefs({
    ...getFilterSectionPrefs(),
    [id]: Boolean(expanded),
  });
}
