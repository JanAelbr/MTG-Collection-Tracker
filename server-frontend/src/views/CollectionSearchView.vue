<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ignoreAborted } from "../api";
import BrowseSelect from "../components/BrowseSelect.vue";
import CollectionAllFilters from "../components/CollectionAllFilters.vue";
import CollectionMobileFilterSheet from "../components/CollectionMobileFilterSheet.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import SearchArtBrowser from "../components/SearchArtBrowser.vue";
import SearchResultsList from "../components/SearchResultsList.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import CollectionGalleryScaleControl from "../components/CollectionGalleryScaleControl.vue";
import CollectionGroupTree from "../components/CollectionGroupTree.vue";
import FilterSidebar from "../components/FilterSidebar.vue";
import StorageGroupGallery from "../components/StorageGroupGallery.vue";
import { formatSetDropdownLabel } from "../utils/format";
import { parseOptionalNumber } from "../utils/collectionFilters";
import { COLLECTION_TYPE_LABELS, COLLECTION_TYPE_ORDER } from "../utils/collectionTypes";
import { searchFiltersFromRoute, searchRouteQuery, searchViewModeFromRoute, defaultSearchSortDirForField, normalizeSearchSort } from "../utils/setScope";
import { getStoredColorFilterMode, storeColorFilterMode } from "../utils/filterStorage";
import { resolveSetIconUri } from "../utils/scryfall";
import {
  collectGroupPaths,
  groupSearchCards,
  normalizeGroupByLevels,
  SEARCH_GROUP_BY_OPTIONS,
} from "../utils/searchResults";

const PAGE_SIZE = 25;
const SEARCH_SET_CODE = "All";
const LARGE_GROUP_CARD_COUNT = 24;

const route = useRoute();
const router = useRouter();

const meta = ref(null);
const searchFacets = ref({ creatureTypes: [], keywords: [] });
const accumulatedCards = ref([]);
const searchTotalMatches = ref(0);
const loadedPages = ref(0);
const loadingMore = ref(false);
const artExplorer = ref(null);
const artPanelLoading = ref(false);
const selectedBrowseName = ref("");
const artSelectedIndex = ref(0);
const variantCache = ref({});
const searchQuery = ref("");
const textSearchQuery = ref("");
const creatureTypeQuery = ref("");
const keywordQuery = ref("");
const searchInput = ref("");
const textSearchInput = ref("");
const creatureTypeInput = ref("");
const keywordInput = ref("");
const searchInputRef = ref(null);
const ownedFilter = ref("owned");
const foilFilter = ref("all");
const typeFilter = ref("all");
const colorFilters = ref([]);
const colorMode = ref(getStoredColorFilterMode());
const storageFilters = ref([]);
const roleFilters = ref([]);
const rarityFilter = ref("all");
const cmcMin = ref("");
const cmcMax = ref("");
const priceMin = ref("");
const priceMax = ref("");
const powerMin = ref("");
const toughnessMin = ref("");
const mobileFiltersOpen = ref(false);
const searchViewMode = ref("gallery");
const searchSort = ref("newest");
const searchSortDir = ref("desc");
const searchGroupByLevels = ref([]);
const collapsedSearchGroups = ref(new Set());
const loadingAll = ref(false);
const routeSyncReady = ref(false);
const virtualGridRef = ref(null);
const filterSidebarRef = ref(null);
const { loading, run } = useAsyncLoad();
const { collectionCardScale, settings: pricingSettings } = usePricingSettings();
let searchRequestToken = 0;

const sets = computed(() => meta.value?.sets || []);
const cards = computed(() => accumulatedCards.value);
const totalMatches = computed(() => searchTotalMatches.value);
const totalPages = computed(() => Math.max(1, Math.ceil(totalMatches.value / PAGE_SIZE)));
const hasMoreResults = computed(() => loadedPages.value < totalPages.value);
const isGroupedResults = computed(() => searchGroupByLevels.value.length > 0);
const searchResultGroups = computed(() => {
  if (!isGroupedResults.value) {
    return [];
  }
  return groupSearchCards(accumulatedCards.value, searchGroupByLevels.value, {
    setLabelFor: setLabel,
  });
});
const hasActiveSearch = computed(() => Boolean(
  searchQuery.value.trim()
  || textSearchQuery.value.trim()
  || creatureTypeQuery.value.trim()
  || keywordQuery.value.trim()
  || roleFilters.value.length
  || colorFilters.value.length
  || typeFilter.value !== "all",
));
const isListView = computed(() => searchViewMode.value === "list");
const showCreatureTypeFilter = computed(() => typeFilter.value === "creature");

const cardTypeOptions = computed(() => [
  { value: "all", label: "Any card type" },
  ...COLLECTION_TYPE_ORDER.map((type) => ({
    value: type,
    label: COLLECTION_TYPE_LABELS[type] || type,
  })),
]);

const creatureTypeOptions = computed(() => {
  const options = [{ value: "", label: "Any creature type" }];
  const seen = new Set([""]);
  for (const type of searchFacets.value.creatureTypes || []) {
    const value = String(type || "").trim();
    if (!value) {
      continue;
    }
    const key = value.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    options.push({ value, label: value });
  }
  const current = creatureTypeInput.value.trim();
  if (current && !seen.has(current.toLowerCase())) {
    options.push({ value: current, label: current });
  }
  return options;
});

const keywordOptions = computed(() => {
  const options = [{ value: "", label: "Any keyword" }];
  const seen = new Set([""]);
  for (const keyword of searchFacets.value.keywords || []) {
    const value = String(keyword || "").trim();
    if (!value) {
      continue;
    }
    const key = value.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    options.push({ value, label: value });
  }
  const current = keywordInput.value.trim();
  if (current && !seen.has(current.toLowerCase())) {
    options.push({ value: current, label: current });
  }
  return options;
});

