<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache, ignoreAborted } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import CollectionAllFilters from "../components/CollectionAllFilters.vue";
import CollectionAllToolbar from "../components/CollectionAllToolbar.vue";
import CollectionMobileFilterSheet from "../components/CollectionMobileFilterSheet.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import SetPicker from "../components/SetPicker.vue";
import FilterSidebar from "../components/FilterSidebar.vue";
import ManagerSetTable from "../components/ManagerSetTable.vue";
import ManagerCardStorageModal from "../components/ManagerCardStorageModal.vue";
import ArtStyleRulesPanel from "../components/ArtStyleRulesPanel.vue";
import { useCollectionBulkSelect } from "../composables/useCollectionBulkSelect";
import { useManagerSetTable } from "../composables/useManagerSetTable";
import { fetchCardCopyState } from "../composables/cardContextMenu";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { applyStrategyToCards } from "../utils/priceStrategies";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { defaultAllCardsSortDir, getStoredAllCardsSort, storeAllCardsSort, storeFoilFilter } from "../utils/filterStorage";
import ArtStylePicker from "../components/ArtStylePicker.vue";
import { hasSelectableArtStyles } from "../utils/format";
import { cardDisplayName, cardFinish, cardRouteQuery } from "../utils/finishes";
import { filterCollectionCards, parseOptionalNumber } from "../utils/collectionFilters";
import { sortCollectionCards } from "../utils/collectionSort";
import { detectActiveLens, lensDefinition } from "../utils/collectionLenses";
import { computeCollectionScopeStats } from "../utils/collectionScopeStats";
import {
  allCardsFiltersFromRoute,
  allCardsRouteQuery,
  collectionScopeFromRoute,
  collectionScopeToQuery,
  collectionViewModeFromRoute,
  shouldOpenManagerArtStyleEditor,
} from "../utils/setScope";
import {
  applySetCountPatchesToSets,
  mergeOwnershipPatchesIntoCards,
  ownershipRevision,
  reconcileOwnershipPatches,
  reconcileSetCountPatches,
  setCountPatches,
} from "../composables/cardContextMenu";

const route = useRoute();
const router = useRouter();

const meta = ref(null);
const appMeta = ref(null);
const cardsPayload = ref(null);
const allViewScopeCards = ref([]);
const allViewScopeKey = ref("");
const viewType = ref("all");
const setCode = ref("All");
const familyScope = ref(false);
const artStyle = ref("");
const ownedFilter = ref("owned");
const foilFilter = ref("all");
const typeFilter = ref("all");
const colorFilters = ref([]);
const storageFilters = ref([]);
const searchQuery = ref("");
const rarityFilter = ref("all");
const cmcMin = ref("");
const cmcMax = ref("");
const priceMin = ref("");
const priceMax = ref("");
const powerMin = ref("");
const toughnessMin = ref("");
const activeLens = ref("");
const mobileFiltersOpen = ref(false);
const virtualGridRef = ref(null);
const allCardsPage = ref(1);
const allCardsSort = ref("value");
const allCardsSortDir = ref("desc");
const { pageSize, collectionCardScale, settings: pricingSettings } = usePricingSettings();
const syncStatus = ref(null);
const syncMessage = ref("");
const syncRunning = ref(false);
let pollTimer = null;
const { loading: loadingCards, run: runCardsLoad } = useAsyncLoad();
const routeSyncReady = ref(false);
const applyingRouteQuery = ref(false);
const routeQuerySyncInFlight = ref(false);
const collectionHydrated = ref(false);
const collectionViewMode = ref("gallery");
const artStyleRulesOpen = ref(false);
const priceIssuesOnly = ref(false);
let suppressPageRouteRead = false;
let searchDebounceTimer = null;
let tableSearchDebounceTimer = null;

const {
  bulkSelectMode,
  selectedKeys,
  bulkBusy,
  focusedIndex,
  toggleBulkMode,
  toggleCardSelection,
  clearSelection,
  selectedCardsFrom,
} = useCollectionBulkSelect();

const sets = computed(() => meta.value?.sets || []);
const patchedSets = computed(() => {
  ownershipRevision.value;
  setCountPatches.value;
  return applySetCountPatchesToSets(sets.value);
});
const selectableSets = computed(() => {
  if (!isAllView.value) {
    return patchedSets.value;
  }
  return patchedSets.value.filter((set) => !isAllSetsCode(set.setCode));
});
const artStyles = computed(() => cardsPayload.value?.artStyles || []);
const tableModeAvailable = computed(
  () => isAllView.value && !isAllSetsView.value && !familyScope.value,
);
const isTableView = computed(() =>
  tableModeAvailable.value && collectionViewMode.value === "table",
);

const managerTable = useManagerSetTable(() => ({
  setCode: isTableView.value ? setCode.value : "",
  artStyle: artStyle.value,
  search: searchQuery.value.trim(),
  foilFilter: foilFilter.value,
  priceIssuesOnly: priceIssuesOnly.value,
  pageSize: pageSize.value,
  sort: allCardsSort.value,
  sortDir: allCardsSortDir.value,
  priceStrategy: pricingSettings.value?.priceStrategy || "trend",
}));

const storageModalOpen = ref(false);
const storageModalCard = ref(null);
const storageModalFinish = ref(0);

