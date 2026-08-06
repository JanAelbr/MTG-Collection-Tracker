<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import BrowseSelect from "./BrowseSelect.vue";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import CollectionGalleryScaleControl from "./CollectionGalleryScaleControl.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import ManaSymbols from "./ManaSymbols.vue";
import StorageLocationSelect from "./StorageLocationSelect.vue";
import {
  fetchPricingSettings,
  savePricingSettings,
  usePricingSettings,
} from "../composables/pricingSettings";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { filterCollectionCards } from "../utils/collectionFilters";
import {
  defaultCollectionSortDir,
  sortCollectionCards,
} from "../utils/collectionSort";
import {
  cardTypeGroup,
  cardWithinColorIdentity,
  visibleColorPipsForIdentity,
} from "../utils/deckCards";
import { cardFinish } from "../utils/finishes";
import { setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import { mergeStorageCardPayloads } from "../utils/storageMerge";

const SORT_OPTIONS = [
  { id: "value", label: "Value" },
  { id: "name", label: "Name" },
  { id: "number", label: "Number" },
  { id: "set", label: "Set" },
  { id: "cmc", label: "CMC" },
  { id: "rarity", label: "Rarity" },
];

const props = defineProps({
  open: { type: Boolean, default: false },
  /** "add" picks an owned storage card into the deck; "swap" replaces an existing deck card. */
  mode: { type: String, default: "add" },
  deckId: { type: String, required: true },
  deckName: { type: String, default: "" },
  /** Outgoing deck card when mode is "swap". */
  card: { type: Object, default: null },
  section: { type: String, default: "main" },
  cardType: { type: String, default: "" },
  typeLabel: { type: String, default: "" },
  /** Commander color identity; null skips identity filtering. Empty array = colorless only. */
  colorIdentity: { type: Array, default: null },
});

const emit = defineEmits(["close", "added", "swapped"]);

const {
  settings: pricingSettings,
  collectionCardScale,
} = usePricingSettings();
const { loading, run } = useAsyncLoad();

const locations = ref([]);
const locationCards = ref([]);
const cardsLoaded = ref(false);
const setsCatalog = ref([]);
const searchQuery = ref("");
const setFilter = ref("");
const colorFilters = ref([]);
const colorMode = ref("includes");
const cardsSort = ref("name");
const cardsSortDir = ref(defaultCollectionSortDir("name"));
const destinationSlug = ref("");
const busy = ref(false);
const actionError = ref("");
const selectedKey = ref("");

const isSwapMode = computed(() => props.mode === "swap");

const outgoingName = computed(
  () => props.card?.cardName || props.card?.name || "card",
);

const targetLabel = computed(() => {
  if (props.typeLabel) {
    return props.typeLabel.toLowerCase();
  }
  if (props.cardType) {
    return props.cardType.toLowerCase();
  }
  return "card";
});

const modalTitle = computed(() => {
  if (isSwapMode.value) {
    if (props.deckName) {
      return `Swap ${outgoingName.value} in ${props.deckName}`;
    }
    return `Swap ${outgoingName.value}`;
  }
  if (props.deckName) {
    return `Add ${targetLabel.value} to ${props.deckName}`;
  }
  return `Add ${targetLabel.value} to deck`;
});

const modalSubtitle = computed(() => {
  if (isSwapMode.value) {
    return "Pick an owned card from storage. The current copy leaves the deck to the destination below.";
  }
  return "Pick an owned card from storage to add to the deck as owned.";
});

const visibleColorPips = computed(() =>
  visibleColorPipsForIdentity(props.colorIdentity),
);

const nonDeckLocations = computed(() =>
  (locations.value || []).filter((location) => {
    const type = String(location.locationType || "").toLowerCase();
    return type === "storage" || type === "binder";
  }),
);

const outgoingKey = computed(() => {
  if (!isSwapMode.value || !props.card) {
    return "";
  }
  return [
    String(props.card.setCode || "").toUpperCase(),
    String(props.card.collectorNumber || ""),
    String(cardFinish(props.card)),
  ].join("|");
});

const hasActiveFilter = computed(
  () =>
    Boolean(searchQuery.value.trim())
    || Boolean(setFilter.value)
    || colorFilters.value.length > 0,
);

const setCodesInPool = computed(() => {
  const codes = new Set();
  for (const card of locationCards.value) {
    if (card.setCode) {
      codes.add(String(card.setCode).toUpperCase());
    }
  }
  if (!codes.size) {
    for (const set of setsCatalog.value || []) {
      if (set.setCode) {
        codes.add(String(set.setCode).toUpperCase());
      }
    }
  }
  return [...codes].sort();
});

function setMetaForCode(code) {
  return (setsCatalog.value || []).find(
    (set) => String(set.setCode || "").toUpperCase() === String(code || "").toUpperCase(),
  );
}

const setFilterOptions = computed(() => {
  const options = [
    {
      value: "",
      label: "All sets",
      iconSrc: null,
      searchText: "all sets",
    },
  ];
  for (const code of setCodesInPool.value) {
    const set = setMetaForCode(code);
    const label = setShortName(set) || code;
    options.push({
      value: code,
      label,
      iconSrc: resolveSetIconUri(set),
      searchText: [code, label, set?.label].filter(Boolean).join(" "),
    });
  }
  return options;
});

const filteredCards = computed(() => {
  if (!hasActiveFilter.value) {
    return [];
  }
  const cards = filterCollectionCards(locationCards.value, {
    setCode: setFilter.value || "All",
    searchQuery: searchQuery.value,
    searchMode: "storage",
    colorFilters: colorFilters.value,
    colorMode: colorMode.value,
    ownedFilter: "all",
  });
  const type = String(props.cardType || "").trim();
  return cards.filter((card) => {
    if (type && cardTypeGroup(card) !== type) {
      return false;
    }
    if (!cardWithinColorIdentity(card, props.colorIdentity)) {
      return false;
    }
    const key = [
      String(card.setCode || "").toUpperCase(),
      String(card.collectorNumber || ""),
      String(cardFinish(card)),
    ].join("|");
    return key !== outgoingKey.value;
  });
});

const sortedCards = computed(() =>
  sortCollectionCards(filteredCards.value, {
    sort: cardsSort.value,
    dir: cardsSortDir.value,
    allowSet: true,
  }),
);

const matchSummaryText = computed(() => {
  if (!hasActiveFilter.value) {
    return "Search or filter to browse owned cards";
  }
  const n = sortedCards.value.length;
  const copies = sortedCards.value.reduce(
    (sum, card) => sum + (Number(card.copyCount) || 0),
    0,
  );
  if (!n) {
    return "No matching cards in storage";
  }
  return `${n} print${n === 1 ? "" : "s"} · ${copies} cop${copies === 1 ? "y" : "ies"}`;
});

function cardPickKey(card) {
  return `${card?.setCode || ""}|${card?.collectorNumber || ""}|${cardFinish(card)}`;
}

function pruneColorFiltersToVisible() {
  const allowed = new Set(visibleColorPips.value);
  colorFilters.value = colorFilters.value.filter((color) => allowed.has(color));
}

function toggleColorFilter(color) {
  if (!visibleColorPips.value.includes(color)) {
    return;
  }
  const next = new Set(colorFilters.value);
  if (next.has(color)) {
    next.delete(color);
  } else {
    next.add(color);
  }
  colorFilters.value = [...next];
}

function clearColorFilters() {
  colorFilters.value = [];
}

function setColorMode(mode) {
  colorMode.value = mode === "exact" ? "exact" : "includes";
}

function onSortChange(event) {
  const next = event.target.value;
  if (next === cardsSort.value) {
    return;
  }
  cardsSort.value = next;
  cardsSortDir.value = defaultCollectionSortDir(next);
}

function toggleSortDir() {
  cardsSortDir.value = cardsSortDir.value === "asc" ? "desc" : "asc";
}

async function onCardScaleChange(scale) {
  await savePricingSettings({ collectionCardScale: Number(scale) });
}

function resetState() {
  searchQuery.value = "";
  setFilter.value = "";
  colorFilters.value = [];
  colorMode.value = "includes";
  cardsSort.value = "name";
  cardsSortDir.value = defaultCollectionSortDir("name");
  busy.value = false;
  actionError.value = "";
  selectedKey.value = "";
  locationCards.value = [];
  cardsLoaded.value = false;
}

function resolveDefaultDestination(settings, locs) {
  const preferred = settings?.defaultStorageLocation;
  if (preferred && locs.some((location) => location.slug === preferred)) {
    return preferred;
  }
  const general = locs.find((location) => location.slug === "storage:general");
  if (general) {
    return general.slug;
  }
  return locs[0]?.slug || "storage:general";
}

async function loadSetup() {
  await run(async () => {
    const [locationsPayload, settings, meta] = await Promise.all([
      api.listStorageLocations(),
      fetchPricingSettings(),
      api.getReportsMeta().catch(() => null),
    ]);
    locations.value = locationsPayload?.locations || locationsPayload || [];
    setsCatalog.value = meta?.sets || [];
    const pool = nonDeckLocations.value;
    destinationSlug.value = resolveDefaultDestination(settings || pricingSettings.value, pool);
    pruneColorFiltersToVisible();
  });
}

async function ensureCardsLoaded() {
  if (cardsLoaded.value || !nonDeckLocations.value.length) {
    if (!nonDeckLocations.value.length) {
      cardsLoaded.value = true;
      locationCards.value = [];
    }
    return;
  }
  await run(async () => {
    const payloads = await Promise.all(
      nonDeckLocations.value.map((location) => api.getStorageLocationCards(location.slug)),
    );
    const merged = mergeStorageCardPayloads(payloads);
    locationCards.value = merged.cards || [];
    cardsLoaded.value = true;
  });
}

function closeModal() {
  resetState();
  emit("close");
}

async function addPickedCard(card) {
  const section = props.section || "main";
  const payload = {
    setCode: card.setCode,
    collectorNumber: card.collectorNumber,
    finish: cardFinish(card),
    section,
    qty: 1,
  };
  const added = await api.addCardToDeck(props.deckId, payload);
  const owned = await api.setDeckCardOwned(props.deckId, {
    setCode: card.setCode,
    collectorNumber: card.collectorNumber,
    finish: cardFinish(card),
    section,
    owned: true,
  });
  return {
    ...added,
    ownedQty: owned.ownedQty ?? added.ownedQty,
    claimedToDeck: owned.claimedToDeck,
  };
}

async function swapPickedCard(card) {
  return api.swapDeckCard(props.deckId, {
    remove: {
      setCode: props.card.setCode,
      collectorNumber: props.card.collectorNumber,
      finish: cardFinish(props.card),
      section: props.section || props.card.section || "main",
      qty: 1,
    },
    add: {
      setCode: card.setCode,
      collectorNumber: card.collectorNumber,
      finish: cardFinish(card),
    },
    destinationStorageLocation: destinationSlug.value || undefined,
  });
}

async function onPickCard(card) {
  if (!card || busy.value || !props.deckId) {
    return;
  }
  if (isSwapMode.value && !props.card) {
    return;
  }
  selectedKey.value = cardPickKey(card);
  busy.value = true;
  actionError.value = "";
  try {
    if (isSwapMode.value) {
      const result = await swapPickedCard(card);
      clearClientCache();
      emit("swapped", result);
    } else {
      const result = await addPickedCard(card);
      clearClientCache();
      emit("added", result);
    }
    closeModal();
  } catch (error) {
    actionError.value = error.message
      || (isSwapMode.value ? "Could not swap card." : "Could not add card.");
  } finally {
    busy.value = false;
  }
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
    await loadSetup();
  },
);

