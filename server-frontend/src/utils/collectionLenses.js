export const COLLECTION_LENSES = [
  { id: "owned", label: "Owned", ownedFilter: "owned", foilFilter: "all" },
  { id: "missing", label: "Missing", ownedFilter: "unowned", foilFilter: "all" },
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

export function detectActiveLens({
  lensId = "",
  ownedFilter,
  foilFilter,
  sort,
  sortDir,
  typeFilter,
  colorFilters,
  searchQuery,
}) {
  if (searchQuery?.trim() || typeFilter !== "all" || colorFilters?.length) {
    return "";
  }
  if (lensId && LENS_BY_ID[lensId]) {
    const lens = LENS_BY_ID[lensId];
    if (
      ownedFilter === lens.ownedFilter
      && foilFilter === (lens.foilFilter || "all")
      && sort === (lens.sort || "value")
      && sortDir === (lens.sortDir || "desc")
    ) {
      return lensId;
    }
  }
  for (const lens of COLLECTION_LENSES) {
    if (
      ownedFilter === lens.ownedFilter
      && foilFilter === (lens.foilFilter || "all")
      && sort === (lens.sort || "value")
      && sortDir === (lens.sortDir || "desc")
    ) {
      return lens.id;
    }
  }
  return "";
}