const displayArtStyles = computed(() => {
  if (isTableView.value && managerTable.artStyles.value.length) {
    return managerTable.artStyles.value;
  }
  return artStyles.value;
});
const showArtStylePicker = computed(() => hasSelectableArtStyles(displayArtStyles.value));
function allCardsFilterParams() {
  return {
    setCode: familyScope.value ? "All" : setCode.value,
    artStyle: isAllSetsView.value || familyScope.value ? "" : artStyle.value,
    ownedFilter: ownedFilter.value,
    foilFilter: foilFilter.value,
    typeFilter: typeFilter.value,
    colorFilters: colorFilters.value,
    storageFilters: storageFilters.value,
    searchQuery: searchQuery.value,
    rarityFilter: rarityFilter.value,
    cmcMin: parseOptionalNumber(cmcMin.value),
    cmcMax: parseOptionalNumber(cmcMax.value),
    priceMin: parseOptionalNumber(priceMin.value),
    priceMax: parseOptionalNumber(priceMax.value),
    powerMin: parseOptionalNumber(powerMin.value),
    toughnessMin: parseOptionalNumber(toughnessMin.value),
  };
}
const cards = computed(() => {
  if (isAllView.value) {
    ownershipRevision.value;
    pricingSettings.value?.priceStrategy;
    const priced = applyStrategyToCards(
      allViewScopeCards.value,
      pricingSettings.value?.priceStrategy || "trend",
    );
    return filterCollectionCards(priced, allCardsFilterParams());
  }
  return cardsPayload.value?.cards || [];
});
const scopeStats = computed(() => {
  if (!isAllView.value) {
    return null;
  }
  ownershipRevision.value;
  const scoped = filterCollectionCards(allViewScopeCards.value, {
    setCode: setCode.value,
    artStyle: isAllSetsView.value ? "" : artStyle.value,
    ownedFilter: "all",
    foilFilter: "all",
    typeFilter: "all",
    colorFilters: [],
    searchQuery: "",
  });
  return computeCollectionScopeStats(scoped);
});
const resolvedActiveLens = computed(() => detectActiveLens({
  lensId: activeLens.value,
  ownedFilter: ownedFilter.value,
  foilFilter: foilFilter.value,
  sort: allCardsSort.value,
  sortDir: allCardsSortDir.value,
  typeFilter: typeFilter.value,
  colorFilters: colorFilters.value,
  searchQuery: searchQuery.value,
  rarityFilter: rarityFilter.value,
  cmcMin: parseOptionalNumber(cmcMin.value),
  cmcMax: parseOptionalNumber(cmcMax.value),
  priceMin: parseOptionalNumber(priceMin.value),
  priceMax: parseOptionalNumber(priceMax.value),
  powerMin: parseOptionalNumber(powerMin.value),
  toughnessMin: parseOptionalNumber(toughnessMin.value),
}));
const hasAllCardsQuickFilters = computed(() => Boolean(
  searchQuery.value.trim()
  || resolvedActiveLens.value
  || typeFilter.value !== "all"
  || colorFilters.value.length
  || storageFilters.value.length
  || rarityFilter.value !== "all"
  || cmcMin.value.trim()
  || cmcMax.value.trim()
  || priceMin.value.trim()
  || priceMax.value.trim()
  || powerMin.value.trim()
  || toughnessMin.value.trim()
  || ownedFilter.value !== "owned"
  || foilFilter.value !== "all",
));
const strategyCards = computed(() => {
  if (isAllView.value) {
    return cards.value;
  }
  pricingSettings.value?.priceStrategy;
  return applyStrategyToCards(cards.value, pricingSettings.value?.priceStrategy || "trend");
});
const isAllView = computed(() => viewType.value === "all");
const isAllSetsView = computed(() => isAllSetsCode(setCode.value));
const showSetCatalogReload = computed(() => viewType.value !== "all" && viewType.value !== "top");

function isAllSetsCode(code) {
  return !code || String(code).toLowerCase() === "all";
}

function currentAllViewScopeKey() {
  const art = isAllSetsView.value || familyScope.value ? "" : artStyle.value;
  return `${setCode.value}|${familyScope.value ? "family" : "single"}|${art}`;
}

function invalidateAllViewScope() {
  allViewScopeKey.value = "";
}

function defaultSetCode() {
  const favorite = sets.value.find((set) => !isAllSetsCode(set.setCode));
  if (meta.value?.defaultSet && !isAllSetsCode(meta.value.defaultSet)) {
    return meta.value.defaultSet;
  }
  return favorite?.setCode || "LTR";
}

function applyScopeFromRoute() {
  const fromRoute = collectionScopeFromRoute(route);
  if (isAllView.value) {
    if (!isAllSetsCode(fromRoute.setCode)) {
      setCode.value = fromRoute.setCode;
    } else if (isAllSetsCode(setCode.value)) {
      setCode.value = defaultSetCode();
    }
  } else if (!isAllSetsCode(fromRoute.setCode)) {
    setCode.value = fromRoute.setCode;
  } else {
    setCode.value = "All";
  }
  familyScope.value = Boolean(fromRoute.family) && !isAllSetsCode(setCode.value);
  artStyle.value = isAllSetsCode(setCode.value) || familyScope.value
    ? ""
    : fromRoute.artStyle;
}

function applyServerFiltersFromRoute() {
  if (!isAllView.value) {
    return;
  }
  const filters = allCardsFiltersFromRoute(route);
  ownedFilter.value = filters.ownedFilter;
  foilFilter.value = filters.foilFilter;
  typeFilter.value = filters.typeFilter;
  colorFilters.value = [...filters.colorFilters];
  storageFilters.value = [...filters.storageFilters];
  searchQuery.value = filters.searchQuery;
  rarityFilter.value = filters.rarityFilter;
  cmcMin.value = filters.cmcMin != null ? String(filters.cmcMin) : "";
  cmcMax.value = filters.cmcMax != null ? String(filters.cmcMax) : "";
  priceMin.value = filters.priceMin != null ? String(filters.priceMin) : "";
  priceMax.value = filters.priceMax != null ? String(filters.priceMax) : "";
  powerMin.value = filters.powerMin != null ? String(filters.powerMin) : "";
  toughnessMin.value = filters.toughnessMin != null ? String(filters.toughnessMin) : "";
  activeLens.value = filters.lens;
}

function applyClientQueryFromRoute() {
  if (!isAllView.value) {
    return;
  }
  const filters = allCardsFiltersFromRoute(route);
  applyingRouteQuery.value = true;
  try {
    allCardsSort.value = filters.sort;
    allCardsSortDir.value = filters.sortDir;
    collectionViewMode.value = filters.viewMode;
    if ("page" in route.query) {
      allCardsPage.value = filters.page;
    }
    if (filters.openArtStyleEditor) {
      artStyleRulesOpen.value = true;
    }
  } finally {
    applyingRouteQuery.value = false;
  }
}

function hydrateCollectionFromRoute() {
  applyingRouteQuery.value = true;
  try {
    applyScopeFromRoute();
    if (isAllView.value) {
      applyAllCardsFiltersFromRoute();
      applyStoredAllCardsSortIfNeeded();
    }
  } finally {
    applyingRouteQuery.value = false;
  }
}

function applyAllCardsFiltersFromRoute() {
  applyServerFiltersFromRoute();
  applyClientQueryFromRoute();
}

