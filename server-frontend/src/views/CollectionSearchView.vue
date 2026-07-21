<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ignoreAborted } from "../api";
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
import FilterSidebar from "../components/FilterSidebar.vue";
import { getStoredFoilFilter, storeFoilFilter } from "../utils/filterStorage";
import { formatSetDropdownLabel } from "../utils/format";
import { parseOptionalNumber } from "../utils/collectionFilters";
import { searchFiltersFromRoute, searchRouteQuery, searchViewModeFromRoute } from "../utils/setScope";

const PAGE_SIZE = 25;
const SEARCH_SET_CODE = "All";

const route = useRoute();
const router = useRouter();

const meta = ref(null);
const accumulatedCards = ref([]);
const searchTotalMatches = ref(0);
const loadedPages = ref(0);
const loadingMore = ref(false);
const artExplorer = ref(null);
const artPanelLoading = ref(false);
const selectedBrowseName = ref("");
const artSelectedIndex = ref(0);
const searchQuery = ref("");
const textSearchQuery = ref("");
const creatureTypeQuery = ref("");
const searchInput = ref("");
const textSearchInput = ref("");
const creatureTypeInput = ref("");
const searchInputRef = ref(null);
const ownedFilter = ref("all");
const foilFilter = ref(getStoredFoilFilter());
const typeFilter = ref("all");
const colorFilters = ref([]);
const storageFilters = ref([]);
const rarityFilter = ref("all");
const cmcMin = ref("");
const cmcMax = ref("");
const priceMin = ref("");
const priceMax = ref("");
const powerMin = ref("");
const toughnessMin = ref("");
const mobileFiltersOpen = ref(false);
const searchViewMode = ref("gallery");
const routeSyncReady = ref(false);
const virtualGridRef = ref(null);
const { loading, run } = useAsyncLoad();
const { collectionCardScale, settings: pricingSettings } = usePricingSettings();
let searchRequestToken = 0;

const sets = computed(() => meta.value?.sets || []);
const cards = computed(() => accumulatedCards.value);
const totalMatches = computed(() => searchTotalMatches.value);
const totalPages = computed(() => Math.max(1, Math.ceil(totalMatches.value / PAGE_SIZE)));
const hasMoreResults = computed(() => loadedPages.value < totalPages.value);
const hasActiveSearch = computed(() => Boolean(
  searchQuery.value.trim() || textSearchQuery.value.trim() || creatureTypeQuery.value.trim(),
));
const isListView = computed(() => searchViewMode.value === "list");

const setLabels = computed(() => {
  const labels = new Map();
  for (const set of sets.value) {
    labels.set(set.setCode, formatSetDropdownLabel(set));
  }
  return labels;
});

function searchApiParams() {
  return {
    setCode: SEARCH_SET_CODE,
    ownedFilter: ownedFilter.value,
    foilFilter: foilFilter.value,
    typeFilter: typeFilter.value,
    colorFilters: colorFilters.value,
    storageFilters: storageFilters.value,
    rarityFilter: rarityFilter.value,
    cmcMin: parseOptionalNumber(cmcMin.value),
    cmcMax: parseOptionalNumber(cmcMax.value),
    priceMin: parseOptionalNumber(priceMin.value),
    priceMax: parseOptionalNumber(priceMax.value),
    powerMin: parseOptionalNumber(powerMin.value),
    toughnessMin: parseOptionalNumber(toughnessMin.value),
  };
}

