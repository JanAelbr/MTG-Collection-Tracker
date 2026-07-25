<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api } from "../api";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import ManaSymbols from "./ManaSymbols.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { DECK_COLOR_ORDER } from "../utils/deckCards";
import { cardFinish } from "../utils/finishes";

const props = defineProps({
  selectedCommander: { type: Object, default: null },
});

const emit = defineEmits(["select"]);

const searchInput = ref("");
const searchQuery = ref("");
const colorFilters = ref([]);
const accumulatedCards = ref([]);
const totalResults = ref(0);
const loadedPages = ref(0);
const loadingMore = ref(false);
const loadMoreSentinel = ref(null);
const { loading, run } = useAsyncLoad();

const PAGE_SIZE = 48;

let debounceTimer = null;
let loadRequestToken = 0;
let sentinelObserver = null;

const selectedKey = computed(() => {
  const card = props.selectedCommander;
  if (!card?.setCode || card?.collectorNumber == null) {
    return "";
  }
  return `${card.setCode}|${card.collectorNumber}|${cardFinish(card)}`;
});

const gridCards = computed(() =>
  accumulatedCards.value.map((card) => ({
    ...card,
    cardName: card.name,
    owned: true,
  })),
);

const totalPages = computed(() => Math.max(1, Math.ceil(totalResults.value / PAGE_SIZE)));
const hasMore = computed(() => loadedPages.value < totalPages.value && totalResults.value > 0);

function scheduleDebouncedSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    if (searchInput.value.trim() === searchQuery.value.trim()) {
      return;
    }
    searchQuery.value = searchInput.value.trim();
    loadResults();
  }, 350);
}

function commitSearch() {
  clearTimeout(debounceTimer);
  searchQuery.value = searchInput.value.trim();
  loadResults();
}

function toggleColorFilter(color) {
  if (colorFilters.value.includes(color)) {
    colorFilters.value = colorFilters.value.filter((item) => item !== color);
  } else {
    colorFilters.value = [...colorFilters.value, color];
  }
  loadResults();
}

function clearColorFilters() {
  if (!colorFilters.value.length) {
    return;
  }
  colorFilters.value = [];
  loadResults();
}

function buildParams(page) {
  const params = {
    page,
    pageSize: PAGE_SIZE,
    uniquePrints: true,
  };
  const trimmed = searchQuery.value.trim();
  if (trimmed) {
    params.q = trimmed;
  }
  if (colorFilters.value.length) {
    params.colors = colorFilters.value.join(",");
  }
  return params;
}

function resetResults() {
  accumulatedCards.value = [];
  totalResults.value = 0;
  loadedPages.value = 0;
}

async function fetchPage(page) {
  return api.getBuilderCommanders(buildParams(page));
}

function applyPayload(payload, { append }) {
  const cards = payload?.cards || [];
  totalResults.value = Number(payload?.total) || 0;
  loadedPages.value = Number(payload?.page) || (append ? loadedPages.value + 1 : 1);
  if (append) {
    const seen = new Set(
      accumulatedCards.value.map((card) => String(card.name || "").toLowerCase()),
    );
    const next = [];
    for (const card of cards) {
      const key = String(card.name || "").toLowerCase();
      if (!key || seen.has(key)) {
        continue;
      }
      seen.add(key);
      next.push(card);
    }
    accumulatedCards.value = [...accumulatedCards.value, ...next];
    return;
  }
  accumulatedCards.value = cards;
}

async function loadResults() {
  const token = ++loadRequestToken;
  loadingMore.value = false;
  await run(async (isCurrent) => {
    resetResults();
    const payload = await fetchPage(1);
    if (!isCurrent() || token !== loadRequestToken || !payload) {
      return;
    }
    applyPayload(payload, { append: false });
  });
  if (token === loadRequestToken) {
    await fillViewport();
  }
}

async function loadMore() {
  if (loading.value || loadingMore.value || !hasMore.value) {
    return;
  }
  const token = loadRequestToken;
  const nextPage = loadedPages.value + 1;
  loadingMore.value = true;
  try {
    const payload = await fetchPage(nextPage);
    if (token !== loadRequestToken || !payload) {
      return;
    }
    applyPayload(payload, { append: true });
  } finally {
    if (token === loadRequestToken) {
      loadingMore.value = false;
    }
  }
}