function applyStoredAllCardsSortIfNeeded() {
  if (!isAllView.value || route.query?.sort) {
    return;
  }
  const stored = getStoredAllCardsSort();
  allCardsSort.value = stored.sort;
  allCardsSortDir.value = stored.dir;
}

function routeQueriesMatch(nextQuery) {
  const current = route.query;
  const keys = new Set([...Object.keys(current), ...Object.keys(nextQuery)]);
  for (const key of keys) {
    const left = current[key];
    const right = nextQuery[key];
    if (left == null && right == null) {
      continue;
    }
    if (String(left ?? "") !== String(right ?? "")) {
      return false;
    }
  }
  return true;
}

const sortedAllCards = computed(() => {
  if (!isAllView.value) {
    return [];
  }
  return sortCollectionCards(strategyCards.value, {
    sort: allCardsSort.value,
    dir: allCardsSortDir.value,
  });
});

const allCardsTotalPages = computed(() => {
  if (!isAllView.value) {
    return 1;
  }
  return Math.max(1, Math.ceil(sortedAllCards.value.length / pageSize.value));
});

const paginatedAllCards = computed(() => {
  if (!isAllView.value) {
    return [];
  }
  const start = (allCardsPage.value - 1) * pageSize.value;
  return sortedAllCards.value.slice(start, start + pageSize.value);
});

const allCardsRangeStart = computed(() => {
  if (!sortedAllCards.value.length) {
    return 0;
  }
  return (allCardsPage.value - 1) * pageSize.value + 1;
});

const allCardsRangeEnd = computed(() => {
  if (!sortedAllCards.value.length) {
    return 0;
  }
  return Math.min(allCardsPage.value * pageSize.value, sortedAllCards.value.length);
});

const displayCards = computed(() => {
  if (isAllView.value) {
    return paginatedAllCards.value;
  }
  return strategyCards.value;
});
const lastPriceUpdate = computed(
  () => syncStatus.value?.lastPriceUpdate || appMeta.value?.lastPriceUpdate || null,
);
const showSyncTile = computed(() => {
  if (syncRunning.value) {
    return true;
  }
  if (syncStatus.value?.status === "failed") {
    return true;
  }
  return false;
});
const showSyncHint = computed(() => {
  if (showSyncTile.value) {
    return false;
  }
  if (syncStatus.value?.pricesOutdated != null) {
    return syncStatus.value.pricesOutdated;
  }
  if (appMeta.value?.pricesOutdated != null) {
    return appMeta.value.pricesOutdated;
  }
  return !lastPriceUpdate.value || lastPriceUpdate.value === "Unknown";
});

async function loadMeta() {
  const next = await ignoreAborted(api.getReportsMeta());
  if (!next) {
    return;
  }
  meta.value = next;
  reconcileSetCountPatches();
}

async function onSetsChanged(event) {
  if (event?.sets) {
    if (meta.value) {
      meta.value = { ...meta.value, sets: event.sets };
    } else {
      meta.value = { sets: event.sets };
    }
    reconcileSetCountPatches();
  } else {
    clearClientCache();
    await loadMeta();
  }
  if (event?.catalogReloaded) {
    clearClientCache();
    invalidateAllViewScope();
    if (isAllView.value || event.setCode === setCode.value) {
      await loadCards();
      if (isTableView.value) {
        await managerTable.loadCards();
      }
    }
    return;
  }
  if (isAllView.value) {
    await loadCards();
    if (isTableView.value) {
      await managerTable.loadCards();
    }
  }
}

async function reloadManagerTable() {
  if (!isTableView.value) {
    managerTable.resetTableState();
    return;
  }
  await managerTable.loadCards();
}

function setCollectionViewMode(mode) {
  if (mode === "table" && !tableModeAvailable.value) {
    return;
  }
  if (collectionViewMode.value === mode) {
    return;
  }
  collectionViewMode.value = mode;
  if (bulkSelectMode.value) {
    toggleBulkMode();
  }
  pushCollectionRoute();
  if (mode === "table") {
    reloadManagerTable();
  }
}

function openArtStyleEditor() {
  artStyleRulesOpen.value = true;
  pushCollectionRoute();
}

function setPriceIssuesOnly(value) {
  if (priceIssuesOnly.value === value) {
    return;
  }
  priceIssuesOnly.value = value;
  if (isTableView.value) {
    reloadManagerTable();
  }
}

async function onArtStyleRulesSaved(result) {
  clearClientCache();
  if (result?.artStyles) {
    managerTable.updateArtStyles(result.artStyles);
    if (cardsPayload.value) {
      cardsPayload.value = {
        ...cardsPayload.value,
        artStyles: result.artStyles,
      };
    }
  }
  artStyle.value = "";
  invalidateAllViewScope();
  await loadCards();
  if (isTableView.value) {
    await managerTable.loadCards();
  }
}

async function onTableSetCopyCount(card, finish, value) {
  try {
    await managerTable.setCopyCount(setCode.value, card, finish, value);
    mergeOwnershipPatchesIntoCards(allViewScopeCards.value);
    reconcileOwnershipPatches(allViewScopeCards.value);
  } catch (error) {
    window.alert(error.message || "Failed to update copy count.");
  }
}

async function onTableUpdateSingleStorage(card, finish, locationSlug) {
  try {
    await managerTable.updateSingleStorage(setCode.value, card, finish, locationSlug);
    mergeOwnershipPatchesIntoCards(allViewScopeCards.value);
    reconcileOwnershipPatches(allViewScopeCards.value);
  } catch (error) {
    window.alert(error.message || "Failed to update storage.");
  }
}

function onTableOpenStorageModal(card, finish) {
  storageModalCard.value = card;
  storageModalFinish.value = finish;
  storageModalOpen.value = true;
}

async function onTableStorageModalSaved() {
  if (!storageModalCard.value) {
    return;
  }
  try {
    const finishCard = {
      ...storageModalCard.value,
      finish: storageModalFinish.value,
      foil: storageModalFinish.value,
    };
    const payload = await fetchCardCopyState(finishCard);
    if (payload?.state) {
      await managerTable.applyStorageModalState(
        storageModalCard.value,
        storageModalFinish.value,
        payload.state,
      );
    }
    mergeOwnershipPatchesIntoCards(allViewScopeCards.value);
    reconcileOwnershipPatches(allViewScopeCards.value);
  } catch (error) {
    window.alert(error.message || "Failed to refresh storage.");
  }
}