function syncFiltersFromRoute() {
  const filters = searchFiltersFromRoute(route);
  ownedFilter.value = filters.ownedFilter;
  foilFilter.value = filters.foilFilter;
  typeFilter.value = filters.typeFilter;
  colorFilters.value = [...filters.colorFilters];
  storageFilters.value = [...filters.storageFilters];
  searchQuery.value = filters.searchQuery;
  textSearchQuery.value = filters.textSearchQuery;
  creatureTypeQuery.value = filters.creatureTypeQuery;
  searchInput.value = filters.searchQuery;
  textSearchInput.value = filters.textSearchQuery;
  creatureTypeInput.value = filters.creatureTypeQuery;
  rarityFilter.value = filters.rarityFilter;
  cmcMin.value = filters.cmcMin != null ? String(filters.cmcMin) : "";
  cmcMax.value = filters.cmcMax != null ? String(filters.cmcMax) : "";
  priceMin.value = filters.priceMin != null ? String(filters.priceMin) : "";
  priceMax.value = filters.priceMax != null ? String(filters.priceMax) : "";
  powerMin.value = filters.powerMin != null ? String(filters.powerMin) : "";
  toughnessMin.value = filters.toughnessMin != null ? String(filters.toughnessMin) : "";
  searchViewMode.value = filters.viewMode;
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
      foilFilter: foilFilter.value,
      typeFilter: typeFilter.value,
      colorFilters: colorFilters.value,
      storageFilters: storageFilters.value,
      searchQuery: searchQuery.value.trim(),
      textSearchQuery: textSearchQuery.value.trim(),
      creatureTypeQuery: creatureTypeQuery.value.trim(),
      rarityFilter: rarityFilter.value,
      cmcMin: parseOptionalNumber(cmcMin.value),
      cmcMax: parseOptionalNumber(cmcMax.value),
      priceMin: parseOptionalNumber(priceMin.value),
      priceMax: parseOptionalNumber(priceMax.value),
      powerMin: parseOptionalNumber(powerMin.value),
      toughnessMin: parseOptionalNumber(toughnessMin.value),
      viewMode: searchViewMode.value,
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
  const creatureTypeTerm = creatureTypeQuery.value.trim();
  if (!nameTerm && !textTerm && !creatureTypeTerm) {
    return null;
  }
  const token = ++searchRequestToken;
  const payload = await ignoreAborted(api.searchCards({
    q: nameTerm,
    text: textTerm,
    creatureType: creatureTypeTerm,
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

async function loadResults({ autoSelectFirst = false } = {}) {
  const nameTerm = searchQuery.value.trim();
  const textTerm = textSearchQuery.value.trim();
  const creatureTypeTerm = creatureTypeQuery.value.trim();
  if (!nameTerm && !textTerm && !creatureTypeTerm) {
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
  if (!isListView.value) {
    await fillVisibleResults();
  }
  if (autoSelectFirst) {
    await autoSelectFirstResult();
  }
}

async function loadMoreResults() {
  if (loadingMore.value || loading.value || !hasMoreResults.value) {
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

async function fillVisibleResults() {
  if (isListView.value) {
    return;
  }
  await nextTick();
  const root = virtualGridRef.value?.rootRef;
  if (!root || !hasMoreResults.value || loadingMore.value || loading.value) {
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

async function autoSelectFirstResult() {
  const first = accumulatedCards.value[0];
  if (!first?.name) {
    closeArtExplorer();
    return;
  }
  try {
    await loadNameVariants(first.name);
  } catch {
    closeArtExplorer();
  }
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

function onTypeFilterChange(event) {
  const next = event.target.value || "all";
  if (typeFilter.value === next) {
    return;
  }
  typeFilter.value = next;
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

function onRarityFilterChange(event) {
  const next = event.target.value || "all";
  if (rarityFilter.value === next) {
    return;
  }
  rarityFilter.value = next;
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

async function reloadLoadedSearchResults() {
  const pagesToLoad = Math.max(loadedPages.value, 1);
  resetSearchResults();
  for (let pageNum = 1; pageNum <= pagesToLoad; pageNum += 1) {
    const payload = await fetchSearchPage(pageNum);
    if (!payload) {
      break;
    }
    applySearchPayload(payload, { append: pageNum > 1 });
    if (pageNum >= (payload.totalPages ?? 1)) {
      break;
    }
  }
}

async function loadNameVariants(name, { preserveSelection = false } = {}) {
  selectedBrowseName.value = name;
  const current = preserveSelection ? artExplorer.value?.variants?.[artSelectedIndex.value] : null;
  artPanelLoading.value = true;
  if (!preserveSelection && artExplorer.value?.name !== name) {
    artExplorer.value = null;
  }
  try {
    const payload = await api.getSearchNameVariants({
      name,
      ...searchApiParams(),
    });
    artExplorer.value = payload;
    if (preserveSelection && current) {
      const nextIndex = payload.variants.findIndex(
        (variant) =>
          variant.setCode === current.setCode
          && String(variant.collectorNumber) === String(current.collectorNumber)
          && (variant.artStyle || "") === (current.artStyle || ""),
      );
      artSelectedIndex.value = nextIndex >= 0 ? nextIndex : 0;
    } else {
      artSelectedIndex.value = 0;
    }
  } finally {
    artPanelLoading.value = false;
  }
}

async function browseCardName(name) {
  try {
    await loadNameVariants(name);
  } catch (error) {
    window.alert(error.message || "Could not load card variants.");
  }
}

function closeArtExplorer() {
  artExplorer.value = null;
  artSelectedIndex.value = 0;
  artPanelLoading.value = false;
  selectedBrowseName.value = "";
}

async function submitSearch() {
  const nextName = searchInput.value.trim();
  const nextText = textSearchInput.value.trim();
  const nextCreatureType = creatureTypeInput.value.trim();
  const sameQuery = nextName === searchQuery.value.trim()
    && nextText === textSearchQuery.value.trim()
    && nextCreatureType === creatureTypeQuery.value.trim();
  searchQuery.value = nextName;
  textSearchQuery.value = nextText;
  creatureTypeQuery.value = nextCreatureType;
  closeArtExplorer();
  syncSearchRoute();
  if (sameQuery && (nextName || nextText || nextCreatureType)) {
    await loadResults({ autoSelectFirst: true });
  }
}

async function onArtOwnershipChanged() {
  const activeName = artExplorer.value?.name;
  if (activeName) {
    try {
      await loadNameVariants(activeName, { preserveSelection: true });
    } catch {
      // Keep the current explorer state if variant refresh fails.
    }
  }
  if (!hasActiveSearch.value) {
    return;
  }
  await reloadLoadedSearchResults();
}

watch([ownedFilter, foilFilter, typeFilter, colorFilters, storageFilters, rarityFilter, cmcMin, cmcMax, priceMin, priceMax, powerMin, toughnessMin, searchViewMode], () => {
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
    route.query.owned,
    route.query.finish,
    route.query.type,
    route.query.colors,
    route.query.storage,
    route.query.rarity,
    route.query.cmcMin,
    route.query.cmcMax,
    route.query.priceMin,
    route.query.priceMax,
    route.query.powMin,
    route.query.tghMin,
  ],
  async (_value, _oldValue, onCleanup) => {
    if (!routeSyncReady.value) {
      return;
    }
    const prevName = searchQuery.value;
    const prevText = textSearchQuery.value;
    const prevCreatureType = creatureTypeQuery.value;
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
      || creatureTypeQuery.value !== prevCreatureType;
    await loadResults({ autoSelectFirst: searchChanged });
    if (cancelled) {
      return;
    }
  },
);

onMounted(async () => {
  syncFiltersFromRoute();
  await Promise.all([fetchPricingSettings(), loadMeta()]);
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
            <input
              id="collection-search-page-creature-input"
              v-model="creatureTypeInput"
              type="search"
              class="collection-search-input collection-search-page-input"
              placeholder="Creature type…"
              autocomplete="off"
              spellcheck="false"
              aria-label="Search cards by creature type"
            >
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
                <CollectionGalleryScaleControl
                  v-if="!isListView"
                  class="collection-gallery-toolbar-scale"
                  :model-value="collectionCardScale"
                  :options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150]"
                  @update:model-value="setCollectionCardScale"
                />
              </div>
              <GalleryLoadingOverlay :loading="loading && !loadingMore" label="Searching cards…">
                <VirtualizedCollectionCardGrid
                  v-if="!isListView"
                  ref="virtualGridRef"
                  :cards="cards"
                  :show-unowned-badge="false"
                  :card-scale="collectionCardScale"
                  :has-more="hasMoreResults"
                  browse-names
                  :selected-name="selectedBrowseName"
                  @browse-name="browseCardName"
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
              <p v-if="loadingMore" class="collection-search-load-more-status">
                <LoadingIndicator label="Loading more cards…" />
              </p>
            </div>

            <p
              v-else-if="!hasActiveSearch"
              class="collection-search-results-hint collection-search-empty-prompt"
            >
              Search for a card name, creature type, or rules text to browse art versions across your collection.
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
              @update:selected-index="artSelectedIndex = $event"
              @close="closeArtExplorer"
              @ownership-changed="onArtOwnershipChanged"
            />
          </aside>
        </div>
      </div>

      <FilterSidebar class="collection-desktop-filters collection-search-filters-sidebar">
        <CollectionAllFilters
          :is-all-view="true"
          :is-all-sets-view="true"
          :art-styles="[]"
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
          :show-sort="false"
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
        :storage-filters="storageFilters"
        :rarity-filter="rarityFilter"
        :cmc-min="cmcMin"
        :cmc-max="cmcMax"
        :price-min="priceMin"
        :price-max="priceMax"
        :power-min="powerMin"
        :toughness-min="toughnessMin"
        :show-sort="false"
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
      />
    </CollectionMobileFilterSheet>
  </div>
</template>
