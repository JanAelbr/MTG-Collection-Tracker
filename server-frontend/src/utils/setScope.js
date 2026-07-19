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

const ALL_CARDS_SORT_FIELDS = new Set(["number", "value", "name", "artStyle"]);
const ALL_CARDS_OWNED_FILTERS = new Set(["owned", "all", "unowned"]);
const ALL_CARDS_FINISH_FILTERS = new Set(["nonfoil", "foil", "etched"]);
import { COLLECTION_TYPE_FILTER_VALUES } from "./collectionTypes";
import { COLLECTION_RARITY_FILTER_VALUES } from "./collectionRarities";
import { collectionLensFromRoute } from "./collectionLenses";
import { parseOptionalNumber } from "./collectionFilters";

const ALL_CARDS_TYPE_FILTERS = COLLECTION_TYPE_FILTER_VALUES;
const ALL_CARDS_COLOR_FILTERS = new Set(["W", "U", "B", "R", "G", "C"]);
const ALL_CARDS_RARITY_FILTERS = COLLECTION_RARITY_FILTER_VALUES;

function parseStorageFiltersFromRoute(route) {
  const storageParam = route.query?.storage;
  if (typeof storageParam !== "string" || !storageParam.trim()) {
    return [];
  }
  return storageParam
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

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

  const searchParam = route.query?.q;
  const searchQuery = typeof searchParam === "string" ? searchParam.trim() : "";

  const rarityParam = route.query?.rarity;
  const rarityFilter = typeof rarityParam === "string" && ALL_CARDS_RARITY_FILTERS.has(rarityParam)
    ? rarityParam
    : "all";

  const cmcMin = parseOptionalNumber(route.query?.cmcMin);
  const cmcMax = parseOptionalNumber(route.query?.cmcMax);
  const powerMin = parseOptionalNumber(route.query?.powMin);
  const toughnessMin = parseOptionalNumber(route.query?.tghMin);

  const storageFilters = parseStorageFiltersFromRoute(route);

  const lens = collectionLensFromRoute(route);

  const viewParam = route.query?.view;
  const viewMode = viewParam === "table" ? "table" : "gallery";

  const editArtStyles = route.query?.editArtStyles;
  const openArtStyleEditor = editArtStyles === "1" || editArtStyles === "true" || editArtStyles === "";

  return {
    ownedFilter,
    foilFilter,
    sort,
    sortDir,
    page,
    typeFilter,
    colorFilters,
    searchQuery,
    rarityFilter,
    cmcMin,
    cmcMax,
    powerMin,
    toughnessMin,
    storageFilters,
    lens,
    viewMode,
    openArtStyleEditor,
  };
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
  searchQuery = "",
  rarityFilter = "all",
  cmcMin = null,
  cmcMax = null,
  powerMin = null,
  toughnessMin = null,
  storageFilters = [],
  lens = "",
  viewMode = "gallery",
  editArtStyles = false,
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
  if (searchQuery) {
    query.q = searchQuery;
  }
  if (rarityFilter !== "all") {
    query.rarity = rarityFilter;
  }
  if (cmcMin != null) {
    query.cmcMin = String(cmcMin);
  }
  if (cmcMax != null) {
    query.cmcMax = String(cmcMax);
  }
  if (powerMin != null) {
    query.powMin = String(powerMin);
  }
  if (toughnessMin != null) {
    query.tghMin = String(toughnessMin);
  }
  if (storageFilters.length) {
    query.storage = storageFilters.join(",");
  }
  if (lens) {
    query.lens = lens;
  }
  if (viewMode === "table") {
    query.view = "table";
  }
  if (editArtStyles) {
    query.editArtStyles = "1";
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

export function searchFiltersFromRoute(route) {
  const owned = route.query?.owned;
  const ownedFilter = ALL_CARDS_OWNED_FILTERS.has(owned) ? owned : "all";

  const finish = route.query?.finish;
  const foilFilter = ALL_CARDS_FINISH_FILTERS.has(finish) ? finish : "all";

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

  const nameParam = route.query?.q;
  const searchQuery = typeof nameParam === "string" ? nameParam.trim() : "";

  const textParam = route.query?.text;
  const textSearchQuery = typeof textParam === "string" ? textParam.trim() : "";

  const creatureParam = route.query?.creature;
  const creatureTypeQuery = typeof creatureParam === "string" ? creatureParam.trim() : "";

  const rarityParam = route.query?.rarity;
  const rarityFilter = typeof rarityParam === "string" && ALL_CARDS_RARITY_FILTERS.has(rarityParam)
    ? rarityParam
    : "all";

  const cmcMin = parseOptionalNumber(route.query?.cmcMin);
  const cmcMax = parseOptionalNumber(route.query?.cmcMax);
  const powerMin = parseOptionalNumber(route.query?.powMin);
  const toughnessMin = parseOptionalNumber(route.query?.tghMin);

  const storageFilters = parseStorageFiltersFromRoute(route);

  const viewParam = route.query?.view;
  const viewMode = viewParam === "list" ? "list" : "gallery";

  return {
    ownedFilter,
    foilFilter,
    page,
    typeFilter,
    colorFilters,
    searchQuery,
    textSearchQuery,
    creatureTypeQuery,
    rarityFilter,
    cmcMin,
    cmcMax,
    powerMin,
    toughnessMin,
    storageFilters,
    viewMode,
  };
}

export function searchRouteQuery({
  ownedFilter = "all",
  foilFilter = "all",
  typeFilter = "all",
  colorFilters = [],
  searchQuery = "",
  textSearchQuery = "",
  creatureTypeQuery = "",
  rarityFilter = "all",
  cmcMin = null,
  cmcMax = null,
  powerMin = null,
  toughnessMin = null,
  storageFilters = [],
  page = 1,
  viewMode = "gallery",
} = {}) {
  const query = {};
  if (searchQuery) {
    query.q = searchQuery;
  }
  if (textSearchQuery) {
    query.text = textSearchQuery;
  }
  if (creatureTypeQuery) {
    query.creature = creatureTypeQuery;
  }
  if (ownedFilter !== "all") {
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
  if (rarityFilter !== "all") {
    query.rarity = rarityFilter;
  }
  if (cmcMin != null) {
    query.cmcMin = String(cmcMin);
  }
  if (cmcMax != null) {
    query.cmcMax = String(cmcMax);
  }
  if (powerMin != null) {
    query.powMin = String(powerMin);
  }
  if (toughnessMin != null) {
    query.tghMin = String(toughnessMin);
  }
  if (storageFilters.length) {
    query.storage = storageFilters.join(",");
  }
  if (page > 1) {
    query.page = String(page);
  }
  if (viewMode === "list") {
    query.view = "list";
  }
  return query;
}

export function searchViewModeFromRoute(route) {
  return searchFiltersFromRoute(route).viewMode;
}

export function searchNavQuery(route) {
  if (route.path === "/collection/search") {
    return searchRouteQuery(searchFiltersFromRoute(route));
  }
  const query = {};
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
        searchQuery: "",
        lens: "",
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
    return { path: "/collection/all" };
  }
  return {
    path: "/collection/all",
    query: { set: code, editArtStyles: "1" },
  };
}

export function collectionViewModeFromRoute(route) {
  return allCardsFiltersFromRoute(route).viewMode;
}

export function shouldOpenManagerArtStyleEditor(route) {
  return allCardsFiltersFromRoute(route).openArtStyleEditor;
}
