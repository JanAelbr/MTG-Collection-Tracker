export function setScopeFromRoute(route) {
  const set = route.query?.set;
  if (typeof set === "string" && set.trim()) {
    return set.trim();
  }
  return "All";
}

export function familyFromRoute(route) {
  const family = route.query?.family;
  if (family === "1" || family === "true" || family === true) {
    const setCode = setScopeFromRoute(route);
    return setCode.toLowerCase() !== "all";
  }
  return false;
}

export function artStyleFromRoute(route) {
  const art = route.query?.art;
  if (typeof art === "string" && art.trim()) {
    return art.trim();
  }
  return "";
}

export function collectionScopeFromRoute(route) {
  const setCode = setScopeFromRoute(route);
  const family = familyFromRoute(route);
  return {
    setCode,
    family,
    artStyle: family ? "" : artStyleFromRoute(route),
  };
}

const ALL_CARDS_SORT_FIELDS = new Set(["number", "value", "name", "artStyle"]);
const SEARCH_SORT_FIELDS = new Set(["newest", "name", "value", "cmc", "rarity", "power"]);
const SEARCH_SORT_DIR_DEFAULTS = {
  newest: "desc",
  name: "asc",
  value: "desc",
  cmc: "asc",
  rarity: "asc",
  power: "desc",
};
const ROLES_SORT_FIELDS = new Set(["name", "cmc", "rarity", "value"]);
const ROLES_SORT_DIR_DEFAULTS = {
  name: "asc",
  cmc: "asc",
  rarity: "asc",
  value: "desc",
};
const ALL_CARDS_OWNED_FILTERS = new Set(["owned", "all", "unowned"]);
const ALL_CARDS_FINISH_FILTERS = new Set(["nonfoil", "foil", "etched"]);
import { COLLECTION_TYPE_FILTER_VALUES } from "./collectionTypes";
import { COLLECTION_RARITY_FILTER_VALUES } from "./collectionRarities";
import { collectionLensFromRoute } from "./collectionLenses";
import { parseOptionalNumber } from "./collectionFilters";
import { SEARCH_ROLE_OPTIONS } from "./deckPower";

const ALL_CARDS_TYPE_FILTERS = COLLECTION_TYPE_FILTER_VALUES;
const ALL_CARDS_COLOR_FILTERS = new Set(["W", "U", "B", "R", "G", "C"]);
const ALL_CARDS_RARITY_FILTERS = COLLECTION_RARITY_FILTER_VALUES;
const SEARCH_ROLE_FILTERS = new Set(SEARCH_ROLE_OPTIONS.map((role) => role.id));

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

function parseRoleFiltersFromRoute(route) {
  const rolesParam = route.query?.roles;
  if (typeof rolesParam !== "string" || !rolesParam.trim()) {
    return [];
  }
  const seen = new Set();
  const roles = [];
  for (const value of rolesParam.split(",")) {
    const role = value.trim().toLowerCase();
    if (!SEARCH_ROLE_FILTERS.has(role) || seen.has(role)) {
      continue;
    }
    seen.add(role);
    roles.push(role);
  }
  return roles;
}

export function defaultAllCardsSortDirForField(sort) {
  return sort === "number" ? "asc" : "desc";
}

export function defaultSearchSortDirForField(sort) {
  return SEARCH_SORT_DIR_DEFAULTS[sort] || "asc";
}

export function normalizeSearchSort(sort) {
  return typeof sort === "string" && SEARCH_SORT_FIELDS.has(sort) ? sort : "newest";
}

export function normalizeSearchSortDir(sort, dir) {
  const normalizedSort = normalizeSearchSort(sort);
  if (dir === "asc" || dir === "desc") {
    return dir;
  }
  return defaultSearchSortDirForField(normalizedSort);
}

export function defaultRolesSortDirForField(sort) {
  return ROLES_SORT_DIR_DEFAULTS[sort] || "asc";
}

export function normalizeRolesSort(sort) {
  return typeof sort === "string" && ROLES_SORT_FIELDS.has(sort) ? sort : "name";
}

export function normalizeRolesSortDir(sort, dir) {
  const normalizedSort = normalizeRolesSort(sort);
  if (dir === "asc" || dir === "desc") {
    return dir;
  }
  return defaultRolesSortDirForField(normalizedSort);
}

export function normalizeRolesRole(role) {
  const value = typeof role === "string" ? role.trim().toLowerCase() : "";
  return SEARCH_ROLE_FILTERS.has(value) ? value : "";
}

