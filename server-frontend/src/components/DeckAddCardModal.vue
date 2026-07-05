<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import SearchArtBrowser from "./SearchArtBrowser.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { cardTypeGroup } from "../utils/deckCards";
import { COLLECTION_TYPE_LABELS, COLLECTION_TYPE_ORDER } from "../utils/collectionTypes";
import { cardFinish } from "../utils/finishes";
import { formatSetDropdownLabel } from "../utils/format";

const PAGE_SIZE = 25;
const SEARCH_SET_CODE = "All";

const props = defineProps({
  open: { type: Boolean, default: false },
  deckId: { type: String, required: true },
  deckName: { type: String, default: "" },
  section: { type: String, default: "main" },
  cardType: { type: String, default: "" },
  typeLabel: { type: String, default: "" },
});

const emit = defineEmits(["close", "added"]);

const meta = ref(null);
const resultsPayload = ref(null);
const artExplorer = ref(null);
const artSelectedIndex = ref(0);
const selectedCardName = ref("");
const searchInput = ref("");
const searchQuery = ref("");
const ownedFilter = ref("all");
const foilFilter = ref("all");
const typeFilter = ref("all");
const page = ref(1);
const adding = ref(false);
const addMessage = ref("");
const addError = ref("");
const { loading, run } = useAsyncLoad();

let debounceTimer = null;

const sets = computed(() => meta.value?.sets || []);
const setLabels = computed(() => {
  const labels = new Map();
  for (const set of sets.value) {
    labels.set(set.setCode, formatSetDropdownLabel(set));
  }
  return labels;
});

const modalTitle = computed(() => {
  const target = activeTypeLabel.value || "card";
  if (props.deckName) {
    return `Add ${target.toLowerCase()} to ${props.deckName}`;
  }
  return `Add ${target.toLowerCase()} to deck`;
});

const activeTypeLabel = computed(() => {
  if (typeFilter.value === "all") {
    return props.typeLabel || "card";
  }
  return COLLECTION_TYPE_LABELS[typeFilter.value] || typeFilter.value;
});

const filteredCards = computed(() => {
  const cards = resultsPayload.value?.cards || [];
  if (typeFilter.value === "all") {
    return cards;
  }
  return cards.filter((card) => cardTypeGroup(card) === typeFilter.value);
});

const filteredVariants = computed(() => {
  const variants = artExplorer.value?.variants || [];
  if (typeFilter.value === "all") {
    return variants;
  }
  return variants.filter((card) => cardTypeGroup(card) === typeFilter.value);
});

const selectedVariant = computed(() => filteredVariants.value[artSelectedIndex.value] || null);

const totalMatches = computed(() => {
  if (!searchQuery.value.trim()) {
    return 0;
  }
  return filteredCards.value.length;
});

const totalPages = computed(() => {
  const total = resultsPayload.value?.totalMatches ?? 0;
  const serverPages = resultsPayload.value?.totalPages ?? 1;
  if (typeFilter.value === "all") {
    return serverPages;
  }
  return Math.max(1, Math.ceil(totalMatches.value / PAGE_SIZE));
});

function applyTypeFilterFromContext() {
  typeFilter.value = props.cardType || "all";
}

function setLabel(code) {
  return setLabels.value.get(code) || code;
}

function setTypeFilter(value) {
  if (typeFilter.value === value) {
    return;
  }
  typeFilter.value = value;
  page.value = 1;
  reloadSearch();
}

function matchesType(card) {
  if (typeFilter.value === "all") {
    return true;
  }
  return cardTypeGroup(card) === typeFilter.value;
}

function resetState() {
  clearTimeout(debounceTimer);
  resultsPayload.value = null;
  artExplorer.value = null;
  artSelectedIndex.value = 0;
  selectedCardName.value = "";
  searchInput.value = "";
  searchQuery.value = "";
  ownedFilter.value = "all";
  foilFilter.value = "all";
  page.value = 1;
  addMessage.value = "";
  addError.value = "";
}

async function ensureMeta() {
  if (meta.value) {
    return;
  }
  meta.value = await api.getReportsMeta();
}

function commitSearch() {
  clearTimeout(debounceTimer);
  searchQuery.value = searchInput.value.trim();
  page.value = 1;
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
  reloadSearch();
}

function setFoilFilter(value) {
  if (foilFilter.value === value) {
    return;
  }
  foilFilter.value = value;
  page.value = 1;
  reloadSearch();
}