function onTableStorageModalClose() {
  storageModalOpen.value = false;
  storageModalCard.value = null;
}

async function onTableAssignStorage(locationSlug) {
  await managerTable.assignSelectedToStorage(locationSlug);
}

async function onTableSelectAll(checked) {
  if (checked) {
    await managerTable.selectAllRows();
    return;
  }
  managerTable.clearRowSelection();
}

async function loadAppMeta() {
  const next = await ignoreAborted(api.getAppMeta());
  if (!next) {
    return;
  }
  appMeta.value = next;
}

async function loadCards() {
  if (isAllView.value) {
    const scopeKey = currentAllViewScopeKey();
    if (allViewScopeKey.value === scopeKey) {
      return;
    }
    await runCardsLoad(async () => {
      const payload = await api.getReportCards({
        report: "all",
        setCode: setCode.value,
        family: familyScope.value,
        artStyle: isAllSetsView.value || familyScope.value ? "" : artStyle.value,
        ownedFilter: "all",
        foilFilter: "all",
        typeFilter: "all",
        colorFilters: [],
        pageSize: pageSize.value,
      });
      cardsPayload.value = payload;
      allViewScopeCards.value = payload.cards || [];
      allViewScopeKey.value = scopeKey;
      mergeOwnershipPatchesIntoCards(allViewScopeCards.value);
      reconcileOwnershipPatches(allViewScopeCards.value);
    });
  }
}

async function refreshSyncStatus() {
  const status = await ignoreAborted(api.getPriceSyncStatus());
  if (!status) {
    return;
  }
  syncStatus.value = status;
  syncRunning.value = syncStatus.value.status === "running";
  if (syncStatus.value.lastPriceUpdate) {
    appMeta.value = {
      ...(appMeta.value || {}),
      lastPriceUpdate: syncStatus.value.lastPriceUpdate,
    };
  }
  if (syncStatus.value.status === "completed") {
    syncMessage.value = syncStatus.value.message || "Price sync completed.";
  } else if (syncStatus.value.status === "failed") {
    syncMessage.value = syncStatus.value.error || syncStatus.value.message || "Price sync failed.";
  } else if (syncStatus.value.status === "running") {
    syncMessage.value = "Updating Cardmarket prices…";
  } else {
    syncMessage.value = "";
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    await refreshSyncStatus();
    if (syncStatus.value?.status !== "running") {
      stopPolling();
      if (syncStatus.value?.status === "completed") {
        clearClientCache();
        invalidateAllViewScope();
        await loadMeta();
        await loadCards();
      }
    }
  }, 2000);
}

async function triggerPriceSync() {
  syncMessage.value = "Starting price sync…";
  try {
    await api.triggerPriceSync();
    syncRunning.value = true;
    await refreshSyncStatus();
    startPolling();
  } catch (error) {
    syncMessage.value = error.message || "Could not start price sync.";
    syncRunning.value = false;
  }
}

function allCardsArtStyleLink(card) {
  if (!card.artStyle) {
    return null;
  }
  return {
    path: "/collection/all",
    query: allCardsRouteQuery({
      setCode: card.setCode,
      artStyle: card.artStyle,
      ownedFilter: ownedFilter.value,
      foilFilter: foilFilter.value,
      typeFilter: typeFilter.value,
      colorFilters: colorFilters.value,
      storageFilters: storageFilters.value,
      sort: allCardsSort.value,
      sortDir: allCardsSortDir.value,
      page: 1,
      searchQuery: searchQuery.value,
      rarityFilter: rarityFilter.value,
      cmcMin: parseOptionalNumber(cmcMin.value),
      cmcMax: parseOptionalNumber(cmcMax.value),
      priceMin: parseOptionalNumber(priceMin.value),
      priceMax: parseOptionalNumber(priceMax.value),
      powerMin: parseOptionalNumber(powerMin.value),
      toughnessMin: parseOptionalNumber(toughnessMin.value),
      lens: resolvedActiveLens.value,
    }),
  };
}

function syncViewFromRoute() {
  viewType.value = "all";
  applyAllCardsFiltersFromRoute();
  applyStoredAllCardsSortIfNeeded();
}

function buildCollectionQuery() {
  return allCardsRouteQuery({
    setCode: setCode.value,
    artStyle: familyScope.value ? "" : artStyle.value,
    family: familyScope.value,
    ownedFilter: ownedFilter.value,
    foilFilter: foilFilter.value,
    typeFilter: typeFilter.value,
    colorFilters: colorFilters.value,
    storageFilters: storageFilters.value,
    sort: allCardsSort.value,
    sortDir: allCardsSortDir.value,
    page: allCardsPage.value,
    searchQuery: searchQuery.value,
    rarityFilter: rarityFilter.value,
    cmcMin: parseOptionalNumber(cmcMin.value),
    cmcMax: parseOptionalNumber(cmcMax.value),
    priceMin: parseOptionalNumber(priceMin.value),
    priceMax: parseOptionalNumber(priceMax.value),
    powerMin: parseOptionalNumber(powerMin.value),
    toughnessMin: parseOptionalNumber(toughnessMin.value),
    lens: resolvedActiveLens.value,
    viewMode: collectionViewMode.value,
    editArtStyles: artStyleRulesOpen.value,
  });
}

function replaceRouteQuery(query) {
  if (routeQueriesMatch(query)) {
    return Promise.resolve();
  }
  routeQuerySyncInFlight.value = true;
  return router.replace({
    path: route.path,
    query,
  }).finally(() => {
    routeQuerySyncInFlight.value = false;
  });
}

function pushCollectionRoute() {
  if (!isAllView.value) {
    return replaceRouteQuery(
      collectionScopeToQuery(setCode.value, artStyle.value, familyScope.value),
    );
  }
  return replaceRouteQuery(buildCollectionQuery());
}

function replacePageInRoute(page) {
  const query = { ...route.query };
  if (page <= 1) {
    delete query.page;
  } else {
    query.page = String(page);
  }
  suppressPageRouteRead = true;
  return replaceRouteQuery(query).finally(() => {
    queueMicrotask(() => {
      suppressPageRouteRead = false;
    });
  });
}

function goToAllCardsPage(page) {
  const nextPage = Math.max(1, Math.min(page, allCardsTotalPages.value));
  if (allCardsPage.value === nextPage) {
    return;
  }
  allCardsPage.value = nextPage;
  replacePageInRoute(nextPage);
}

