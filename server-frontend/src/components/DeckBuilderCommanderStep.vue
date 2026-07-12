<script setup>
import { ref } from "vue";
import { api } from "../api";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import ManaSymbols from "./ManaSymbols.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";

const props = defineProps({
  selectedCommander: { type: Object, default: null },
});

const emit = defineEmits(["select"]);

const searchInput = ref("");
const searchQuery = ref("");
const resultsPayload = ref(null);
const { loading, run } = useAsyncLoad();

const PAGE_SIZE = 40;

let debounceTimer = null;

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

async function loadResults() {
  const trimmed = searchQuery.value.trim();
  if (!trimmed) {
    resultsPayload.value = await api.getBuilderCommanders({ page: 1, pageSize: PAGE_SIZE });
    return;
  }
  await run(async () => {
    resultsPayload.value = await api.getBuilderCommanders({
      q: trimmed,
      page: 1,
      pageSize: PAGE_SIZE,
    });
  });
}

function selectCommander(card) {
  emit("select", {
    ...card,
    cardName: card.name || card.cardName || "Unknown",
  });
}

function onBrowseName(name) {
  const card = resultsPayload.value?.cards?.find((item) => item.name === name);
  if (card) {
    selectCommander(card);
  }
}

loadResults();
</script>

<template>
  <section class="deck-builder-step">
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

    <div v-if="loading" class="deck-builder-loading">
      <LoadingIndicator label="Loading commanders…" />
    </div>

    <div v-else-if="resultsPayload?.cards?.length" class="collection-page">
      <p class="deck-builder-result-count">
        {{ resultsPayload.total }} owned commander print{{ resultsPayload.total === 1 ? "" : "s" }}
      </p>
      <CollectionCardGrid
        :cards="resultsPayload.cards.map((card) => ({
          ...card,
          cardName: card.name,
          owned: true,
        }))"
        browse-names
        :card-scale="78"
        @browse-name="onBrowseName"
      />
    </div>

    <p v-else class="deck-builder-empty">
      No owned legendary commanders found. Add cards to storage first.
    </p>
  </section>
</template>