function reloadSearch() {
  if (!searchQuery.value.trim()) {
    closeArtExplorer();
    return;
  }
  closeArtExplorer();
  loadResults({ autoSelectFirst: true });
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
  const first = filteredCards.value[0];
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

async function loadNameVariants(name) {
  const payload = await api.getSearchNameVariants({
    name,
    q: searchQuery.value.trim(),
    setCode: SEARCH_SET_CODE,
    ownedFilter: ownedFilter.value,
    foilFilter: foilFilter.value,
  });
  const variants = (payload.variants || []).filter(matchesType);
  if (!variants.length) {
    throw new Error("No matching prints for this card type.");
  }
  artExplorer.value = { ...payload, variants };
  artSelectedIndex.value = 0;
  selectedCardName.value = name;
}

async function browseCardName(name) {
  addError.value = "";
  try {
    await loadNameVariants(name);
  } catch (error) {
    addError.value = error.message || "Could not load card variants.";
  }
}

function closeArtExplorer() {
  artExplorer.value = null;
  artSelectedIndex.value = 0;
  selectedCardName.value = "";
}

function closeModal() {
  resetState();
  emit("close");
}

async function addSelectedToDeck() {
  const card = selectedVariant.value;
  if (!card || adding.value) {
    return;
  }
  adding.value = true;
  addError.value = "";
  addMessage.value = "";
  try {
    const result = await api.addCardToDeck(props.deckId, {
      setCode: card.setCode,
      collectorNumber: card.collectorNumber,
      finish: cardFinish(card),
      section: props.section || "main",
    });
    clearClientCache();
    addMessage.value = result.created
      ? `Added to ${result.deckName}`
      : `Qty ${result.qty} in ${result.deckName}`;
    emit("added", result);
  } catch (error) {
    addError.value = error.message || "Could not add card to deck.";
  } finally {
    adding.value = false;
  }
}

function goToPage(nextPage) {
  page.value = Math.max(1, Math.min(nextPage, totalPages.value));
  loadResults();
}

watch(
  () => props.open,
  async (isOpen) => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    if (!isOpen) {
      resetState();
      return;
    }
    resetState();
    applyTypeFilterFromContext();
    await ensureMeta();
  },
);

watch(
  () => [props.cardType, props.typeLabel],
  () => {
    if (props.open) {
      applyTypeFilterFromContext();
    }
  },
);

watch(artSelectedIndex, (index) => {
  if (index >= filteredVariants.value.length) {
    artSelectedIndex.value = Math.max(0, filteredVariants.value.length - 1);
  }
});

onUnmounted(() => {
  document.body.style.overflow = "";
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop deck-add-card-modal-backdrop"
      @click.self="closeModal"
    >
    <div class="modal-card deck-add-card-modal" role="dialog" aria-modal="true">
      <header class="deck-add-card-modal-head">
        <div>
          <h3>{{ modalTitle }}</h3>
          <p class="deck-add-card-modal-subtitle">
            Search the catalog, pick a printing, then add it to the deck.
          </p>
        </div>
        <button type="button" class="btn btn-secondary btn-small" @click="closeModal">
          Close
        </button>
      </header>

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
        </div>
      </form>

      <div class="reports-toolbar deck-add-card-modal-filters">
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

          <div class="deck-add-card-type-filter">
            <select
              :value="typeFilter"
              aria-label="Card type"
              @change="setTypeFilter($event.target.value)"
            >
              <option value="all">All types</option>
              <option v-for="type in COLLECTION_TYPE_ORDER" :key="type" :value="type">
                {{ COLLECTION_TYPE_LABELS[type] }}
              </option>
            </select>
          </div>
        </div>
      </div>

      <div class="deck-add-card-modal-body collection-page">
        <SearchArtBrowser
          v-if="artExplorer && filteredVariants.length"
          :name="artExplorer.name"
          :variants="filteredVariants"
          :selected-index="artSelectedIndex"
          :set-label-for="setLabel"
          :show-random="false"
          @update:selected-index="artSelectedIndex = $event"
          @close="closeArtExplorer"
        />

        <div v-if="selectedVariant" class="deck-add-card-modal-actions">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="adding"
            @click="addSelectedToDeck"
          >
            {{ adding ? "Adding…" : "Add to deck" }}
          </button>
          <p v-if="addMessage" class="deck-add-card-modal-status">{{ addMessage }}</p>
        </div>

        <p v-if="searchQuery.trim()" class="manager-stats">
          <template v-if="totalMatches">
            {{ totalMatches }} unique card{{ totalMatches === 1 ? "" : "s" }} for “{{ searchQuery }}”
            <span v-if="totalPages > 1"> · page {{ page }} / {{ totalPages }}</span>
          </template>
          <template v-else-if="!loading">
            No {{ activeTypeLabel.toLowerCase() }} match “{{ searchQuery }}”.
          </template>
        </p>
        <p v-else-if="!artExplorer && !loading" class="manager-stats collection-search-empty-prompt">
          Search for a card to browse printings and add it to the deck.
        </p>

        <div v-if="loading && !filteredCards.length" class="storage-empty">
          <LoadingIndicator label="Searching cards…" />
        </div>

        <div
          v-else-if="searchQuery.trim() && filteredCards.length"
          class="table-panel cards-panel reports-cards-panel deck-add-card-modal-results"
        >
          <CollectionCardGrid
            :cards="filteredCards"
            :show-unowned-badge="false"
            browse-names
            :selected-name="selectedCardName"
            @browse-name="browseCardName"
          />
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

        <p v-if="addError" class="deck-add-card-modal-status error">{{ addError }}</p>
      </div>
    </div>
  </div>
  </Teleport>
</template>