const setLabels = computed(() => {
  const labels = new Map();
  for (const set of sets.value) {
    labels.set(set.setCode, formatSetDropdownLabel(set));
  }
  return labels;
});

const setsByCode = computed(() => {
  const byCode = new Map();
  for (const set of sets.value) {
    byCode.set(String(set.setCode || "").toUpperCase(), set);
  }
  return byCode;
});

function setIconForCode(code) {
  const normalized = String(code || "").trim().toUpperCase();
  if (!normalized || normalized === "—") {
    return null;
  }
  return resolveSetIconUri(setsByCode.value.get(normalized) || { setCode: normalized });
}

function searchApiParams() {
  return {
    setCode: SEARCH_SET_CODE,
    ownedFilter: ownedFilter.value,
    foilFilter: "all",
    typeFilter: typeFilter.value,
    colorFilters: colorFilters.value,
    colorMode: colorMode.value,
    storageFilters: storageFilters.value,
    roleFilters: roleFilters.value,
    rarityFilter: rarityFilter.value,
    cmcMin: parseOptionalNumber(cmcMin.value),
    cmcMax: parseOptionalNumber(cmcMax.value),
    priceMin: parseOptionalNumber(priceMin.value),
    priceMax: parseOptionalNumber(priceMax.value),
    powerMin: parseOptionalNumber(powerMin.value),
    toughnessMin: parseOptionalNumber(toughnessMin.value),
    sort: searchSort.value,
    dir: searchSortDir.value,
  };
}

function matchFacetValue(value, catalog) {
  const needle = String(value || "").trim();
  if (!needle) {
    return "";
  }
  const lower = needle.toLowerCase();
  for (const item of catalog || []) {
    if (String(item).toLowerCase() === lower) {
      return String(item);
    }
  }
  return needle;
}

function syncFiltersFromRoute() {
  const filters = searchFiltersFromRoute(route);
  ownedFilter.value = filters.ownedFilter;
  foilFilter.value = "all";
  typeFilter.value = filters.typeFilter;
  colorFilters.value = [...filters.colorFilters];
  colorMode.value = filters.colorMode || getStoredColorFilterMode();
  storageFilters.value = [...filters.storageFilters];
  roleFilters.value = [...filters.roleFilters];
  searchQuery.value = filters.searchQuery;
  textSearchQuery.value = filters.textSearchQuery;
  const creatureType = typeFilter.value === "creature"
    ? matchFacetValue(filters.creatureTypeQuery, searchFacets.value.creatureTypes)
    : "";
  const keyword = matchFacetValue(filters.keywordQuery || "", searchFacets.value.keywords);
  creatureTypeQuery.value = creatureType;
  keywordQuery.value = keyword;
  searchInput.value = filters.searchQuery;
  textSearchInput.value = filters.textSearchQuery;
  creatureTypeInput.value = creatureType;
  keywordInput.value = keyword;
  rarityFilter.value = filters.rarityFilter;
  cmcMin.value = filters.cmcMin != null ? String(filters.cmcMin) : "";
  cmcMax.value = filters.cmcMax != null ? String(filters.cmcMax) : "";
  priceMin.value = filters.priceMin != null ? String(filters.priceMin) : "";
  priceMax.value = filters.priceMax != null ? String(filters.priceMax) : "";
  powerMin.value = filters.powerMin != null ? String(filters.powerMin) : "";
  toughnessMin.value = filters.toughnessMin != null ? String(filters.toughnessMin) : "";
  searchViewMode.value = filters.viewMode;
  searchSort.value = filters.sort;
  searchSortDir.value = filters.sortDir;
}

function setLabel(code) {
  return setLabels.value.get(code) || code;
}

function stripSetScopeFromRoute() {
  if (!route.query.set && !route.query.art) {
    return false;
  }
  syncSearchRoute();
  return true;
}

function syncSearchRoute() {
  router.replace({
    path: route.path,
    query: searchRouteQuery({
      ownedFilter: ownedFilter.value,
      foilFilter: "all",
      typeFilter: typeFilter.value,
      colorFilters: colorFilters.value,
      colorMode: colorMode.value,
      storageFilters: storageFilters.value,
      searchQuery: searchQuery.value.trim(),
      textSearchQuery: textSearchQuery.value.trim(),
      creatureTypeQuery: typeFilter.value === "creature" ? creatureTypeQuery.value.trim() : "",
      keywordQuery: keywordQuery.value.trim(),
      roleFilters: roleFilters.value,
      rarityFilter: rarityFilter.value,
      cmcMin: parseOptionalNumber(cmcMin.value),
      cmcMax: parseOptionalNumber(cmcMax.value),
      priceMin: parseOptionalNumber(priceMin.value),
      priceMax: parseOptionalNumber(priceMax.value),
      powerMin: parseOptionalNumber(powerMin.value),
      toughnessMin: parseOptionalNumber(toughnessMin.value),
      viewMode: searchViewMode.value,
      sort: searchSort.value,
      sortDir: searchSortDir.value,
    }),
  });
}

function setSearchViewMode(mode) {
  if (searchViewMode.value === mode) {
    return;
  }
  searchViewMode.value = mode;
  syncSearchRoute();
}

function resetSearchResults() {
  accumulatedCards.value = [];
  searchTotalMatches.value = 0;
  loadedPages.value = 0;
  variantCache.value = {};
  collapsedSearchGroups.value = new Set();
}

function applySearchPayload(payload, { append = false } = {}) {
  const nextCards = payload?.cards || [];
  searchTotalMatches.value = payload?.totalMatches ?? 0;
  accumulatedCards.value = append
    ? [...accumulatedCards.value, ...nextCards]
    : nextCards;
  loadedPages.value = payload?.page ?? 1;
}