async function fillViewport() {
  await nextTick();
  if (!hasMore.value || loading.value || loadingMore.value) {
    return;
  }
  const sentinel = loadMoreSentinel.value;
  if (!sentinel) {
    return;
  }
  const rect = sentinel.getBoundingClientRect();
  // If the sentinel is still on-screen, keep loading until the grid can scroll.
  if (rect.top <= (window.innerHeight || 0) + 80) {
    await loadMore();
    if (hasMore.value) {
      await fillViewport();
    }
  }
}

function selectCommander(card) {
  emit("select", {
    ...card,
    cardName: card.name || card.cardName || "Unknown",
  });
}

function setupSentinelObserver() {
  teardownSentinelObserver();
  if (typeof IntersectionObserver === "undefined") {
    return;
  }
  sentinelObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadMore();
      }
    },
    { root: null, rootMargin: "320px 0px", threshold: 0 },
  );
  if (loadMoreSentinel.value) {
    sentinelObserver.observe(loadMoreSentinel.value);
  }
}

function teardownSentinelObserver() {
  if (sentinelObserver) {
    sentinelObserver.disconnect();
    sentinelObserver = null;
  }
}

watch(loadMoreSentinel, (el) => {
  teardownSentinelObserver();
  if (el) {
    setupSentinelObserver();
  }
});

onMounted(() => {
  setupSentinelObserver();
  loadResults();
});

onBeforeUnmount(() => {
  clearTimeout(debounceTimer);
  teardownSentinelObserver();
  loadRequestToken += 1;
});
</script>

<template>
  <section class="deck-builder-step deck-builder-commander-step">
    <header class="deck-builder-step-head">
      <h3>Pick your commander</h3>
      <p>Choose a legendary creature or planeswalker you own.</p>
    </header>

    <div v-if="selectedCommander" class="deck-builder-selected-commander">
      <img
        v-if="selectedCommander.imageUri"
        :src="selectedCommander.imageUri"
        :alt="selectedCommander.cardName || selectedCommander.name"
        loading="lazy"
      />
      <div>
        <strong>{{ selectedCommander.cardName || selectedCommander.name }}</strong>
        <ManaSymbols :colors="selectedCommander.colorIdentity || selectedCommander.colors || []" />
      </div>
    </div>

    <div class="deck-builder-commander-filters">
      <div class="collection-search-input-row">
        <input
          v-model="searchInput"
          type="search"
          class="collection-search-input"
          placeholder="Search owned legendaries…"
          autocomplete="off"
          aria-label="Search owned commanders"
          @input="scheduleDebouncedSearch"
        />
        <button type="button" class="btn btn-primary" :disabled="loading" @click="commitSearch">
          Search
        </button>
      </div>

      <div class="deck-builder-color-filter-group">
        <span class="deck-builder-filter-label">Color identity</span>
        <span class="deck-builder-filter-hint">Exact match (AND)</span>
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
    </div>

    <div v-if="loading && !gridCards.length" class="deck-builder-loading">
      <LoadingIndicator label="Loading commanders…" />
    </div>

    <div v-else-if="gridCards.length" class="collection-page deck-builder-commander-grid">
      <p class="deck-builder-result-count">
        Showing {{ gridCards.length }} of {{ totalResults }} unique commander{{ totalResults === 1 ? "" : "s" }}
      </p>
      <CollectionCardGrid
        :cards="gridCards"
        pick-prints
        zoom-only
        :card-scale="130"
        :selected-key="selectedKey"
        @pick-card="selectCommander"
      />
      <div
        ref="loadMoreSentinel"
        class="deck-builder-load-more-sentinel"
        aria-hidden="true"
      />
      <div v-if="loadingMore" class="deck-builder-loading-more">
        <LoadingIndicator label="Loading more…" />
      </div>
      <p v-else-if="!hasMore" class="deck-builder-end-of-results">
        End of results
      </p>
    </div>

    <p v-else class="deck-builder-empty">
      No owned legendary commanders found. Add cards to storage first.
    </p>
  </section>
</template>