function resetAllCardsPage() {
  allCardsPage.value = 1;
}

async function setCollectionCardScale(scale) {
  await savePricingSettings({ collectionCardScale: Number(scale) });
}

function updateAllCardsSort(event) {
  allCardsSort.value = event.target.value;
  allCardsSortDir.value = defaultAllCardsSortDir(allCardsSort.value);
  storeAllCardsSort(allCardsSort.value, allCardsSortDir.value);
  resetAllCardsPage();
  pushCollectionRoute();
}

function toggleAllCardsSortDir() {
  allCardsSortDir.value = allCardsSortDir.value === "asc" ? "desc" : "asc";
  storeAllCardsSort(allCardsSort.value, allCardsSortDir.value);
  resetAllCardsPage();
  pushCollectionRoute();
}

function onTableSort(field) {
  if (allCardsSort.value === field) {
    allCardsSortDir.value = allCardsSortDir.value === "asc" ? "desc" : "asc";
  } else {
    allCardsSort.value = field;
    allCardsSortDir.value = defaultAllCardsSortDir(field);
  }
  storeAllCardsSort(allCardsSort.value, allCardsSortDir.value);
  pushCollectionRoute();
}

function setOwnedFilter(value) {
  if (ownedFilter.value === value) {
    return;
  }
  ownedFilter.value = value;
}

function setFoilFilter(value) {
  if (foilFilter.value === value) {
    return;
  }
  foilFilter.value = value;
  storeFoilFilter(value);
  if (isTableView.value) {
    reloadManagerTable();
  }
}

function setTypeFilter(value) {
  const next = value || "all";
  if (typeFilter.value === next) {
    return;
  }
  typeFilter.value = next;
}

function onTypeFilterChange(event) {
  setTypeFilter(event.target.value);
}

function toggleColorFilter(color) {
  if (colorFilters.value.includes(color)) {
    colorFilters.value = colorFilters.value.filter((item) => item !== color);
    return;
  }
  colorFilters.value = [...colorFilters.value, color];
}

function clearColorFilters() {
  colorFilters.value = [];
}

function toggleStorageFilter(slug) {
  if (storageFilters.value.includes(slug)) {
    storageFilters.value = storageFilters.value.filter((item) => item !== slug);
    return;
  }
  storageFilters.value = [...storageFilters.value, slug];
}

function clearStorageFilters() {
  storageFilters.value = [];
}

function setRarityFilter(value) {
  const next = value || "all";
  if (rarityFilter.value === next) {
    return;
  }
  rarityFilter.value = next;
  activeLens.value = "";
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
  activeLens.value = "";
}

function onRarityFilterChange(event) {
  setRarityFilter(event.target.value);
}

function updateSearchQuery(value) {
  searchQuery.value = value;
  activeLens.value = "";
  resetAllCardsPage();
  focusedIndex.value = -1;
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
  }
  searchDebounceTimer = setTimeout(() => {
    if (routeSyncReady.value && !applyingRouteQuery.value && isAllView.value && !isTableView.value) {
      pushCollectionRoute();
    }
  }, 250);
  if (tableSearchDebounceTimer) {
    clearTimeout(tableSearchDebounceTimer);
  }
  tableSearchDebounceTimer = setTimeout(() => {
    if (routeSyncReady.value && isTableView.value) {
      reloadManagerTable();
    }
  }, 300);
}

function clearAllCardsQuickFilters() {
  ownedFilter.value = "owned";
  foilFilter.value = "all";
  storeFoilFilter("all");
  typeFilter.value = "all";
  colorFilters.value = [];
  storageFilters.value = [];
  searchQuery.value = "";
  rarityFilter.value = "all";
  cmcMin.value = "";
  cmcMax.value = "";
  priceMin.value = "";
  priceMax.value = "";
  powerMin.value = "";
  toughnessMin.value = "";
  activeLens.value = "";
  allCardsSort.value = "value";
  allCardsSortDir.value = "desc";
  storeAllCardsSort("value", "desc");
  resetAllCardsPage();
  focusedIndex.value = -1;
  pushCollectionRoute();
}

function applyCollectionLens(lensId) {
  if (resolvedActiveLens.value === lensId) {
    clearAllCardsQuickFilters();
    return;
  }
  const lens = lensDefinition(lensId);
  if (!lens) {
    return;
  }
  ownedFilter.value = lens.ownedFilter;
  foilFilter.value = lens.foilFilter || "all";
  storeFoilFilter(foilFilter.value);
  if (lens.sort) {
    allCardsSort.value = lens.sort;
    allCardsSortDir.value = lens.sortDir || defaultAllCardsSortDir(lens.sort);
    storeAllCardsSort(allCardsSort.value, allCardsSortDir.value);
  }
  activeLens.value = lensId;
  typeFilter.value = "all";
  colorFilters.value = [];
  searchQuery.value = "";
  resetAllCardsPage();
  focusedIndex.value = -1;
  pushCollectionRoute();
}

function setFocusIndex(index) {
  focusedIndex.value = index;
}

function onCollectionGridKeydown(event) {
  if (!isAllView.value || !sortedAllCards.value.length) {
    return;
  }
  const total = sortedAllCards.value.length;
  let next = focusedIndex.value < 0 ? 0 : focusedIndex.value;

  if (event.key === "ArrowRight") {
    next = Math.min(total - 1, next + 1);
    event.preventDefault();
  } else if (event.key === "ArrowLeft") {
    next = Math.max(0, next - 1);
    event.preventDefault();
  } else if (event.key === "ArrowDown") {
    next = Math.min(total - 1, next + 4);
    event.preventDefault();
  } else if (event.key === "ArrowUp") {
    next = Math.max(0, next - 4);
    event.preventDefault();
  } else if (event.key === " " && bulkSelectMode.value) {
    event.preventDefault();
    toggleCardSelection(sortedAllCards.value[next]);
    return;
  } else if (event.key === "Enter" && next >= 0) {
    const card = sortedAllCards.value[next];
    if (card) {
      router.push({
        name: "card",
        params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
        query: cardRouteQuery(cardFinish(card)),
      });
    }
    return;
  } else {
    return;
  }

  focusedIndex.value = next;
  virtualGridRef.value?.scrollToIndex(next);
}