async function fetchSearchPage(pageNum) {
  const nameTerm = searchQuery.value.trim();
  const textTerm = textSearchQuery.value.trim();
  const creatureTypeTerm = showCreatureTypeFilter.value ? creatureTypeQuery.value.trim() : "";
  const keywordTerm = keywordQuery.value.trim();
  if (
    !nameTerm
    && !textTerm
    && !creatureTypeTerm
    && !keywordTerm
    && !roleFilters.value.length
    && !colorFilters.value.length
    && typeFilter.value === "all"
  ) {
    return null;
  }
  const token = ++searchRequestToken;
  const payload = await ignoreAborted(api.searchCards({
    q: nameTerm,
    text: textTerm,
    creatureType: creatureTypeTerm,
    keyword: keywordTerm,
    ...searchApiParams(),
    page: pageNum,
    pageSize: PAGE_SIZE,
  }));
  if (!payload || token !== searchRequestToken) {
    return null;
  }
  return payload;
}

async function loadMeta() {
  const next = await ignoreAborted(api.getReportsMeta());
  if (next) {
    meta.value = next;
  }
}

async function loadSearchFacets() {
  const next = await ignoreAborted(api.getSearchFacets());
  if (next) {
    searchFacets.value = {
      creatureTypes: next.creatureTypes || [],
      keywords: next.keywords || [],
    };
  }
}

async function onCreatureTypeSelect(value) {
  const next = String(value || "").trim();
  creatureTypeInput.value = next;
  if (next === creatureTypeQuery.value.trim()) {
    return;
  }
  creatureTypeQuery.value = next;
  closeArtExplorer();
  syncSearchRoute();
}

function clearCreatureTypeFilter() {
  if (!creatureTypeInput.value && !creatureTypeQuery.value) {
    return;
  }
  creatureTypeInput.value = "";
  creatureTypeQuery.value = "";
}

async function onCardTypeSelect(value) {
  const next = String(value || "all").trim() || "all";
  if (typeFilter.value === next) {
    return;
  }
  typeFilter.value = next;
  if (next !== "creature") {
    clearCreatureTypeFilter();
  }
  closeArtExplorer();
  syncSearchRoute();
}

async function onKeywordSelect(value) {
  const next = String(value || "").trim();
  keywordInput.value = next;
  if (next === keywordQuery.value.trim()) {
    return;
  }
  keywordQuery.value = next;
  closeArtExplorer();
  syncSearchRoute();
}

async function loadResults({ autoSelectFirst = false } = {}) {
  const nameTerm = searchQuery.value.trim();
  const textTerm = textSearchQuery.value.trim();
  const creatureTypeTerm = showCreatureTypeFilter.value ? creatureTypeQuery.value.trim() : "";
  const keywordTerm = keywordQuery.value.trim();
  if (
    !nameTerm
    && !textTerm
    && !creatureTypeTerm
    && !keywordTerm
    && !roleFilters.value.length
    && !colorFilters.value.length
    && typeFilter.value === "all"
  ) {
    resetSearchResults();
    if (autoSelectFirst) {
      closeArtExplorer();
    }
    return;
  }
  await run(async (isCurrent) => {
    resetSearchResults();
    const payload = await fetchSearchPage(1);
    if (!isCurrent() || !payload) {
      return;
    }
    applySearchPayload(payload, { append: false });
  });
  if (isGroupedResults.value && hasMoreResults.value) {
    await loadAllResults();
  } else if (!isListView.value) {
    await fillVisibleResults();
  }
  if (autoSelectFirst) {
    await autoSelectFirstResult();
  }
}

async function loadMoreResults() {
  if (loadingMore.value || loading.value || loadingAll.value || !hasMoreResults.value) {
    return;
  }
  loadingMore.value = true;
  try {
    const payload = await fetchSearchPage(loadedPages.value + 1);
    if (payload) {
      applySearchPayload(payload, { append: true });
    }
  } finally {
    loadingMore.value = false;
  }
}

async function loadAllResults() {
  if (loadingAll.value || loading.value || !hasMoreResults.value) {
    return;
  }
  loadingAll.value = true;
  try {
    while (hasMoreResults.value) {
      const before = loadedPages.value;
      const payload = await fetchSearchPage(loadedPages.value + 1);
      if (!payload) {
        break;
      }
      applySearchPayload(payload, { append: true });
      if (loadedPages.value === before) {
        break;
      }
    }
  } finally {
    loadingAll.value = false;
  }
}

async function fillVisibleResults() {
  if (isListView.value || isGroupedResults.value) {
    return;
  }
  await nextTick();
  const root = virtualGridRef.value?.rootRef;
  if (!root || !hasMoreResults.value || loadingMore.value || loading.value || loadingAll.value) {
    return;
  }
  const scrollable = root.scrollHeight > root.clientHeight + 8;
  if (!scrollable) {
    await loadMoreResults();
    if (hasMoreResults.value) {
      await fillVisibleResults();
    }
  }
}

function isLargeSearchGroup(group) {
  return (group?.cards?.length || 0) > LARGE_GROUP_CARD_COUNT;
}

function isSearchGroupExpanded(path) {
  return !collapsedSearchGroups.value.has(path);
}

function toggleSearchGroup(path) {
  const next = new Set(collapsedSearchGroups.value);
  if (next.has(path)) {
    next.delete(path);
  } else {
    next.add(path);
  }
  collapsedSearchGroups.value = next;
}

function expandAllSearchGroups() {
  collapsedSearchGroups.value = new Set();
}

function collapseAllSearchGroups() {
  collapsedSearchGroups.value = new Set(collectGroupPaths(searchResultGroups.value));
}

