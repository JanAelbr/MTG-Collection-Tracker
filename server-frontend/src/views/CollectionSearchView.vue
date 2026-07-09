<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ignoreAborted } from "../api";
import CollectionCardGrid from "../components/CollectionCardGrid.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import SearchArtBrowser from "../components/SearchArtBrowser.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import CollectionGalleryScaleControl from "../components/CollectionGalleryScaleControl.vue";
import PageControls from "../components/PageControls.vue";
import FilterSidebar from "../components/FilterSidebar.vue";
import { getStoredFoilFilter, storeFoilFilter } from "../utils/filterStorage";
import { formatSetDropdownLabel } from "../utils/format";

const PAGE_SIZE = 25;
const SEARCH_SET_CODE = "All";

const route = useRoute();
const router = useRouter();

const meta = ref(null);
const resultsPayload = ref(null);
const artExplorer = ref(null);
const artSelectedIndex = ref(0);
const selectedCardName = ref("");
const searchQuery = ref("");
const ownedFilter = ref("all");
const foilFilter = ref(getStoredFoilFilter());
const page = ref(1);
const randomLoading = ref(false);
const routeSyncReady = ref(false);
const { loading, run } = useAsyncLoad();
const { collectionCardScale, settings: pricingSettings } = usePricingSettings();

const sets = computed(() => meta.value?.sets || []);
const cards = computed(() => resultsPayload.value?.cards || []);
const totalMatches = computed(() => resultsPayload.value?.totalMatches ?? 0);
const totalPages = computed(() => resultsPayload.value?.totalPages ?? 1);
const resultsRangeStart = computed(() => {
  if (!totalMatches.value) {
    return 0;
  }
  return (page.value - 1) * PAGE_SIZE + 1;
});
const resultsRangeEnd = computed(() => Math.min(page.value * PAGE_SIZE, totalMatches.value));

const setLabels = computed(() => {
  const labels = new Map();
  for (const set of sets.value) {
    labels.set(set.setCode, formatSetDropdownLabel(set));
  }
  return labels;
});

function searchRouteQuery() {
  const query = {};
  const trimmed = searchQuery.value.trim();
  if (trimmed) {
    query.q = trimmed;
  }
  if (ownedFilter.value !== "all") {
    query.owned = ownedFilter.value;
  }
  if (foilFilter.value !== "all") {
    query.finish = foilFilter.value;
  }
  if (page.value > 1) {
    query.page = String(page.value);
  }
  return query;
}

function syncFiltersFromRoute() {
  const owned = route.query.owned;
  if (owned === "owned" || owned === "unowned") {
    ownedFilter.value = owned;
  } else {
    ownedFilter.value = "all";
  }
  const finish = route.query.finish;
  if (finish === "nonfoil" || finish === "foil" || finish === "etched") {
    foilFilter.value = finish;
  }
  const q = route.query.q;
  searchQuery.value = typeof q === "string" ? q : "";
  const pageParam = route.query.page;
  const parsedPage = Number(pageParam);
  page.value = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;
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
    query: searchRouteQuery(),
  });
}

async function loadMeta() {
  const next = await ignoreAborted(api.getReportsMeta());
  if (next) {
    meta.value = next;
  }
}

async function loadResults({ autoSelectFirst = false } = {}) {
  const trimmed = searchQuery.value.trim();
  if (!trimmed) {
    resultsPayload.value = null;
    if (autoSelectFirst) {
      closeArtExplorer();
    }
    return;
  }
  await run(async () => {
    resultsPayload.value = await api.searchCards({
      q: trimmed,
      setCode: SEARCH_SET_CODE,
      ownedFilter: ownedFilter.value,
      foilFilter: foilFilter.value,
      page: page.value,
      pageSize: PAGE_SIZE,
    });
  });
  if (autoSelectFirst) {
    await autoSelectFirstResult();
  }
}

async function autoSelectFirstResult() {
  const first = resultsPayload.value?.cards?.[0];
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
  page.value = 1;
}

function setFoilFilter(value) {
  if (foilFilter.value === value) {
    return;
  }
  foilFilter.value = value;
  storeFoilFilter(value);
  page.value = 1;
}

async function setCollectionCardScale(scale) {
  await savePricingSettings({ collectionCardScale: Number(scale) });
}

function goToPage(nextPage) {
  page.value = Math.max(1, Math.min(nextPage, totalPages.value));
}

async function loadNameVariants(name) {
  const payload = await api.getSearchNameVariants({
    name,
    q: searchQuery.value.trim(),
    setCode: SEARCH_SET_CODE,
    ownedFilter: ownedFilter.value,
    foilFilter: foilFilter.value,
  });
  artExplorer.value = payload;
  artSelectedIndex.value = 0;
  selectedCardName.value = name;
}