export function rolesFiltersFromRoute(route) {
  const role = normalizeRolesRole(route.query?.role);
  const sort = normalizeRolesSort(route.query?.sort);
  const sortDir = normalizeRolesSortDir(sort, route.query?.dir);
  const storageFilters = parseStorageFiltersFromRoute(route);

  const finish = route.query?.finish;
  const foilFilter = ALL_CARDS_FINISH_FILTERS.has(finish) ? finish : "all";

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

  const rarityParam = route.query?.rarity;
  const rarityFilter = typeof rarityParam === "string" && ALL_CARDS_RARITY_FILTERS.has(rarityParam)
    ? rarityParam
    : "all";

  const nameParam = route.query?.q;
  const searchQuery = typeof nameParam === "string" ? nameParam.trim() : "";

  return {
    role,
    sort,
    sortDir,
    storageFilters,
    foilFilter,
    typeFilter,
    colorFilters,
    rarityFilter,
    searchQuery,
    cmcMin: parseOptionalNumber(route.query?.cmcMin),
    cmcMax: parseOptionalNumber(route.query?.cmcMax),
    priceMin: parseOptionalNumber(route.query?.priceMin),
    priceMax: parseOptionalNumber(route.query?.priceMax),
    powerMin: parseOptionalNumber(route.query?.powMin),
    toughnessMin: parseOptionalNumber(route.query?.tghMin),
  };
}