async function onGalleryOwnershipChanged() {
  mergeOwnershipPatchesIntoCards(allViewScopeCards.value);
  mergeOwnershipPatchesIntoCards(cardsPayload.value?.cards);
  reconcileOwnershipPatches(allViewScopeCards.value);
  reconcileOwnershipPatches(cardsPayload.value?.cards);
}

async function bulkMarkSelectedOwned() {
  const selected = selectedCardsFrom(sortedAllCards.value);
  if (!selected.length || bulkBusy.value) {
    return;
  }
  bulkBusy.value = true;
  try {
    await api.bulkUpdateOwnership({
      setCode: setCode.value,
      items: selected.map((card) => ({
        collectorNumber: card.collectorNumber,
        finish: card.finish ?? card.foil ?? 0,
        owned: true,
      })),
    });
    clearClientCache();
    invalidateAllViewScope();
    clearSelection();
    await loadCards();
  } catch (error) {
    window.alert(error.message || "Could not update ownership.");
  } finally {
    bulkBusy.value = false;
  }
}

function syncCollectionRoute() {
  return pushCollectionRoute();
}

function onCollectionScopeChange() {
  if (
    !routeSyncReady.value
    || applyingRouteQuery.value
    || !collectionHydrated.value
    || suppressPageRouteRead
  ) {
    return;
  }
  if (isAllSetsView.value && artStyle.value) {
    artStyle.value = "";
    return;
  }
  invalidateAllViewScope();
  resetAllCardsPage();
  if (!isAllView.value) {
    pushCollectionRoute();
    loadCards();
    return;
  }
  pushCollectionRoute();
  loadCards();
}

watch(setCode, (newSet, oldSet) => {
  if (
    !routeSyncReady.value
    || applyingRouteQuery.value
    || !collectionHydrated.value
    || suppressPageRouteRead
    || newSet === oldSet
  ) {
    return;
  }
  if (artStyle.value) {
    artStyle.value = "";
    return;
  }
  onCollectionScopeChange();
});

watch(familyScope, (newFamily, oldFamily) => {
  if (
    !routeSyncReady.value
    || applyingRouteQuery.value
    || !collectionHydrated.value
    || suppressPageRouteRead
    || newFamily === oldFamily
  ) {
    return;
  }
  if (newFamily && artStyle.value) {
    artStyle.value = "";
  }
  onCollectionScopeChange();
});

watch(artStyle, () => {
  onCollectionScopeChange();
});

watch(displayArtStyles, (styles) => {
  if (!hasSelectableArtStyles(styles) && artStyle.value) {
    artStyle.value = "";
  }
});

watch([ownedFilter, foilFilter, typeFilter, colorFilters, storageFilters, rarityFilter, cmcMin, cmcMax, priceMin, priceMax, powerMin, toughnessMin], () => {
  if (
    !routeSyncReady.value
    || applyingRouteQuery.value
    || !collectionHydrated.value
    || suppressPageRouteRead
    || !isAllView.value
  ) {
    return;
  }
  activeLens.value = resolvedActiveLens.value;
  resetAllCardsPage();
  focusedIndex.value = -1;
  pushCollectionRoute();
});

watch(pageSize, () => {
  if (
    !routeSyncReady.value
    || applyingRouteQuery.value
    || !collectionHydrated.value
    || suppressPageRouteRead
  ) {
    return;
  }
  resetAllCardsPage();
  if (isAllView.value) {
    return;
  }
  pushCollectionRoute();
  loadCards();
});

watch(allCardsTotalPages, (totalPages) => {
  if (applyingRouteQuery.value || loadingCards.value || routeQuerySyncInFlight.value || !cards.value.length) {
    return;
  }
  if (allCardsPage.value > totalPages) {
    allCardsPage.value = totalPages;
    replacePageInRoute(allCardsPage.value);
  }
});

watch(
  () => [
    route.query.set,
    route.query.family,
    route.query.art,
    route.query.owned,
    route.query.finish,
    route.query.type,
    route.query.colors,
    route.query.q,
    route.query.lens,
  ],
  () => {
    if (!routeSyncReady.value || suppressPageRouteRead) {
      return;
    }
    const prevSet = setCode.value;
    const prevFamily = familyScope.value;
    const prevArt = artStyle.value;
    const prevOwned = ownedFilter.value;
    const prevFinish = foilFilter.value;
    const prevType = typeFilter.value;
    const prevColors = colorFilters.value.join(",");
    const prevSearch = searchQuery.value;
    const prevLens = activeLens.value;
    applyingRouteQuery.value = true;
    try {
      applyScopeFromRoute();
      if (isAllView.value) {
        applyServerFiltersFromRoute();
      }
    } finally {
      applyingRouteQuery.value = false;
    }
    const changed = setCode.value !== prevSet
      || familyScope.value !== prevFamily
      || artStyle.value !== prevArt
      || (isAllView.value && (
        ownedFilter.value !== prevOwned
        || foilFilter.value !== prevFinish
        || typeFilter.value !== prevType
        || colorFilters.value.join(",") !== prevColors
        || searchQuery.value !== prevSearch
        || activeLens.value !== prevLens
      ));
    if (changed) {
      const scopeChanged = setCode.value !== prevSet
        || familyScope.value !== prevFamily
        || artStyle.value !== prevArt;
      if (isAllView.value) {
        resetAllCardsPage();
        pushCollectionRoute();
        if (scopeChanged) {
          invalidateAllViewScope();
          loadCards();
        }
      } else {
        if (scopeChanged) {
          resetAllCardsPage();
          pushCollectionRoute();
        }
        loadCards();
      }
    }
  },
);

watch(
  () => route.query.page,
  (pageParam) => {
    if (
      !routeSyncReady.value
      || !isAllView.value
      || routeQuerySyncInFlight.value
      || suppressPageRouteRead
    ) {
      return;
    }
    applyingRouteQuery.value = true;
    try {
      if (pageParam == null || pageParam === "") {
        if (!("page" in route.query)) {
          allCardsPage.value = 1;
        }
        return;
      }
      const parsed = Number(pageParam);
      allCardsPage.value = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
    } finally {
      applyingRouteQuery.value = false;
    }
  },
);

watch(
  () => route.query.sort,
  () => {
    if (!routeSyncReady.value || !isAllView.value || routeQuerySyncInFlight.value) {
      return;
    }
    applyingRouteQuery.value = true;
    try {
      allCardsSort.value = allCardsFiltersFromRoute(route).sort;
    } finally {
      applyingRouteQuery.value = false;
    }
  },
);