function searchGroupByOptionsForLevel(levelIndex) {
  const used = new Set(searchGroupByLevels.value.slice(0, levelIndex));
  return SEARCH_GROUP_BY_OPTIONS.filter(
    (option) => option.value === "none" || !used.has(option.value),
  );
}

async function onSearchGroupLevelChange(levelIndex, event) {
  const nextValue = String(event?.target?.value || "none");
  const next = searchGroupByLevels.value.slice(0, levelIndex);
  if (nextValue !== "none") {
    next.push(nextValue);
  }
  const normalized = normalizeGroupByLevels(next, { emptyDefault: [] });
  const changed = normalized.join(",") !== searchGroupByLevels.value.join(",");
  searchGroupByLevels.value = normalized;
  collapsedSearchGroups.value = new Set();
  if (changed && normalized.length && hasMoreResults.value) {
    await loadAllResults();
  }
}

async function autoSelectFirstResult() {
  const first = accumulatedCards.value[0];
  if (!first?.name) {
    closeArtExplorer();
    return;
  }
  try {
    await loadNameVariants(first.name);
    minimizeSearchFilters();
  } catch {
    closeArtExplorer();
  }
}

function setOwnedFilter(value) {
  const next = value === "unowned" ? "all" : value;
  if (ownedFilter.value === next) {
    return;
  }
  ownedFilter.value = next;
}

function onTypeFilterChange(event) {
  const next = event.target.value || "all";
  if (typeFilter.value === next) {
    return;
  }
  typeFilter.value = next;
  if (next !== "creature") {
    clearCreatureTypeFilter();
  }
}

function toggleColorFilter(color) {
  if (colorFilters.value.includes(color)) {
    colorFilters.value = colorFilters.value.filter((item) => item !== color);
  } else {
    colorFilters.value = [...colorFilters.value, color];
  }
}

function clearColorFilters() {
  colorFilters.value = [];
}

function setColorMode(mode) {
  const next = mode === "includes" ? "includes" : "exact";
  if (colorMode.value === next) {
    return;
  }
  colorMode.value = next;
  storeColorFilterMode(next);
}

function toggleStorageFilter(slug) {
  if (storageFilters.value.includes(slug)) {
    storageFilters.value = storageFilters.value.filter((item) => item !== slug);
  } else {
    storageFilters.value = [...storageFilters.value, slug];
  }
}

function clearStorageFilters() {
  storageFilters.value = [];
}

function setStorageFilters(values) {
  storageFilters.value = Array.isArray(values) ? [...values] : [];
}

function toggleRoleFilter(role) {
  if (roleFilters.value.includes(role)) {
    roleFilters.value = roleFilters.value.filter((item) => item !== role);
  } else {
    roleFilters.value = [...roleFilters.value, role];
  }
}

function clearRoleFilters() {
  roleFilters.value = [];
}

function setRoleFilters(values) {
  roleFilters.value = Array.isArray(values) ? [...values] : [];
}

function onRarityFilterChange(event) {
  const next = event.target.value || "all";
  if (rarityFilter.value === next) {
    return;
  }
  rarityFilter.value = next;
}

function updateSearchSort(event) {
  const next = normalizeSearchSort(event?.target?.value);
  if (searchSort.value === next) {
    return;
  }
  searchSort.value = next;
  searchSortDir.value = defaultSearchSortDirForField(next);
}

function toggleSearchSortDir() {
  searchSortDir.value = searchSortDir.value === "asc" ? "desc" : "asc";
}

function updateDetailFilter(field, value) {
  const next = String(value ?? "");
  if (field === "cmcMin" && cmcMin.value === next) return;
  if (field === "cmcMax" && cmcMax.value === next) return;
  if (field === "priceMin" && priceMin.value === next) return;
  if (field === "priceMax" && priceMax.value === next) return;
  if (field === "powerMin" && powerMin.value === next) return;
  if (field === "toughnessMin" && toughnessMin.value === next) return;
  if (field === "cmcMin") cmcMin.value = next;
  if (field === "cmcMax") cmcMax.value = next;
  if (field === "priceMin") priceMin.value = next;
  if (field === "priceMax") priceMax.value = next;
  if (field === "powerMin") powerMin.value = next;
  if (field === "toughnessMin") toughnessMin.value = next;
}

async function setCollectionCardScale(scale) {
  await savePricingSettings({ collectionCardScale: Number(scale) });
}

function variantPrintKey(card) {
  return `${card?.setCode || ""}|${String(card?.collectorNumber ?? "")}|${card?.artStyle || ""}`;
}

function cheapestValueKey(card) {
  const raw = Number(card?.currentValue);
  if (!Number.isFinite(raw) || raw <= 0) {
    return [1, 0];
  }
  return [0, raw];
}

function sortVariantsCheapestFirst(variants) {
  return [...(variants || [])].sort((left, right) => {
    const leftKey = cheapestValueKey(left);
    const rightKey = cheapestValueKey(right);
    if (leftKey[0] !== rightKey[0]) {
      return leftKey[0] - rightKey[0];
    }
    if (leftKey[1] !== rightKey[1]) {
      return leftKey[1] - rightKey[1];
    }
    return variantPrintKey(left).localeCompare(variantPrintKey(right));
  });
}

function findVariantIndex(variants, card) {
  if (!card || !variants?.length) {
    return 0;
  }
  const key = variantPrintKey(card);
  const index = variants.findIndex((variant) => variantPrintKey(variant) === key);
  return index >= 0 ? index : 0;
}

function displayedCardForName(name) {
  return accumulatedCards.value.find((card) => card.name === name) || null;
}

