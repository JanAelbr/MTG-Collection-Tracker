<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache, ignoreAborted } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import CollectionCardGrid from "../components/CollectionCardGrid.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import ReportTopCardsHero from "../components/ReportTopCardsHero.vue";
import CardPreview from "../components/CardPreview.vue";
import SetPicker from "../components/SetPicker.vue";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { defaultAllCardsSortDir, getStoredAllCardsSort, storeAllCardsSort, storeFoilFilter } from "../utils/filterStorage";
import { formatEuro, formatPriceChange, formatProfit } from "../utils/format";
import ArtStylePicker from "../components/ArtStylePicker.vue";
import ManaSymbols from "../components/ManaSymbols.vue";
import { DECK_COLOR_ORDER } from "../utils/deckCards";
import {
  COLLECTION_TYPE_LABELS,
  COLLECTION_TYPE_ORDER,
} from "../utils/collectionTypes";
import { cardDisplayName, cardFinish, cardRouteQuery } from "../utils/finishes";
import {
  allCardsFiltersFromRoute,
  allCardsRouteQuery,
  collectionScopeFromRoute,
  collectionScopeToQuery,
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
const viewType = ref("all");
const setCode = ref("All");
const artStyle = ref("");
const ownedFilter = ref("owned");
const foilFilter = ref("all");
const typeFilter = ref("all");
const colorFilters = ref([]);
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
let suppressPageRouteRead = false;

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
const cards = computed(() => cardsPayload.value?.cards || []);
const isAllView = computed(() => viewType.value === "all");
const isAllSetsView = computed(() => isAllSetsCode(setCode.value));

function isAllSetsCode(code) {
  return !code || String(code).toLowerCase() === "all";
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
  artStyle.value = isAllSetsCode(setCode.value) ? "" : fromRoute.artStyle;
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
    if ("page" in route.query) {
      allCardsPage.value = filters.page;
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

function collectorSortKey(value) {
  const text = String(value ?? "");
  if (/^\d+$/.test(text)) {
    return [0, Number(text), ""];
  }
  return [1, 0, text];
}

function compareCollectorNumbers(left, right) {
  const leftKey = collectorSortKey(left);
  const rightKey = collectorSortKey(right);
  for (let index = 0; index < 3; index += 1) {
    if (leftKey[index] < rightKey[index]) {
      return -1;
    }
    if (leftKey[index] > rightKey[index]) {
      return 1;
    }
  }
  return 0;
}

function priceChangePercent(card) {
  const change = card.priceChange;
  const previous = card.previousValue;
  if (change == null || previous == null || previous === 0) {
    return null;
  }
  return (change / previous) * 100;
}

function compareNullableNumber(leftValue, rightValue, ascending) {
  if (leftValue == null && rightValue == null) {
    return 0;
  }
  if (leftValue == null) {
    return 1;
  }
  if (rightValue == null) {
    return -1;
  }
  const order = leftValue - rightValue;
  return ascending ? order : -order;
}

function comparePriceChange(left, right, ascending) {
  return compareNullableNumber(left.priceChange, right.priceChange, ascending);
}

function comparePriceChangePercent(left, right, ascending) {
  return compareNullableNumber(priceChangePercent(left), priceChangePercent(right), ascending);
}

function compareAllCardsTieBreak(left, right) {
  const numberOrder = compareCollectorNumbers(left.collectorNumber, right.collectorNumber);
  if (numberOrder !== 0) {
    return numberOrder;
  }
  return (left.finish ?? 0) - (right.finish ?? 0);
}

const sortedAllCards = computed(() => {
  if (!isAllView.value) {
    return [];
  }
  const list = [...cards.value];
  const ascending = allCardsSortDir.value === "asc";

  return list.sort((left, right) => {
    let primary = 0;
    if (allCardsSort.value === "value") {
      const leftValue = left.currentValue ?? Number.NEGATIVE_INFINITY;
      const rightValue = right.currentValue ?? Number.NEGATIVE_INFINITY;
      primary = ascending ? leftValue - rightValue : rightValue - leftValue;
    } else if (allCardsSort.value === "changeEuro") {
      primary = comparePriceChange(left, right, ascending);
    } else if (allCardsSort.value === "changePct") {
      primary = comparePriceChangePercent(left, right, ascending);
    } else {
      primary = compareCollectorNumbers(left.collectorNumber, right.collectorNumber);
      if (primary !== 0) {
        return ascending ? primary : -primary;
      }
      return (left.finish ?? 0) - (right.finish ?? 0);
    }
    if (primary !== 0) {
      return primary;
    }
    return compareAllCardsTieBreak(left, right);
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
  return cards.value;
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
  if (isAllView.value) {
    await loadCards();
  }
}

const statsLink = computed(() => ({
  path: "/stats",
  query: collectionScopeToQuery(setCode.value),
}));

async function loadAppMeta() {
  const next = await ignoreAborted(api.getAppMeta());
  if (!next) {
    return;
  }
  appMeta.value = next;
}

async function loadCards() {
  await runCardsLoad(async () => {
    cardsPayload.value = await api.getReportCards({
      report: viewType.value,
      setCode: setCode.value,
      artStyle: isAllSetsView.value ? "" : artStyle.value,
      ownedFilter: isAllView.value ? ownedFilter.value : "owned",
      foilFilter: isAllView.value ? foilFilter.value : "all",
      typeFilter: isAllView.value ? typeFilter.value : "all",
      colorFilters: isAllView.value ? colorFilters.value : [],
      pageSize: pageSize.value,
    });
    mergeOwnershipPatchesIntoCards(cardsPayload.value?.cards);
    reconcileOwnershipPatches(cardsPayload.value?.cards);
  });
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

function formatGainLoss(profitLoss, purchaseValue) {
  if (purchaseValue == null || purchaseValue === 0) {
    return "—";
  }
  return formatProfit(profitLoss);
}

function cardTitle(card) {
  const number = String(card.collectorNumber).padStart(3, "0");
  return `${number} · ${cardDisplayName(card)}`;
}

function storageLink(location) {
  return {
    path: "/storage",
    query: { location: location.slug },
  };
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
      sort: allCardsSort.value,
      sortDir: allCardsSortDir.value,
      page: 1,
    }),
  };
}

function syncViewFromRoute() {
  const view = route.params.view;
  if (typeof view === "string" && view !== viewType.value) {
    viewType.value = view;
    if (view === "all") {
      applyAllCardsFiltersFromRoute();
      applyStoredAllCardsSortIfNeeded();
    } else {
      ownedFilter.value = "owned";
      typeFilter.value = "all";
      colorFilters.value = [];
    }
  }
}

function buildCollectionQuery() {
  return allCardsRouteQuery({
    setCode: setCode.value,
    artStyle: artStyle.value,
    ownedFilter: ownedFilter.value,
    foilFilter: foilFilter.value,
    typeFilter: typeFilter.value,
    colorFilters: colorFilters.value,
    sort: allCardsSort.value,
    sortDir: allCardsSortDir.value,
    page: allCardsPage.value,
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
    return replaceRouteQuery(collectionScopeToQuery(setCode.value, artStyle.value));
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

function collectionCardScaleLabel(scale) {
  if (scale <= 75) {
    return "Small";
  }
  if (scale >= 150) {
    return "Extra large";
  }
  if (scale >= 125) {
    return "Large";
  }
  return "Normal";
}

async function updateCollectionCardScale(event) {
  await savePricingSettings({ collectionCardScale: Number(event.target.value) });
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

function syncCollectionRoute() {
  return pushCollectionRoute();
}

watch(
  () => route.params.view,
  () => {
    syncViewFromRoute();
    hydrateCollectionFromRoute();
    if (!isAllView.value) {
      resetAllCardsPage();
    }
    if (routeSyncReady.value) {
      syncCollectionRoute();
      loadCards();
    }
  },
);

watch([setCode, artStyle, ownedFilter, foilFilter, typeFilter, colorFilters, pageSize], () => {
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
  if (!isAllView.value) {
    return;
  }
  resetAllCardsPage();
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
    route.query.art,
    route.query.owned,
    route.query.finish,
    route.query.type,
    route.query.colors,
  ],
  () => {
    if (!routeSyncReady.value || suppressPageRouteRead) {
      return;
    }
    const prevSet = setCode.value;
    const prevArt = artStyle.value;
    const prevOwned = ownedFilter.value;
    const prevFinish = foilFilter.value;
    const prevType = typeFilter.value;
    const prevColors = colorFilters.value.join(",");
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
      || artStyle.value !== prevArt
      || (isAllView.value && (
        ownedFilter.value !== prevOwned
        || foilFilter.value !== prevFinish
        || typeFilter.value !== prevType
        || colorFilters.value.join(",") !== prevColors
      ));
    if (changed) {
      if (isAllView.value) {
        resetAllCardsPage();
        pushCollectionRoute();
      }
      loadCards();
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

watch(ownershipRevision, async () => {
  if (!routeSyncReady.value) {
    return;
  }
  await loadMeta();
});

onMounted(async () => {
  syncViewFromRoute();
  await Promise.all([fetchPricingSettings(), loadMeta(), loadAppMeta(), refreshSyncStatus()]);
  hydrateCollectionFromRoute();
  routeSyncReady.value = true;
  await loadCards();
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
      layout="banner"
      :sets="selectableSets"
      @sets-changed="onSetsChanged"
    />

    <div class="reports-toolbar">
      <div class="reports-toolbar-filters">
        <SetPicker
          v-model="setCode"
          layout="dropdown"
          :sets="selectableSets"
        />

        <ArtStylePicker
          v-model="artStyle"
          :art-styles="artStyles"
          :disabled="isAllSetsView"
        />

        <div v-if="isAllView" class="button-group collection-ownership-group">
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
            <button
              type="button"
              class="filter-button"
              :class="{ active: ownedFilter === 'unowned' }"
              @click="setOwnedFilter('unowned')"
            >
            Not owned
          </button>
        </div>

        <div v-if="isAllView" class="button-group collection-finish-group">
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'all' }"
            @click="setFoilFilter('all')"
          >
            All finishes
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'nonfoil' }"
            @click="setFoilFilter('nonfoil')"
          >
            Non-foil
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'foil' }"
            @click="setFoilFilter('foil')"
          >
            Foil
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'etched' }"
            @click="setFoilFilter('etched')"
          >
            Etched
          </button>
        </div>

        <div v-if="isAllView" class="collection-type-color-filters">
          <label class="manager-filter collection-type-filter">
            <span>Type</span>
            <select :value="typeFilter" @change="onTypeFilterChange">
              <option value="all">All types</option>
              <option
                v-for="type in COLLECTION_TYPE_ORDER"
                :key="type"
                :value="type"
              >
                {{ COLLECTION_TYPE_LABELS[type] }}
              </option>
            </select>
          </label>

          <div class="button-group collection-color-group">
            <button
              v-for="color in DECK_COLOR_ORDER"
              :key="color"
              type="button"
              class="filter-button collection-color-filter"
              :class="{ active: colorFilters.includes(color) }"
              :title="color === 'C' ? 'Colorless' : color"
              @click="toggleColorFilter(color)"
            >
              <ManaSymbols :colors="color === 'C' ? [] : [color]" :size="18" />
            </button>
            <button
              v-if="colorFilters.length"
              type="button"
              class="filter-button"
              @click="clearColorFilters"
            >
              Clear
            </button>
          </div>
        </div>

        <label v-if="isAllView" class="manager-filter">
          <span>Image size</span>
          <select :value="collectionCardScale" @change="updateCollectionCardScale">
            <option
              v-for="scale in (pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150])"
              :key="scale"
              :value="scale"
            >
              {{ collectionCardScaleLabel(scale) }} ({{ scale }}%)
            </option>
          </select>
        </label>

        <label v-if="isAllView" class="manager-filter">
          <span>Sort by</span>
          <select :value="allCardsSort" @change="updateAllCardsSort">
            <option value="number">Collector number</option>
            <option value="value">Value</option>
            <option value="changePct">Price change (%)</option>
            <option value="changeEuro">Price change (€)</option>
          </select>
          <button
            type="button"
            class="btn btn-secondary collection-sort-dir"
            :title="allCardsSortDir === 'asc' ? 'Ascending' : 'Descending'"
            :aria-label="`Sort ${allCardsSortDir === 'asc' ? 'ascending' : 'descending'}`"
            @click="toggleAllCardsSortDir"
          >
            {{ allCardsSortDir === "asc" ? "↑" : "↓" }}
          </button>
        </label>

        <RouterLink :to="statsLink" class="btn btn-secondary btn-small">
          View stats
        </RouterLink>
      </div>
    </div>

    <p class="manager-stats">
      <template v-if="isAllView && sortedAllCards.length">
        Showing {{ allCardsRangeStart }}–{{ allCardsRangeEnd }} of {{ sortedAllCards.length }} cards
        <span v-if="allCardsTotalPages > 1"> · page {{ allCardsPage }} / {{ allCardsTotalPages }}</span>
      </template>
      <template v-else>
        Showing {{ displayCards.length }} of {{ cardsPayload?.totalMatches ?? 0 }} matches
      </template>
    </p>

    <div v-if="loadingCards && !cards.length" class="storage-empty">
      <LoadingIndicator label="Loading cards…" />
    </div>

    <div v-else-if="(isAllView ? !sortedAllCards.length : !cards.length)" class="storage-empty">
      No cards match these filters.
    </div>

    <div v-else-if="isAllView" class="table-panel cards-panel reports-cards-panel">
      <GalleryLoadingOverlay :loading="loadingCards" label="Updating cards…">
        <CollectionCardGrid
          :cards="paginatedAllCards"
          :show-unowned-badge="ownedFilter === 'all'"
          :show-finish-badge="true"
          :card-scale="collectionCardScale"
          :price-change-mode="allCardsSort === 'changeEuro' || allCardsSort === 'changePct' ? allCardsSort : ''"
        />
        <div v-if="allCardsTotalPages > 1" class="manager-pagination collection-pagination">
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="allCardsPage <= 1"
            @click="goToAllCardsPage(allCardsPage - 1)"
          >
            Previous
          </button>
          <span>Page {{ allCardsPage }} / {{ allCardsTotalPages }}</span>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="allCardsPage >= allCardsTotalPages"
            @click="goToAllCardsPage(allCardsPage + 1)"
          >
            Next
          </button>
        </div>
      </GalleryLoadingOverlay>
    </div>

    <div v-else class="table-panel cards-panel reports-cards-panel">
      <GalleryLoadingOverlay :loading="loadingCards" label="Updating cards…">
        <ReportTopCardsHero :cards="displayCards" />
        <table class="reports-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Card</th>
            <th>Art style</th>
            <th>Value</th>
            <th>Change</th>
            <th>Gain / loss</th>
            <th>Storage</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(card, index) in displayCards" :key="`${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`">
            <td>{{ index + 1 }}</td>
            <td>
              <CardPreview :image-uri="card.imageUri">
                <RouterLink
                  :to="{
                    name: 'card',
                    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
                    query: cardRouteQuery(cardFinish(card)),
                  }"
                  class="reports-card-link"
                >
                  {{ cardTitle(card) }}
                </RouterLink>
              </CardPreview>
            </td>
            <td>
              <RouterLink
                v-if="allCardsArtStyleLink(card)"
                :to="allCardsArtStyleLink(card)"
                class="reports-card-link"
              >
                {{ card.artStyle }}
              </RouterLink>
              <span v-else>—</span>
            </td>
            <td>{{ formatEuro(card.currentValue) }}</td>
            <td
              :class="{
                'reports-change-up': card.priceChange != null && card.priceChange > 0,
                'reports-change-down': card.priceChange != null && card.priceChange < 0,
              }"
            >
              {{ formatPriceChange(card.priceChange, card.previousValue) }}
            </td>
            <td
              :class="{
                'reports-gain': card.profitLoss != null && card.profitLoss >= 0,
                'reports-loss': card.profitLoss != null && card.profitLoss < 0,
              }"
            >
              {{ formatGainLoss(card.profitLoss, card.purchaseValue) }}
            </td>
            <td class="reports-locations">
              <template v-if="card.locations?.length">
                <RouterLink
                  v-for="location in card.locations"
                  :key="location.slug"
                  :to="storageLink(location)"
                  class="reports-location-link"
                >
                  {{ location.label }}<span v-if="location.count > 1"> ×{{ location.count }}</span>
                </RouterLink>
              </template>
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </table>
      </GalleryLoadingOverlay>
    </div>
  </div>
</template>
