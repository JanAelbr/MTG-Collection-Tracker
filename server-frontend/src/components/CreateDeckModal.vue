<script setup>
import { computed, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import SearchArtBrowser from "./SearchArtBrowser.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { cardFinish } from "../utils/finishes";

const PAGE_SIZE = 25;
const SEARCH_SET_CODE = "All";

const DECK_FORMATS = [
  { id: "commander", label: "Commander" },
];

const props = defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "created"]);

const deckFormat = ref("commander");
const deckName = ref("");
const nameTouched = ref(false);
const selectedCommanders = ref([]);
const searchInput = ref("");
const searchQuery = ref("");
const resultsPayload = ref(null);
const artExplorer = ref(null);
const artSelectedIndex = ref(0);
const selectedCardName = ref("");
const createError = ref("");
const creating = ref(false);
const { loading, run } = useAsyncLoad();

let debounceTimer = null;

const canCreate = computed(() => {
  if (creating.value) {
    return false;
  }
  if (deckFormat.value === "commander" && selectedCommanders.value.length < 1) {
    return false;
  }
  return Boolean(deckName.value.trim());
});

function isCommanderCandidate(card) {
  const typeLine = String(card.typeLine || card.type_line || "").toLowerCase();
  return typeLine.includes("legendary");
}

function commanderKey(card) {
  return `${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`;
}

function resetState() {
  clearTimeout(debounceTimer);
  deckFormat.value = "commander";
  deckName.value = "";
  nameTouched.value = false;
  selectedCommanders.value = [];
  searchInput.value = "";
  searchQuery.value = "";
  resultsPayload.value = null;
  artExplorer.value = null;
  artSelectedIndex.value = 0;
  selectedCardName.value = "";
  createError.value = "";
  creating.value = false;
}

function closeModal() {
  resetState();
  emit("close");
}

function onNameInput() {
  nameTouched.value = true;
}

function syncDefaultName() {
  if (nameTouched.value || !selectedCommanders.value.length) {
    return;
  }
  const first = selectedCommanders.value[0];
  deckName.value = first.cardName || first.name || "";
}

function addCommander(card) {
  if (!card?.setCode || !card?.collectorNumber) {
    return;
  }
  if (!isCommanderCandidate(card)) {
    createError.value = "Pick a legendary card as commander.";
    return;
  }
  if (selectedCommanders.value.some((item) => commanderKey(item) === commanderKey(card))) {
    createError.value = "That commander is already selected.";
    return;
  }
  createError.value = "";
  selectedCommanders.value = [
    ...selectedCommanders.value,
    {
      ...card,
      cardName: card.cardName || card.name || "Unknown",
    },
  ];
  syncDefaultName();
}

function removeCommander(card) {
  selectedCommanders.value = selectedCommanders.value.filter(
    (item) => commanderKey(item) !== commanderKey(card),
  );
  syncDefaultName();
}