function replaceDisplayedVariant(name, variant, variantCount) {
  const index = accumulatedCards.value.findIndex((card) => card.name === name);
  if (index < 0 || !variant) {
    return;
  }
  const previous = accumulatedCards.value[index];
  const next = {
    ...variant,
    variantCount: Number(variantCount || previous.variantCount || 1),
  };
  accumulatedCards.value = [
    ...accumulatedCards.value.slice(0, index),
    next,
    ...accumulatedCards.value.slice(index + 1),
  ];
}

async function ensureVariantsCached(name) {
  const cached = variantCache.value[name];
  if (cached?.variants?.length) {
    return cached;
  }
  const payload = await api.getSearchNameVariants({
    name,
    ...searchApiParams(),
  });
  const variants = sortVariantsCheapestFirst(payload?.variants || []);
  const entry = {
    variants,
    index: findVariantIndex(variants, displayedCardForName(name)),
  };
  variantCache.value = {
    ...variantCache.value,
    [name]: entry,
  };
  const displayed = displayedCardForName(name);
  if (displayed && Number(displayed.variantCount || 0) !== variants.length) {
    replaceDisplayedVariant(name, displayed, variants.length);
  }
  return entry;
}

async function cycleCardVariant({ name, direction }) {
  const cardName = String(name || "").trim();
  if (!cardName || !direction) {
    return;
  }
  try {
    const entry = await ensureVariantsCached(cardName);
    if (!entry.variants.length) {
      return;
    }
    const count = entry.variants.length;
    const nextIndex = (entry.index + direction + count) % count;
    entry.index = nextIndex;
    variantCache.value = {
      ...variantCache.value,
      [cardName]: { ...entry },
    };
    replaceDisplayedVariant(cardName, entry.variants[nextIndex], count);
    if (artExplorer.value?.name === cardName) {
      artExplorer.value = {
        ...artExplorer.value,
        variants: entry.variants,
      };
      artSelectedIndex.value = nextIndex;
    }
  } catch (error) {
    window.alert(error.message || "Could not load card versions.");
  }
}

async function loadNameVariants(name, { preserveSelection = false } = {}) {
  selectedBrowseName.value = name;
  const current = preserveSelection
    ? artExplorer.value?.variants?.[artSelectedIndex.value]
    : displayedCardForName(name);
  artPanelLoading.value = true;
  if (!preserveSelection && artExplorer.value?.name !== name) {
    artExplorer.value = null;
  }
  try {
    const entry = await ensureVariantsCached(name);
    const variants = entry.variants;
    artExplorer.value = {
      name,
      variants,
      totalVariants: variants.length,
    };
    if (preserveSelection && current) {
      artSelectedIndex.value = findVariantIndex(variants, current);
    } else if (current) {
      artSelectedIndex.value = findVariantIndex(variants, current);
    } else {
      artSelectedIndex.value = entry.index || 0;
    }
    entry.index = artSelectedIndex.value;
    variantCache.value = {
      ...variantCache.value,
      [name]: { ...entry },
    };
  } finally {
    artPanelLoading.value = false;
  }
}

async function browseCardName(name) {
  try {
    await loadNameVariants(name);
    minimizeSearchFilters();
  } catch (error) {
    window.alert(error.message || "Could not load card variants.");
  }
}

function minimizeSearchFilters() {
  filterSidebarRef.value?.collapse?.({ persist: false });
}

function closeArtExplorer() {
  artExplorer.value = null;
  artSelectedIndex.value = 0;
  artPanelLoading.value = false;
  selectedBrowseName.value = "";
}

function onArtSelectedIndexChange(index) {
  const nextIndex = Number(index) || 0;
  artSelectedIndex.value = nextIndex;
  const name = artExplorer.value?.name;
  const variants = artExplorer.value?.variants || [];
  if (!name || !variants.length) {
    return;
  }
  const variant = variants[nextIndex];
  if (!variant) {
    return;
  }
  const cached = variantCache.value[name];
  if (cached) {
    variantCache.value = {
      ...variantCache.value,
      [name]: { ...cached, index: nextIndex, variants },
    };
  }
  replaceDisplayedVariant(name, variant, variants.length);
}

async function submitSearch() {
  const nextName = searchInput.value.trim();
  const nextText = textSearchInput.value.trim();
  const nextCreatureType = showCreatureTypeFilter.value ? creatureTypeInput.value.trim() : "";
  const nextKeyword = keywordInput.value.trim();
  const sameQuery = nextName === searchQuery.value.trim()
    && nextText === textSearchQuery.value.trim()
    && nextCreatureType === creatureTypeQuery.value.trim()
    && nextKeyword === keywordQuery.value.trim();
  searchQuery.value = nextName;
  textSearchQuery.value = nextText;
  creatureTypeQuery.value = nextCreatureType;
  creatureTypeInput.value = nextCreatureType;
  keywordQuery.value = nextKeyword;
  closeArtExplorer();
  const hasQuery = Boolean(
    nextName
    || nextText
    || nextCreatureType
    || nextKeyword
    || roleFilters.value.length
    || typeFilter.value !== "all",
  );
  if (sameQuery && hasQuery) {
    await loadResults({ autoSelectFirst: true });
    return;
  }
  if (hasQuery) {
    syncSearchRoute();
    return;
  }
  resetSearchResults();
  syncSearchRoute();
}

async function onArtOwnershipChanged() {
  const activeName = artExplorer.value?.name;
  if (!activeName) {
    return;
  }
  try {
    // Refresh the open art panel only — do not re-run the search query.
    await loadNameVariants(activeName, { preserveSelection: true });
  } catch {
    // Keep the current explorer state if variant refresh fails.
  }
}

