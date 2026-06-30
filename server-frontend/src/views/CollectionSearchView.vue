<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ignoreAborted } from "../api";
import CollectionCardGrid from "../components/CollectionCardGrid.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import SearchArtBrowser from "../components/SearchArtBrowser.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
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
const searchInput = ref("");
const searchQuery = ref("");
const ownedFilter = ref("all");
const foilFilter = ref(getStoredFoilFilter());
const page = ref(1);
const randomLoading = ref(false);
const routeSyncReady = ref(false);
const { loading, run } = useAsyncLoad();
const { collectionCardScale } = usePricingSettings();

let debounceTimer = null;

const sets = computed(() => meta.value?.sets || []);
const cards = computed(() => resultsPayload.value?.cards || []);
const totalMatches = computed(() => resultsPayload.value?.totalMatches ?? 0);
const totalPages = computed(() => resultsPayload.value?.totalPages ?? 1);

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
  searchInput.value = searchQuery.value;
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

function commitSearch() {
  clearTimeout(debounceTimer);
  const trimmed = searchInput.value.trim();
  searchQuery.value = trimmed;
  page.value = 1;
  syncSearchRoute();
  loadResults({ autoSelectFirst: true });
}

function scheduleDebouncedSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    if (searchInput.value.trim() === searchQuery.value.trim()) {
      return;
    }
    commitSearch();
  }, 350);
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
    <section class="collection-search-hero table-panel">
      <form class="collection-search-form" @submit.prevent="commitSearch">
        <div class="collection-search-input-row">
          <input
            v-model="searchInput"
            type="search"
            class="collection-search-input"
            placeholder="Search by name, number, art style, type…"
            autocomplete="off"
            aria-label="Search cards"
            @input="scheduleDebouncedSearch"
          />
          <button type="submit" class="btn btn-primary" :disabled="loading">
            Search
          </button>
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="randomLoading"
            title="Pick a random card name and browse its art on this page"
            @click="openRandomCard"
          >
            {{ randomLoading ? "…" : "Random" }}
          </button>
        </div>
        <p class="collection-search-hint">
          Try a card name, collector number, art style, or card type. Filters below narrow results.
        </p>
      </form>
    </section>

    <div class="reports-toolbar">
      <div class="reports-toolbar-filters">
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
            Not owned
          </button>
        </div>

        <div class="button-group collection-finish-group">
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
      </div>
    </div>

    <SearchArtBrowser
      v-if="artExplorer"
      :name="artExplorer.name"
      :variants="artExplorer.variants"
      :selected-index="artSelectedIndex"
      :set-label-for="setLabel"
      @update:selected-index="artSelectedIndex = $event"
      @random="openRandomCard"
      @close="closeArtExplorer"
    />

    <p v-if="searchQuery.trim()" class="manager-stats">
      <template v-if="totalMatches">
        {{ totalMatches }} unique card{{ totalMatches === 1 ? "" : "s" }} for “{{ searchQuery }}”
        <span v-if="totalPages > 1"> · page {{ page }} / {{ totalPages }}</span>
      </template>
      <template v-else-if="!loading">
        No cards match “{{ searchQuery }}” with these filters.
      </template>
    </p>
    <p v-else class="manager-stats collection-search-empty-prompt">
      Browsing a random card. Enter a search term to find specific cards.
    </p>

    <div v-if="loading && !cards.length" class="storage-empty">
      <LoadingIndicator label="Searching cards…" />
    </div>

    <div v-else-if="searchQuery.trim() && cards.length" class="table-panel cards-panel reports-cards-panel">
      <GalleryLoadingOverlay :loading="loading" label="Searching cards…">
        <CollectionCardGrid
          :cards="cards"
          :show-unowned-badge="false"
          :card-scale="collectionCardScale"
          browse-names
          :selected-name="selectedCardName"
          @browse-name="browseCardName"
        />
      </GalleryLoadingOverlay>
    </div>

    <div v-if="searchQuery.trim() && totalPages > 1" class="manager-pagination">
      <button
        type="button"
        class="btn btn-secondary btn-small"
        :disabled="page <= 1"
        @click="goToPage(page - 1)"
      >
        Previous
      </button>
      <span>Page {{ page }} / {{ totalPages }}</span>
      <button
        type="button"
        class="btn btn-secondary btn-small"
        :disabled="page >= totalPages"
        @click="goToPage(page + 1)"
      >
        Next
      </button>
    </div>
  </div>
</template>