function commitSearch() {
  clearTimeout(debounceTimer);
  searchQuery.value = searchInput.value.trim();
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

function closeArtExplorer() {
  artExplorer.value = null;
  artSelectedIndex.value = 0;
  selectedCardName.value = "";
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
      ownedFilter: "all",
      foilFilter: "all",
      page: 1,
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

async function loadNameVariants(name) {
  const payload = await api.getSearchNameVariants({
    name,
    q: searchQuery.value.trim(),
    setCode: SEARCH_SET_CODE,
    ownedFilter: "all",
    foilFilter: "all",
  });
  const variants = (payload.variants || []).filter(isCommanderCandidate);
  if (!variants.length) {
    throw new Error("No legendary printings found for this card.");
  }
  artExplorer.value = { ...payload, variants };
  artSelectedIndex.value = 0;
  selectedCardName.value = name;
}

async function browseCardName(name) {
  createError.value = "";
  try {
    await loadNameVariants(name);
  } catch (error) {
    createError.value = error.message || "Could not load card variants.";
  }
}

const selectedVariant = computed(
  () => artExplorer.value?.variants?.[artSelectedIndex.value] || null,
);

async function addSelectedCommander() {
  const card = selectedVariant.value;
  if (!card) {
    return;
  }
  addCommander(card);
}

async function createDeck() {
  if (!canCreate.value) {
    return;
  }
  creating.value = true;
  createError.value = "";
  try {
    const result = await api.createDeck({
      format: deckFormat.value,
      name: deckName.value.trim(),
      commanders: selectedCommanders.value.map((card) => ({
        setCode: card.setCode,
        collectorNumber: card.collectorNumber,
        finish: cardFinish(card),
      })),
    });
    clearClientCache();
    emit("created", result.deck);
    closeModal();
  } catch (error) {
    createError.value = error.message || "Could not create deck.";
  } finally {
    creating.value = false;
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      resetState();
    }
  },
);
</script>

<template>
  <div
    v-if="open"
    class="modal-backdrop deck-create-modal-backdrop"
    @click.self="closeModal"
  >
    <form class="modal-card deck-create-modal" @submit.prevent="createDeck">
      <header class="deck-create-modal-head">
        <div>
          <h3>New deck</h3>
          <p class="deck-create-modal-subtitle">
            Choose a format, pick your commander(s), then name the deck.
          </p>
        </div>
        <button type="button" class="btn btn-secondary btn-small" @click="closeModal">
          Close
        </button>
      </header>

      <div class="deck-create-modal-body">
      <section class="deck-create-section">
        <h4 class="deck-create-section-title">Format</h4>
        <div class="button-group deck-create-format-group">
          <button
            v-for="format in DECK_FORMATS"
            :key="format.id"
            type="button"
            class="filter-button"
            :class="{ active: deckFormat === format.id }"
            @click="deckFormat = format.id"
          >
            {{ format.label }}
          </button>
        </div>
      </section>

      <section v-if="deckFormat === 'commander'" class="deck-create-section">
        <h4 class="deck-create-section-title">Commander</h4>
        <p class="deck-create-section-help">Search for legendary cards. You can add multiple commanders.</p>

        <div v-if="selectedCommanders.length" class="deck-create-commander-list">
          <figure
            v-for="card in selectedCommanders"
            :key="commanderKey(card)"
            class="deck-create-commander-chip"
          >
            <img
              v-if="card.imageUri"
              :src="card.imageUri"
              :alt="card.cardName"
              loading="lazy"
            />
            <figcaption>
              <span class="deck-create-commander-name">{{ card.cardName }}</span>
              <button
                type="button"
                class="deck-create-commander-remove"
                @click="removeCommander(card)"
              >
                Remove
              </button>
            </figcaption>
          </figure>
        </div>

        <div class="collection-search-input-row">
          <input
            v-model="searchInput"
            type="search"
            class="collection-search-input"
            placeholder="Search legendary commanders…"
            autocomplete="off"
            aria-label="Search commanders"
            @input="scheduleDebouncedSearch"
          />
          <button type="button" class="btn btn-primary" :disabled="loading" @click="commitSearch">
            Search
          </button>
        </div>

        <div v-if="loading" class="deck-create-loading">
          <LoadingIndicator label="Searching…" />
        </div>

        <div v-else-if="resultsPayload?.cards?.length" class="collection-page">
          <CollectionCardGrid
            :cards="resultsPayload.cards"
            browse-names
            :selected-name="selectedCardName"
            :card-scale="78"
            @browse-name="browseCardName"
          />
        </div>

        <SearchArtBrowser
          v-if="artExplorer && artExplorer.variants?.length"
          compact
          :name="artExplorer.name"
          :variants="artExplorer.variants"
          :selected-index="artSelectedIndex"
          :show-random="false"
          @update:selected-index="artSelectedIndex = $event"
          @close="closeArtExplorer"
        />

        <div v-if="selectedVariant" class="deck-create-add-commander-row">
          <button type="button" class="btn btn-primary" @click="addSelectedCommander">
            Add commander
          </button>
        </div>
      </section>

      <section v-if="selectedCommanders.length" class="deck-create-section">
        <h4 class="deck-create-section-title">Deck name</h4>
        <label class="deck-create-name-field">
          <span>Name</span>
          <input
            v-model="deckName"
            type="text"
            maxlength="120"
            required
            @input="onNameInput"
          />
        </label>
      </section>

      <p v-if="createError" class="deck-create-error">{{ createError }}</p>
      </div>

      <div class="modal-actions">
        <button type="button" class="btn btn-secondary" @click="closeModal">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" :disabled="!canCreate">
          {{ creating ? "Creating…" : "Create deck" }}
        </button>
      </div>
    </form>
  </div>
</template>