watch([ownedFilter, foilFilter, typeFilter, colorFilters, colorMode, storageFilters, roleFilters, rarityFilter, cmcMin, cmcMax, priceMin, priceMax, powerMin, toughnessMin, searchViewMode, searchSort, searchSortDir], () => {
  if (!routeSyncReady.value) {
    return;
  }
  syncSearchRoute();
});

watch(
  () => route.query.view,
  () => {
    if (!routeSyncReady.value) {
      return;
    }
    const nextMode = searchViewModeFromRoute(route);
    if (searchViewMode.value === nextMode) {
      return;
    }
    searchViewMode.value = nextMode;
  },
);

watch(
  () => [
    route.query.q,
    route.query.text,
    route.query.creature,
    route.query.keyword,
    route.query.owned,
    route.query.finish,
    route.query.type,
    route.query.colors,
    route.query.storage,
    route.query.roles,
    route.query.rarity,
    route.query.cmcMin,
    route.query.cmcMax,
    route.query.priceMin,
    route.query.priceMax,
    route.query.powMin,
    route.query.tghMin,
    route.query.sort,
    route.query.dir,
  ],
  async (_value, _oldValue, onCleanup) => {
    if (!routeSyncReady.value) {
      return;
    }
    const prevName = searchQuery.value;
    const prevText = textSearchQuery.value;
    const prevCreatureType = creatureTypeQuery.value;
    const prevKeyword = keywordQuery.value;
    const prevRoles = roleFilters.value.join(",");
    syncFiltersFromRoute();
    let cancelled = false;
    onCleanup(() => {
      cancelled = true;
    });
    if (!hasActiveSearch.value) {
      closeArtExplorer();
      resetSearchResults();
      return;
    }
    const searchChanged = searchQuery.value !== prevName
      || textSearchQuery.value !== prevText
      || creatureTypeQuery.value !== prevCreatureType
      || keywordQuery.value !== prevKeyword
      || roleFilters.value.join(",") !== prevRoles;
    await loadResults({ autoSelectFirst: searchChanged });
    if (cancelled) {
      return;
    }
  },
);

onMounted(async () => {
  syncFiltersFromRoute();
  await Promise.all([fetchPricingSettings(), loadMeta(), loadSearchFacets()]);
  syncFiltersFromRoute();
  routeSyncReady.value = true;
  stripSetScopeFromRoute();
  if (hasActiveSearch.value) {
    await loadResults({ autoSelectFirst: true });
  }
  await nextTick();
  searchInputRef.value?.focus();
});
</script>