watch(
  hasActiveFilter,
  async (active) => {
    if (active && props.open) {
      await ensureCardsLoaded();
    }
  },
);

watch(
  () => props.colorIdentity,
  () => {
    pruneColorFiltersToVisible();
  },
);

onUnmounted(() => {
  document.body.style.overflow = "";
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop deck-add-card-modal-backdrop deck-swap-card-modal-backdrop"
      @click.self="closeModal"
    >
      <div
        class="modal-card deck-add-card-modal deck-swap-card-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="deck-storage-pick-title"
      >
        <header class="deck-add-card-modal-head">
          <div>
            <h3 id="deck-storage-pick-title">{{ modalTitle }}</h3>
            <p class="deck-add-card-modal-subtitle">{{ modalSubtitle }}</p>
          </div>
          <button type="button" class="btn btn-secondary btn-small" @click="closeModal">
            Close
          </button>
        </header>

        <div class="deck-swap-card-toolbar storage-detail-toolbar">
          <div class="storage-toolbar-row deck-swap-card-toolbar-row">
            <label class="storage-toolbar-search">
              <span class="visually-hidden">Search storage</span>
              <input
                v-model="searchQuery"
                type="search"
                placeholder="Words AND · punctuation flexible…"
                autocomplete="off"
              >
            </label>

            <BrowseSelect
              v-model="setFilter"
              class="storage-toolbar-set-select"
              :options="setFilterOptions"
              filterable
              show-icons
              optional-icons
              hide-arrows
              empty-icon-label="All"
              placeholder="All sets"
              aria-label="Filter by set"
              portal-panel
            />

            <div class="storage-color-filter" role="group" aria-label="Color identity">
              <div class="storage-color-filter-pips">
                <button
                  v-for="color in visibleColorPips"
                  :key="color"
                  type="button"
                  class="storage-color-filter-btn"
                  :class="{ active: colorFilters.includes(color) }"
                  :title="color === 'C' ? 'Colorless' : color"
                  :aria-pressed="colorFilters.includes(color) ? 'true' : 'false'"
                  @click="toggleColorFilter(color)"
                >
                  <ManaSymbols :colors="color === 'C' ? [] : [color]" :size="14" />
                </button>
              </div>
              <button
                v-if="colorFilters.length"
                type="button"
                class="storage-color-filter-clear"
                title="Clear color filters"
                aria-label="Clear color filters"
                @click="clearColorFilters"
              >
                ×
              </button>
              <label class="storage-color-mode-toggle" title="Exact color identity only">
                <input
                  type="checkbox"
                  :checked="colorMode === 'exact'"
                  @change="setColorMode($event.target.checked ? 'exact' : 'includes')"
                >
                <span>Exact</span>
              </label>
            </div>

            <div class="storage-sort-row">
              <label class="visually-hidden" for="deck-storage-pick-sort">Sort by</label>
              <select id="deck-storage-pick-sort" :value="cardsSort" @change="onSortChange">
                <option
                  v-for="option in SORT_OPTIONS"
                  :key="option.id"
                  :value="option.id"
                >
                  {{ option.label }}
                </option>
              </select>
              <button
                type="button"
                class="btn btn-secondary collection-sort-dir"
                :title="cardsSortDir === 'asc' ? 'Ascending' : 'Descending'"
                @click="toggleSortDir"
              >
                {{ cardsSortDir === "asc" ? "↑" : "↓" }}
              </button>
            </div>

            <CollectionGalleryScaleControl
              class="collection-gallery-toolbar-scale"
              :model-value="collectionCardScale"
              :options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150, 175, 200, 225, 250]"
              @update:model-value="onCardScaleChange"
            />

            <label v-if="isSwapMode" class="deck-swap-destination">
              <span>Move out to</span>
              <StorageLocationSelect
                v-model="destinationSlug"
                :locations="nonDeckLocations"
                :include-types="['storage', 'binder']"
                compact
                aria-label="Destination storage for removed card"
              />
            </label>
          </div>
          <p class="storage-toolbar-summary">{{ matchSummaryText }}</p>
        </div>

        <div class="deck-add-card-modal-body collection-page">
          <p v-if="!hasActiveFilter" class="storage-empty">
            Search by name, set, or color to browse owned cards in storage.
          </p>

          <div v-else-if="loading && !sortedCards.length" class="storage-empty">
            <LoadingIndicator label="Loading storage cards…" />
          </div>

          <p v-else-if="!sortedCards.length" class="storage-empty">
            No matching cards in non-deck storage.
          </p>

          <div
            v-else
            class="table-panel cards-panel reports-cards-panel deck-add-card-modal-results"
          >
            <CollectionCardGrid
              :cards="sortedCards"
              :show-unowned-badge="false"
              :card-scale="collectionCardScale"
              pick-prints
              :selected-key="selectedKey"
              @pick-card="onPickCard"
            />
          </div>

          <p v-if="busy" class="deck-add-card-modal-status">
            {{ isSwapMode ? "Swapping…" : "Adding…" }}
          </p>
          <p v-else-if="actionError" class="deck-add-card-modal-status error">{{ actionError }}</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>