watch(
  () => route.query.dir,
  () => {
    if (!routeSyncReady.value || !isAllView.value || routeQuerySyncInFlight.value) {
      return;
    }
    applyingRouteQuery.value = true;
    try {
      allCardsSortDir.value = allCardsFiltersFromRoute(route).sortDir;
    } finally {
      applyingRouteQuery.value = false;
    }
  },
);

watch(
  () => route.query.view,
  () => {
    if (!routeSyncReady.value || !isAllView.value || routeQuerySyncInFlight.value) {
      return;
    }
    const nextMode = collectionViewModeFromRoute(route);
    if (collectionViewMode.value === nextMode) {
      return;
    }
    collectionViewMode.value = nextMode;
    if (nextMode === "table") {
      reloadManagerTable();
    }
  },
);

watch(
  () => route.query.editArtStyles,
  () => {
    if (!routeSyncReady.value || !isAllView.value) {
      return;
    }
    artStyleRulesOpen.value = shouldOpenManagerArtStyleEditor(route);
  },
);

watch(isAllSetsView, (allSets) => {
  if (!allSets || collectionViewMode.value !== "table") {
    return;
  }
  collectionViewMode.value = "gallery";
  if (routeSyncReady.value && isAllView.value) {
    pushCollectionRoute();
  }
});

watch(artStyleRulesOpen, (open, wasOpen) => {
  if (!routeSyncReady.value || !isAllView.value || applyingRouteQuery.value || open === wasOpen) {
    return;
  }
  pushCollectionRoute();
});

watch([isTableView, artStyle, pageSize], () => {
  if (!collectionHydrated.value || !routeSyncReady.value) {
    return;
  }
  reloadManagerTable();
});

onMounted(async () => {
  syncViewFromRoute();
  await Promise.all([fetchPricingSettings(), loadMeta(), loadAppMeta(), refreshSyncStatus()]);
  hydrateCollectionFromRoute();
  if (shouldOpenManagerArtStyleEditor(route)) {
    artStyleRulesOpen.value = true;
  }
  routeSyncReady.value = true;
  await loadCards();
  if (isTableView.value) {
    await managerTable.loadCards();
  }
  collectionHydrated.value = true;
  if (syncStatus.value?.status === "running") {
    startPolling();
  }
});

onUnmounted(stopPolling);
</script>