export function rolesRouteQuery({
  role = "",
  sort = "name",
  sortDir = "asc",
  storageFilters = [],
  foilFilter = "all",
  typeFilter = "all",
  colorFilters = [],
  rarityFilter = "all",
  searchQuery = "",
  cmcMin = null,
  cmcMax = null,
  priceMin = null,
  priceMax = null,
  powerMin = null,
  toughnessMin = null,
} = {}) {
  const query = {};
  const normalizedRole = normalizeRolesRole(role);
  if (normalizedRole) {
    query.role = normalizedRole;
  }
  if (searchQuery) {
    query.q = searchQuery;
  }
  const normalizedSort = normalizeRolesSort(sort);
  if (normalizedSort !== "name") {
    query.sort = normalizedSort;
  }
  const normalizedDir = normalizeRolesSortDir(normalizedSort, sortDir);
  if (normalizedDir !== defaultRolesSortDirForField(normalizedSort)) {
    query.dir = normalizedDir;
  }
  if (foilFilter !== "all") {
    query.finish = foilFilter;
  }
  if (typeFilter !== "all") {
    query.type = typeFilter;
  }
  if (colorFilters?.length) {
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
  if (priceMin != null) {
    query.priceMin = String(priceMin);
  }
  if (priceMax != null) {
    query.priceMax = String(priceMax);
  }
  if (powerMin != null) {
    query.powMin = String(powerMin);
  }
  if (toughnessMin != null) {
    query.tghMin = String(toughnessMin);
  }
  if (storageFilters?.length) {
    query.storage = storageFilters.join(",");
  }
  return query;
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
  const priceMin = parseOptionalNumber(route.query?.priceMin);
  const priceMax = parseOptionalNumber(route.query?.priceMax);
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
    priceMin,
    priceMax,
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
  family = false,
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
  priceMin = null,
  priceMax = null,
  powerMin = null,
  toughnessMin = null,
  storageFilters = [],
  lens = "",
  viewMode = "gallery",
  editArtStyles = false,
} = {}) {
  const query = collectionScopeToQuery(setCode, family ? "" : artStyle, family);
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
  if (priceMin != null) {
    query.priceMin = String(priceMin);
  }
  if (priceMax != null) {
    query.priceMax = String(priceMax);
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

export function setScopeToQuery(setCode, family = false) {
  if (!setCode || String(setCode).toLowerCase() === "all") {
    return {};
  }
  const query = { set: String(setCode) };
  if (family) {
    query.family = "1";
  }
  return query;
}

export function collectionScopeToQuery(setCode, artStyle = "", family = false) {
  const query = setScopeToQuery(setCode, family);
  if (!family && artStyle) {
    query.art = artStyle;
  }
  return query;
}

export function collectionRouteForSet(setCode, artStyle = "", family = false) {
  const code = String(setCode || "").trim();
  if (!code || code.toLowerCase() === "all") {
    return { path: "/collection/all" };
  }
  return {
    path: "/collection/all",
    query: collectionScopeToQuery(code, artStyle, family),
  };
}

export function searchFiltersFromRoute(route) {
  const owned = route.query?.owned;
  let ownedFilter = "owned";
  if (owned === "all") {
    ownedFilter = "all";
  } else if (owned === "owned") {
    ownedFilter = "owned";
  } else if (owned === "unowned") {
    // Search no longer exposes Unowned; treat legacy links as All.
    ownedFilter = "all";
  }

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

  const keywordParam = route.query?.keyword;
  const keywordQuery = typeof keywordParam === "string" ? keywordParam.trim() : "";

  const rarityParam = route.query?.rarity;
  const rarityFilter = typeof rarityParam === "string" && ALL_CARDS_RARITY_FILTERS.has(rarityParam)
    ? rarityParam
    : "all";

  const cmcMin = parseOptionalNumber(route.query?.cmcMin);
  const cmcMax = parseOptionalNumber(route.query?.cmcMax);
  const priceMin = parseOptionalNumber(route.query?.priceMin);
  const priceMax = parseOptionalNumber(route.query?.priceMax);
  const powerMin = parseOptionalNumber(route.query?.powMin);
  const toughnessMin = parseOptionalNumber(route.query?.tghMin);

  const storageFilters = parseStorageFiltersFromRoute(route);
  const roleFilters = parseRoleFiltersFromRoute(route);

  const viewParam = route.query?.view;
  const viewMode = viewParam === "list" ? "list" : "gallery";

  const sort = normalizeSearchSort(route.query?.sort);
  const sortDir = normalizeSearchSortDir(sort, route.query?.dir);

  return {
    ownedFilter,
    foilFilter,
    page,
    typeFilter,
    colorFilters,
    searchQuery,
    textSearchQuery,
    creatureTypeQuery,
    keywordQuery,
    rarityFilter,
    cmcMin,
    cmcMax,
    priceMin,
    priceMax,
    powerMin,
    toughnessMin,
    storageFilters,
    roleFilters,
    viewMode,
    sort,
    sortDir,
  };
}

export function searchRouteQuery({
  ownedFilter = "owned",
  foilFilter = "all",
  typeFilter = "all",
  colorFilters = [],
  searchQuery = "",
  textSearchQuery = "",
  creatureTypeQuery = "",
  keywordQuery = "",
  rarityFilter = "all",
  cmcMin = null,
  cmcMax = null,
  priceMin = null,
  priceMax = null,
  powerMin = null,
  toughnessMin = null,
  storageFilters = [],
  roleFilters = [],
  page = 1,
  viewMode = "gallery",
  sort = "newest",
  sortDir = "",
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
  if (keywordQuery) {
    query.keyword = keywordQuery;
  }
  if (ownedFilter !== "owned") {
    query.owned = ownedFilter === "unowned" ? "all" : ownedFilter;
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
  if (priceMin != null) {
    query.priceMin = String(priceMin);
  }
  if (priceMax != null) {
    query.priceMax = String(priceMax);
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
  if (roleFilters.length) {
    query.roles = roleFilters.join(",");
  }
  const normalizedSort = normalizeSearchSort(sort);
  const normalizedDir = normalizeSearchSortDir(normalizedSort, sortDir);
  if (normalizedSort !== "newest") {
    query.sort = normalizedSort;
  }
  if (normalizedDir !== defaultSearchSortDirForField(normalizedSort)) {
    query.dir = normalizedDir;
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
  const { setCode, artStyle, family } = collectionScopeFromRoute(route);
  if (targetPath === "/collection/search") {
    return searchNavQuery(route);
  }
  if (targetPath === "/collection/roles") {
    if (route.path === "/collection/roles") {
      return rolesRouteQuery(rolesFiltersFromRoute(route));
    }
    return rolesRouteQuery({ role: "", sort: "name", sortDir: "asc", storageFilters: [] });
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
    return allCardsRouteQuery({ setCode, artStyle, family, ...filters });
  }
  return collectionScopeToQuery(setCode, artStyle, family);
}

export function setScopeQueryFromRoute(route) {
  if (route.path === "/collection/all") {
    const { setCode, artStyle, family } = collectionScopeFromRoute(route);
    return allCardsRouteQuery({
      setCode,
      artStyle,
      family,
      ...allCardsFiltersFromRoute(route),
    });
  }
  const { setCode, artStyle, family } = collectionScopeFromRoute(route);
  return collectionScopeToQuery(setCode, artStyle, family);
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