<template>
  <div class="reports-page collection-page collection-search-page">
    <div class="page-with-sidebar collection-search-page-layout">
      <div class="page-with-sidebar-main collection-search-main">
        <form
          class="collection-search-form collection-search-page-form"
          role="search"
          @submit.prevent="submitSearch"
        >
          <div class="collection-search-toolbar-row">
            <div
              class="button-group collection-ownership-group collection-ownership-group--binary collection-search-ownership"
              role="group"
              aria-label="Ownership"
            >
              <button
                type="button"
                class="filter-button"
                :class="{ active: ownedFilter === 'owned' }"
                @click="setOwnedFilter('owned')"
              >
                Owned
              </button>
              <button
                type="button"
                class="filter-button"
                :class="{ active: ownedFilter === 'all' }"
                @click="setOwnedFilter('all')"
              >
                All
              </button>
            </div>
            <input
              id="collection-search-page-input"
              ref="searchInputRef"
              v-model="searchInput"
              type="search"
              class="collection-search-input collection-search-page-input"
              placeholder="Card name…"
              autocomplete="off"
              spellcheck="false"
              aria-label="Search cards by name"
            >
            <BrowseSelect
              id="collection-search-page-type-input"
              class="collection-search-page-input collection-search-page-select"
              :model-value="typeFilter"
              :options="cardTypeOptions"
              filterable
              hide-arrows
              portal-panel
              placeholder="Card type…"
              aria-label="Filter by card type"
              @update:model-value="onCardTypeSelect"
            />
            <BrowseSelect
              v-if="showCreatureTypeFilter"
              id="collection-search-page-creature-input"
              class="collection-search-page-input collection-search-page-select"
              :model-value="creatureTypeInput"
              :options="creatureTypeOptions"
              filterable
              hide-arrows
              portal-panel
              placeholder="Creature type…"
              aria-label="Filter by creature type"
              @update:model-value="onCreatureTypeSelect"
            />
            <input
              id="collection-search-page-text-input"
              v-model="textSearchInput"
              type="search"
              class="collection-search-input collection-search-page-input"
              placeholder="Card text…"
              autocomplete="off"
              spellcheck="false"
              aria-label="Search cards by oracle text"
            >
            <BrowseSelect
              id="collection-search-page-keyword-input"
              class="collection-search-page-input collection-search-page-select"
              :model-value="keywordInput"
              :options="keywordOptions"
              filterable
              hide-arrows
              portal-panel
              placeholder="Keyword…"
              aria-label="Filter by keyword ability"
              @update:model-value="onKeywordSelect"
            />
            <button type="submit" class="btn btn-primary collection-search-page-submit">
              Search
            </button>
            <button
              type="button"
              class="btn btn-secondary collection-all-filters-btn collection-search-page-filters-btn"
              @click="mobileFiltersOpen = true"
            >
              Filters
            </button>
          </div>
        </form>

        <div class="collection-search-body">
          <div class="collection-search-results">
            <p
              v-if="hasActiveSearch && !loading && !totalMatches"
              class="manager-stats collection-search-empty-prompt"
            >
              No cards match your search with these filters.
            </p>

            <div v-if="loading && !cards.length" class="storage-empty">
              <LoadingIndicator label="Searching cards…" />
            </div>

            <div
              v-else-if="hasActiveSearch && cards.length"
              class="table-panel cards-panel reports-cards-panel collection-gallery-panel"
            >
              <div class="collection-gallery-toolbar search-results-toolbar">
                <p class="collection-gallery-toolbar-stats">
                  Showing {{ cards.length }} of {{ totalMatches }} cards
                </p>
                <div class="search-results-toolbar-controls">
                  <div
                    class="button-group collection-view-mode-group"
                    role="group"
                    aria-label="View mode"
                  >
                    <button
                      type="button"
                      class="filter-button"
                      :class="{ active: searchViewMode === 'gallery' }"
                      @click="setSearchViewMode('gallery')"
                    >
                      Gallery
                    </button>
                    <button
                      type="button"
                      class="filter-button"
                      :class="{ active: searchViewMode === 'list' }"
                      @click="setSearchViewMode('list')"
                    >
                      List
                    </button>
                  </div>
                  <div class="search-results-group-by-stack">
                    <label class="search-results-group-by">
                      <span>Group by</span>
                      <select
                        :value="searchGroupByLevels[0] || 'none'"
                        aria-label="Group search results"
                        @change="onSearchGroupLevelChange(0, $event)"
                      >
                        <option
                          v-for="option in searchGroupByOptionsForLevel(0)"
                          :key="option.value"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                    <label
                      v-if="searchGroupByLevels[0]"
                      class="search-results-group-by"
                    >
                      <span>Then</span>
                      <select
                        :value="searchGroupByLevels[1] || 'none'"
                        aria-label="Then group search results"
                        @change="onSearchGroupLevelChange(1, $event)"
                      >
                        <option
                          v-for="option in searchGroupByOptionsForLevel(1)"
                          :key="option.value"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                    <label
                      v-if="searchGroupByLevels[1]"
                      class="search-results-group-by"
                    >
                      <span>Then</span>
                      <select
                        :value="searchGroupByLevels[2] || 'none'"
                        aria-label="Then group search results again"
                        @change="onSearchGroupLevelChange(2, $event)"
                      >
                        <option
                          v-for="option in searchGroupByOptionsForLevel(2)"
                          :key="option.value"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                  </div>
                  <button
                    v-if="isGroupedResults && searchResultGroups.length"
                    type="button"
                    class="btn btn-secondary btn-small"
                    @click="collapsedSearchGroups.size ? expandAllSearchGroups() : collapseAllSearchGroups()"
                  >
                    {{ collapsedSearchGroups.size ? "Expand all" : "Collapse all" }}
                  </button>
                  <button
                    v-if="hasMoreResults"
                    type="button"
                    class="btn btn-secondary btn-small"
                    :disabled="loadingAll || loadingMore || loading"
                    @click="loadAllResults"
                  >
                    {{ loadingAll ? "Loading…" : "Load all" }}
                  </button>
                </div>
                <div class="search-results-toolbar-end">
                  <label class="collection-all-sort">
                    <span class="visually-hidden">Sort by</span>
                    <div class="collection-sort-row">
                      <select :value="searchSort" @change="updateSearchSort">
                        <option value="newest">Newest set</option>
                        <option value="name">Name</option>
                        <option value="value">Value</option>
                        <option value="cmc">CMC</option>
                        <option value="power">Power</option>
                        <option value="rarity">Rarity</option>
                      </select>
                      <button
                        type="button"
                        class="btn btn-secondary collection-sort-dir"
                        :title="searchSortDir === 'asc' ? 'Ascending' : 'Descending'"
                        :aria-label="`Sort ${searchSortDir === 'asc' ? 'ascending' : 'descending'}`"
                        @click="toggleSearchSortDir"
                      >
                        {{ searchSortDir === "asc" ? "↑" : "↓" }}
                      </button>
                    </div>
                  </label>
                  <CollectionGalleryScaleControl
                    v-if="!isListView"
                    class="collection-gallery-toolbar-scale"
                    :model-value="collectionCardScale"
                    :options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150, 175, 200, 225, 250]"
                    @update:model-value="setCollectionCardScale"
                  />
                </div>
              </div>
              <GalleryLoadingOverlay :loading="(loading && !loadingMore && !loadingAll) || loadingAll" :label="loadingAll ? 'Loading all cards…' : 'Searching cards…'">
                <div v-if="isGroupedResults" class="search-results-groups">
                  <CollectionGroupTree
                    :groups="searchResultGroups"
                    :is-expanded="isSearchGroupExpanded"
                    :set-icon-for="setIconForCode"
                    @toggle="toggleSearchGroup"
                  >
                    <template #leaf="{ group }">
                      <SearchResultsList
                        v-if="isListView"
                        :cards="group.cards"
                        :selected-name="selectedBrowseName"
                        :set-label-for="setLabel"
                        @browse-name="browseCardName"
                      />
                      <StorageGroupGallery
                        v-else
                        :cards="group.cards"
                        :card-scale="collectionCardScale"
                        :scrollable="isLargeSearchGroup(group)"
                        :show-unowned-badge="false"
                        :show-favorites="false"
                        browse-names
                        :selected-name="selectedBrowseName"
                        @browse-name="browseCardName"
                        @cycle-variant="cycleCardVariant"
                        @ownership-changed="onArtOwnershipChanged"
                      />
                    </template>
                  </CollectionGroupTree>
                </div>
                <VirtualizedCollectionCardGrid
                  v-else-if="!isListView"
                  ref="virtualGridRef"
                  :cards="cards"
                  :show-unowned-badge="false"
                  :card-scale="collectionCardScale"
                  :has-more="hasMoreResults"
                  browse-names
                  :selected-name="selectedBrowseName"
                  @browse-name="browseCardName"
                  @cycle-variant="cycleCardVariant"
                  @load-more="loadMoreResults"
                  @ownership-changed="onArtOwnershipChanged"
                />
                <SearchResultsList
                  v-else
                  :cards="cards"
                  :selected-name="selectedBrowseName"
                  :set-label-for="setLabel"
                  :loading-more="loadingMore"
                  :has-more="hasMoreResults"
                  @browse-name="browseCardName"
                  @load-more="loadMoreResults"
                />
              </GalleryLoadingOverlay>
              <p v-if="loadingMore || loadingAll" class="collection-search-load-more-status">
                <LoadingIndicator :label="loadingAll ? 'Loading all cards…' : 'Loading more cards…'" />
              </p>
            </div>

            <p
              v-else-if="!hasActiveSearch"
              class="collection-search-results-hint collection-search-empty-prompt"
            >
              Search for a card name, card type, keyword, or rules text to browse art versions across your collection.
            </p>
          </div>

          <aside v-if="artExplorer || artPanelLoading" class="collection-search-detail">
            <div
              v-if="artPanelLoading && !artExplorer"
              class="collection-search-detail-loading"
            >
              <LoadingIndicator label="Loading card…" />
            </div>
            <SearchArtBrowser
              v-else-if="artExplorer"
              sidebar
              :name="artExplorer.name"
              :variants="artExplorer.variants"
              :selected-index="artSelectedIndex"
              :set-label-for="setLabel"
              @update:selected-index="onArtSelectedIndexChange"
              @close="closeArtExplorer"
              @ownership-changed="onArtOwnershipChanged"
            />
          </aside>
        </div>
      </div>

      <FilterSidebar
        ref="filterSidebarRef"
        class="collection-desktop-filters collection-search-filters-sidebar"
      >
        <CollectionAllFilters
          :is-all-view="true"
          :is-all-sets-view="true"
          :art-styles="[]"
          :owned-filter="ownedFilter"
          :foil-filter="foilFilter"
          :type-filter="typeFilter"
          :color-filters="colorFilters"
          :color-mode="colorMode"
          :storage-filters="storageFilters"
          :role-filters="roleFilters"
          :rarity-filter="rarityFilter"
          :cmc-min="cmcMin"
          :cmc-max="cmcMax"
          :price-min="priceMin"
          :price-max="priceMax"
          :power-min="powerMin"
          :toughness-min="toughnessMin"
          :show-sort="false"
          sort-mode="search"
          :all-cards-sort="searchSort"
          :all-cards-sort-dir="searchSortDir"
          :show-role-filter="true"
          :show-finish-filter="false"
          :show-ownership-filter="false"
          :show-unowned-filter="false"
          @set-owned-filter="setOwnedFilter"
          @type-filter-change="onTypeFilterChange"
          @toggle-color-filter="toggleColorFilter"
          @clear-color-filters="clearColorFilters"
          @update:color-mode="setColorMode"
          @toggle-storage-filter="toggleStorageFilter"
          @clear-storage-filters="clearStorageFilters"
          @set-storage-filters="setStorageFilters"
          @toggle-role-filter="toggleRoleFilter"
          @clear-role-filters="clearRoleFilters"
          @set-role-filters="setRoleFilters"
          @rarity-filter-change="onRarityFilterChange"
          @update:cmc-min="updateDetailFilter('cmcMin', $event)"
          @update:cmc-max="updateDetailFilter('cmcMax', $event)"
          @update:price-min="updateDetailFilter('priceMin', $event)"
          @update:price-max="updateDetailFilter('priceMax', $event)"
          @update:power-min="updateDetailFilter('powerMin', $event)"
          @update:toughness-min="updateDetailFilter('toughnessMin', $event)"
        />
      </FilterSidebar>
    </div>

    <CollectionMobileFilterSheet
      :open="mobileFiltersOpen"
      @close="mobileFiltersOpen = false"
    >
      <CollectionAllFilters
        :is-all-view="true"
        :is-all-sets-view="true"
        :art-styles="[]"
        :owned-filter="ownedFilter"
        :foil-filter="foilFilter"
        :type-filter="typeFilter"
        :color-filters="colorFilters"
        :color-mode="colorMode"
        :storage-filters="storageFilters"
        :role-filters="roleFilters"
        :rarity-filter="rarityFilter"
        :cmc-min="cmcMin"
        :cmc-max="cmcMax"
        :price-min="priceMin"
        :price-max="priceMax"
        :power-min="powerMin"
        :toughness-min="toughnessMin"
        :show-sort="false"
        sort-mode="search"
        :all-cards-sort="searchSort"
        :all-cards-sort-dir="searchSortDir"
        :show-role-filter="true"
        :show-finish-filter="false"
        :show-unowned-filter="false"
        @set-owned-filter="setOwnedFilter"
        @type-filter-change="onTypeFilterChange"
        @toggle-color-filter="toggleColorFilter"
        @clear-color-filters="clearColorFilters"
        @update:color-mode="setColorMode"
        @toggle-storage-filter="toggleStorageFilter"
        @clear-storage-filters="clearStorageFilters"
        @set-storage-filters="setStorageFilters"
        @toggle-role-filter="toggleRoleFilter"
        @clear-role-filters="clearRoleFilters"
        @set-role-filters="setRoleFilters"
        @rarity-filter-change="onRarityFilterChange"
        @update:cmc-min="updateDetailFilter('cmcMin', $event)"
        @update:cmc-max="updateDetailFilter('cmcMax', $event)"
        @update:price-min="updateDetailFilter('priceMin', $event)"
        @update:price-max="updateDetailFilter('priceMax', $event)"
        @update:power-min="updateDetailFilter('powerMin', $event)"
        @update:toughness-min="updateDetailFilter('toughnessMin', $event)"
      />
    </CollectionMobileFilterSheet>
  </div>
</template>
