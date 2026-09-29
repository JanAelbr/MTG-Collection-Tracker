export const COLLECTION_LENSES = [
  { id: "owned", label: "Owned", ownedFilter: "owned", foilFilter: "all" },
  { id: "missing", label: "Missing", ownedFilter: "unowned", foilFilter: "all" },
  {
    id: "unique",
    label: "Unique",
    title: "Hide collector numbers you already own in foil or non-foil",
    ownedFilter: "missing-number",
    sort: "number",
    sortDir: "asc",
  },
  { id: "foils", label: "Foils", ownedFilter: "all", foilFilter: "foil" },
  { id: "high-value", label: "High value", ownedFilter: "owned", foilFilter: "all", sort: "value", sortDir: "desc" },
  { id: "completion", label: "Completion", ownedFilter: "all", foilFilter: "all", sort: "number", sortDir: "asc" },
];

const LENS_BY_ID = Object.fromEntries(COLLECTION_LENSES.map((lens) => [lens.id, lens]));

export function collectionLensFromRoute(route) {
  const lens = route.query?.lens;
  if (typeof lens === "string" && LENS_BY_ID[lens]) {
    return lens;
  }
  return "";
}

export function lensDefinition(lensId) {
  return LENS_BY_ID[lensId] || null;
}

function lensMatches(lens, { ownedFilter, foilFilter, sort, sortDir }) {
  if (!lens || ownedFilter !== lens.ownedFilter) {
    return false;
  }
  if ("foilFilter" in lens && foilFilter !== (lens.foilFilter || "all")) {
    return false;
  }
  return sort === (lens.sort || "value") && sortDir === (lens.sortDir || "desc");
}

export function detectActiveLens({
  lensId = "",
  ownedFilter,
  foilFilter,
  sort,
  sortDir,
  typeFilter,
  colorFilters,
  searchQuery,
  rarityFilter = "all",
  cmcMin = null,
  cmcMax = null,
  priceMin = null,
  priceMax = null,
  powerMin = null,
  toughnessMin = null,
}) {
  if (
    searchQuery?.trim()
    || typeFilter !== "all"
    || colorFilters?.length
    || (rarityFilter && rarityFilter !== "all")
    || cmcMin != null
    || cmcMax != null
    || priceMin != null
    || priceMax != null
    || powerMin != null
    || toughnessMin != null
  ) {
    return "";
  }
  if (lensId && lensMatches(LENS_BY_ID[lensId], { ownedFilter, foilFilter, sort, sortDir })) {
    return lensId;
  }
  for (const lens of COLLECTION_LENSES) {
    if (lensMatches(lens, { ownedFilter, foilFilter, sort, sortDir })) {
      return lens.id;
    }
  }
  return "";
}