<template>
  <div class="reports-page collection-page">
    <div v-if="showSyncTile" class="collection-status">
      <p v-if="lastPriceUpdate" class="collection-status-meta">
        Last price snapshot: <strong>{{ lastPriceUpdate }}</strong>
      </p>
      <p v-else class="collection-status-meta">No price snapshot recorded yet.</p>
      <div class="collection-status-actions">
        <p
          v-if="syncMessage"
          class="collection-sync-message"
          :class="{ error: syncStatus?.status === 'failed' }"
        >
          {{ syncMessage }}
        </p>
        <button
          type="button"
          class="btn btn-secondary btn-small"
          :disabled="syncRunning"
          @click="triggerPriceSync"
        >
          {{ syncRunning ? "Syncing…" : "Sync prices" }}
        </button>
      </div>
    </div>

    <SetPicker
      v-model="setCode"
      v-model:family="familyScope"
      layout="banner"
      :sets="selectableSets"
      :active-art-style="artStyle"
      :show-reload-catalog="showSetCatalogReload"
      @sets-changed="onSetsChanged"
    />

    <div class="page-with-sidebar">
      <FilterSidebar class="collection-desktop-filters">
        <CollectionAllFilters
          v-if="isAllView"
          :is-all-view="isAllView"
          :is-all-sets-view="isAllSetsView || familyScope"
          :is-table-view="isTableView"
          :art-styles="displayArtStyles"
          :set-code="setCode"
          :art-style="artStyle"
          :owned-filter="ownedFilter"
          :foil-filter="foilFilter"
          :type-filter="typeFilter"
          :color-filters="colorFilters"
          :storage-filters="storageFilters"
          :rarity-filter="rarityFilter"
          :cmc-min="cmcMin"
          :cmc-max="cmcMax"
          :price-min="priceMin"
          :price-max="priceMax"
          :power-min="powerMin"
          :toughness-min="toughnessMin"
          :all-cards-sort="allCardsSort"
          :all-cards-sort-dir="allCardsSortDir"
          :price-issues-only="priceIssuesOnly"
          :price-issue-count="managerTable.priceIssueCount.value"
          :show-price-health="tableModeAvailable"
          @update:art-style="artStyle = $event"
          @set-owned-filter="setOwnedFilter"
          @set-foil-filter="setFoilFilter"
          @type-filter-change="onTypeFilterChange"
          @toggle-color-filter="toggleColorFilter"
          @clear-color-filters="clearColorFilters"
          @toggle-storage-filter="toggleStorageFilter"
          @clear-storage-filters="clearStorageFilters"
          @rarity-filter-change="onRarityFilterChange"
          @update:cmc-min="updateDetailFilter('cmcMin', $event)"
          @update:cmc-max="updateDetailFilter('cmcMax', $event)"
          @update:price-min="updateDetailFilter('priceMin', $event)"
          @update:price-max="updateDetailFilter('priceMax', $event)"
          @update:power-min="updateDetailFilter('powerMin', $event)"
          @update:toughness-min="updateDetailFilter('toughnessMin', $event)"
          @update-sort="updateAllCardsSort"
          @toggle-sort-dir="toggleAllCardsSortDir"
          @update:price-issues-only="setPriceIssuesOnly"
          @open-art-style-editor="openArtStyleEditor"
        />
        <template v-else>
          <div class="filter-sidebar-section">
            <p class="filter-sidebar-label">Set</p>
            <SetPicker
              v-model="setCode"
              v-model:family="familyScope"
              layout="dropdown"
              :sets="selectableSets"
            />
          </div>
          <div
            v-if="!isAllSetsView && !familyScope"
            class="filter-sidebar-section"
          >
            <p class="filter-sidebar-label">Art style</p>
            <ArtStylePicker
              v-if="showArtStylePicker"
              v-model="artStyle"
              layout="list"
              :set-code="setCode"
              :art-styles="artStyles"
            />
          </div>
        </template>
      </FilterSidebar>

      <CollectionMobileFilterSheet
        :open="mobileFiltersOpen"
        @close="mobileFiltersOpen = false"
      >
        <CollectionAllFilters
          v-if="isAllView"
          :is-all-view="isAllView"
          :is-all-sets-view="isAllSetsView || familyScope"
          :is-table-view="isTableView"
          :art-styles="displayArtStyles"
          :set-code="setCode"
          :art-style="artStyle"
          :owned-filter="ownedFilter"
          :foil-filter="foilFilter"
          :type-filter="typeFilter"
          :color-filters="colorFilters"
          :storage-filters="storageFilters"
          :rarity-filter="rarityFilter"
          :cmc-min="cmcMin"
          :cmc-max="cmcMax"
          :price-min="priceMin"
          :price-max="priceMax"
          :power-min="powerMin"
          :toughness-min="toughnessMin"
          :all-cards-sort="allCardsSort"
          :all-cards-sort-dir="allCardsSortDir"
          :price-issues-only="priceIssuesOnly"
          :price-issue-count="managerTable.priceIssueCount.value"
          :show-price-health="tableModeAvailable"
          @update:art-style="artStyle = $event"
          @set-owned-filter="setOwnedFilter"
          @set-foil-filter="setFoilFilter"
          @type-filter-change="onTypeFilterChange"
          @toggle-color-filter="toggleColorFilter"
          @clear-color-filters="clearColorFilters"
          @toggle-storage-filter="toggleStorageFilter"
          @clear-storage-filters="clearStorageFilters"
          @rarity-filter-change="onRarityFilterChange"
          @update:cmc-min="updateDetailFilter('cmcMin', $event)"
          @update:cmc-max="updateDetailFilter('cmcMax', $event)"
          @update:price-min="updateDetailFilter('priceMin', $event)"
          @update:price-max="updateDetailFilter('priceMax', $event)"
          @update:power-min="updateDetailFilter('powerMin', $event)"
          @update:toughness-min="updateDetailFilter('toughnessMin', $event)"
          @update-sort="updateAllCardsSort"
          @toggle-sort-dir="toggleAllCardsSortDir"
          @update:price-issues-only="setPriceIssuesOnly"
          @open-art-style-editor="openArtStyleEditor"
        />
      </CollectionMobileFilterSheet>

      <div class="page-with-sidebar-main">
        <div v-if="loadingCards && isAllView && !collectionHydrated" class="storage-empty">
          <LoadingIndicator label="Loading cards…" />
        </div>

        <div v-else-if="isAllView" class="table-panel cards-panel reports-cards-panel collection-gallery-panel">
          <CollectionAllToolbar
            :search-query="searchQuery"
            :active-lens="resolvedActiveLens"
            :filtered-count="sortedAllCards.length"
            :scope-count="scopeStats?.totalCount ?? 0"
            :scope-stats="scopeStats"
            :bulk-select-mode="bulkSelectMode"
            :selected-count="selectedKeys.size"
            :bulk-busy="bulkBusy"
            :card-scale="collectionCardScale"
            :scale-options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150]"
            :mobile-filters-open="mobileFiltersOpen"
            :view-mode="collectionViewMode"
            :table-mode-available="tableModeAvailable"
            @update:search-query="updateSearchQuery"
            @update:view-mode="setCollectionViewMode"
            @select-lens="applyCollectionLens"
            @toggle-bulk-mode="toggleBulkMode"
            @bulk-mark-owned="bulkMarkSelectedOwned"
            @bulk-clear-selection="clearSelection"
            @open-mobile-filters="mobileFiltersOpen = true"
            @update:card-scale="setCollectionCardScale"
          />
          <ArtStyleRulesPanel
            v-if="tableModeAvailable"
            v-model:open="artStyleRulesOpen"
            :set-code="setCode"
            @saved="onArtStyleRulesSaved"
          />
          <p v-if="showSyncHint && !isTableView" class="collection-sync-hint">
            Prices may be outdated.
            <button type="button" class="collection-sync-hint-btn" @click="triggerPriceSync">
              Sync now
            </button>
          </p>
          <ManagerSetTable
            v-if="isTableView"
            :set-code="setCode"
            :finish-rows="managerTable.finishRows.value"
            :loading="managerTable.loadingCards.value"
            :loading-more="managerTable.loadingMore.value"
            :has-more="managerTable.hasMoreCards.value"
            :total-matches="managerTable.totalMatches.value"
            :all-visible-selected="managerTable.allVisibleSelected.value"
            :is-row-selected="managerTable.isRowSelected"
            :sort-field="allCardsSort"
            :sort-dir="allCardsSortDir"
            :price-strategy="pricingSettings?.priceStrategy || 'trend'"
            @update:all-visible-selected="onTableSelectAll"
            @toggle-row="managerTable.toggleRow"
            @set-copy-count="onTableSetCopyCount"
            @update-single-storage="onTableUpdateSingleStorage"
            @open-storage-modal="onTableOpenStorageModal"
            @assign-storage="onTableAssignStorage"
            @load-more="managerTable.loadMoreCards"
            @sort="onTableSort"
          />
          <template v-else>
          <div v-if="!sortedAllCards.length" class="storage-empty collection-gallery-empty">
            <p>No cards match these filters.</p>
            <button
              v-if="hasAllCardsQuickFilters"
              type="button"
              class="btn btn-secondary btn-small"
              @click="clearAllCardsQuickFilters"
            >
              Clear filters
            </button>
          </div>
          <GalleryLoadingOverlay v-else :loading="loadingCards" label="Updating cards…">
            <VirtualizedCollectionCardGrid
              ref="virtualGridRef"
              :cards="sortedAllCards"
              :card-scale="collectionCardScale"
              :selectable="bulkSelectMode"
              :selected-keys="selectedKeys"
              :focused-index="focusedIndex"
              @toggle-select="toggleCardSelection"
              @focus-index="setFocusIndex"
              @keydown="onCollectionGridKeydown"
              @ownership-changed="onGalleryOwnershipChanged"
            />
          </GalleryLoadingOverlay>
          </template>
        </div>
      </div>
    </div>

    <ManagerCardStorageModal
      :open="storageModalOpen"
      :card="storageModalCard"
      :finish="storageModalFinish"
      @saved="onTableStorageModalSaved"
      @close="onTableStorageModalClose"
    />
  </div>
</template>