async function openRandomCard() {
  randomLoading.value = true;
  try {
    const payload = await api.getRandomSearchExplore({
      q: searchQuery.value.trim(),
      setCode: SEARCH_SET_CODE,
      ownedFilter: ownedFilter.value,
      foilFilter: foilFilter.value,
    });
    artExplorer.value = payload;
    artSelectedIndex.value = 0;
    selectedCardName.value = payload.name;
  } catch (error) {
    window.alert(error.message || "No cards match these filters.");
  } finally {
    randomLoading.value = false;
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
  selectedCardName.value = "";
}

async function onArtOwnershipChanged() {
  if (!searchQuery.value.trim()) {
    return;
  }
  await loadResults();
}

watch([ownedFilter, foilFilter], () => {
  if (!routeSyncReady.value) {
    return;
  }
  page.value = 1;
  syncSearchRoute();
  if (searchQuery.value.trim()) {
    closeArtExplorer();
    loadResults({ autoSelectFirst: true });
  } else {
    openRandomCard();
  }
});

watch(page, () => {
  if (!routeSyncReady.value) {
    return;
  }
  syncSearchRoute();
  loadResults();
});

watch(
  () => [route.query.q, route.query.owned, route.query.finish, route.query.page],
  () => {
    if (!routeSyncReady.value) {
      return;
    }
    const prevQuery = searchQuery.value;
    syncFiltersFromRoute();
    if (searchQuery.value !== prevQuery) {
      if (searchQuery.value.trim()) {
        loadResults({ autoSelectFirst: true });
      } else {
        openRandomCard();
      }
    }
  },
);

onMounted(async () => {
  syncFiltersFromRoute();
  await Promise.all([fetchPricingSettings(), loadMeta()]);
  routeSyncReady.value = true;
  stripSetScopeFromRoute();
  if (searchQuery.value.trim()) {
    await loadResults({ autoSelectFirst: true });
  } else {
    await openRandomCard();
  }
});
</script>

<template>
  <div class="reports-page collection-page collection-search-page">
    <div class="page-with-sidebar">
      <FilterSidebar>
        <div class="filter-sidebar-section filter-sidebar-section--compact-filters">
          <div class="filter-sidebar-compact-filter">
            <p class="filter-sidebar-label">Ownership</p>
            <div class="button-group collection-ownership-group">
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
                Unowned
              </button>
            </div>
          </div>

          <div class="filter-sidebar-compact-filter">
            <p class="filter-sidebar-label">Finish</p>
            <div class="button-group collection-finish-group">
              <button
                type="button"
                class="filter-button"
                :class="{ active: foilFilter === 'all' }"
                @click="setFoilFilter('all')"
              >
                All
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
          </div>
        </div>
      </FilterSidebar>

      <div class="page-with-sidebar-main collection-search-main">
        <div class="collection-search-toolbar">
          <p v-if="searchQuery.trim()" class="collection-search-toolbar-query">
            Results for “{{ searchQuery.trim() }}”
          </p>
          <p v-else class="collection-search-toolbar-query collection-search-empty-prompt">
            Use the search bar above to find cards by name, or browse a random one.
          </p>
          <button
            type="button"
            class="btn btn-secondary btn-small collection-search-random-btn"
            :disabled="randomLoading"
            title="Pick a random card name and browse its art on this page"
            @click="openRandomCard"
          >
            {{ randomLoading ? "…" : "Random card" }}
          </button>
        </div>

        <div class="collection-search-body">
          <div class="collection-search-results">
            <p
              v-if="searchQuery.trim() && !loading && !totalMatches"
              class="manager-stats collection-search-empty-prompt"
            >
              No cards match “{{ searchQuery }}” with these filters.
            </p>

            <div v-if="loading && !cards.length" class="storage-empty">
              <LoadingIndicator label="Searching cards…" />
            </div>

            <div
              v-else-if="searchQuery.trim() && cards.length"
              class="table-panel cards-panel reports-cards-panel collection-gallery-panel"
            >
              <div class="collection-gallery-toolbar">
                <p class="collection-gallery-toolbar-stats">
                  Showing {{ resultsRangeStart }}–{{ resultsRangeEnd }} of {{ totalMatches }} cards
                </p>
                <PageControls
                  v-if="totalPages > 1"
                  :page="page"
                  :total-pages="totalPages"
                  class="collection-gallery-toolbar-pagination"
                  @update:page="goToPage"
                />
                <CollectionGalleryScaleControl
                  class="collection-gallery-toolbar-scale"
                  :model-value="collectionCardScale"
                  :options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150]"
                  @update:model-value="setCollectionCardScale"
                />
              </div>
              <GalleryLoadingOverlay :loading="loading" label="Searching cards…">
                <CollectionCardGrid
                  :cards="cards"
                  :show-unowned-badge="false"
                  :card-scale="collectionCardScale"
                  browse-names
                  :selected-name="selectedCardName"
                  @browse-name="browseCardName"
                  @ownership-changed="onArtOwnershipChanged"
                />
              </GalleryLoadingOverlay>
            </div>

            <p
              v-else-if="!searchQuery.trim() && !artExplorer"
              class="collection-search-results-hint collection-search-empty-prompt"
            >
              Select a card from the list after searching, or use Random card.
            </p>
          </div>

          <aside v-if="artExplorer" class="collection-search-detail">
            <SearchArtBrowser
              sidebar
              :name="artExplorer.name"
              :variants="artExplorer.variants"
              :selected-index="artSelectedIndex"
              :set-label-for="setLabel"
              :show-random="!searchQuery.trim()"
              @update:selected-index="artSelectedIndex = $event"
              @random="openRandomCard"
              @close="closeArtExplorer"
              @ownership-changed="onArtOwnershipChanged"
            />
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>
