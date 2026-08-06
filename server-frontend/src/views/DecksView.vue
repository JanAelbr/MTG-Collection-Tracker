<script setup>
import "../styles/decks.css";
import { computed, nextTick, onActivated, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DeckGallery from "../components/DeckGallery.vue";
import CreateDeckModal from "../components/CreateDeckModal.vue";
import DeckPowerPanel from "../components/DeckPowerPanel.vue";
import DeckCardGrid from "../components/DeckCardGrid.vue";
import DeckCardStacks from "../components/DeckCardStacks.vue";
import DeckOverview from "../components/DeckOverview.vue";
import DeckSwapCardModal from "../components/DeckSwapCardModal.vue";
import DeckCsvImportModal from "../components/DeckCsvImportModal.vue";
import DeckCardQtyControl from "../components/DeckCardQtyControl.vue";
import DeckOwnedToggle from "../components/DeckOwnedToggle.vue";
import CardFinishBadge from "../components/CardFinishBadge.vue";
import CardSetSymbol from "../components/CardSetSymbol.vue";
import DeckCommanderPane from "../components/DeckCommanderPane.vue";
import DeckTypeIcon from "../components/DeckTypeIcon.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import ManaSymbols from "../components/ManaSymbols.vue";
import ManaCost from "../components/ManaCost.vue";
import CardPreview from "../components/CardPreview.vue";
import { api, clearClientCache } from "../api";
import { cacheKeyFor, getCachedEntry } from "../apiCache";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import {
  effectiveDeckOwnedQty,
  isDeckCardFullyOwned,
  mergeOwnershipPatchesIntoPages,
  ownershipRevision,
} from "../composables/cardContextMenu";
import {
  DECK_CARDS_VIEW_KEY,
  filterDecksForGallery,
  getStoredDeckCardsView,
  sortDecksForGallery,
} from "../utils/deckBrowse";
import { useDeckGalleryFilter } from "../composables/deckGalleryFilter";
import {
  buildDeckCardGroups,
  buildEmptyDeckCardGroups,
  cardTypeGroup,
  collectDeckCardTypes,
  commanderColorIdentity,
  deckTypeCounts,
  deckTypeIconType,
  deckTypeLabel,
  formatDeckGroupHeading,
  DECK_COLOR_ORDER,
  filterDeckCards,
  sortDeckCards,
  splitCommanderCards,
} from "../utils/deckCards";
import { cardFinish, cardRouteQuery } from "../utils/finishes";
import { formatCardRoles } from "../utils/deckPower";
import {
  formatEuro,
} from "../utils/format";

defineOptions({ name: "DecksView" });

const route = useRoute();
const router = useRouter();
const { deckGalleryFilter } = useDeckGalleryFilter();

const deckId = ref("");
const browseIndex = ref(null);
const deckCardsView = ref(getStoredDeckCardsView());
const deckTypeFilter = ref("all");
const deckOwnershipFilter = ref("all");
const deckColorFilters = ref([]);
const deckCardSort = ref("name");
const createDeckOpen = ref(false);
const csvImportOpen = ref(false);
const storagePickModal = ref({
  open: false,
  mode: "add",
  card: null,
  section: "main",
  cardType: "",
  typeLabel: "",
});
const refreshingUnpricedMetadata = ref(false);
const unpricedMetadataMessage = ref("");
const unpricedMetadataError = ref("");
const loadingDeckCards = ref(false);
const hasMounted = ref(false);

const { loading: loadingBrowse, run: runBrowseLoad } = useAsyncLoad();

const decks = computed(() => browseIndex.value?.decks || []);
const browsePages = computed(() => browseIndex.value?.pages || {});
const browseStats = computed(() => browsePages.value[String(deckId.value)] || null);
const activeBrowseDeck = computed(
  () => decks.value.find((deck) => String(deck.id) === String(deckId.value)) || null,
);

const commanderCards = computed(() => {
  const source = Array.isArray(browseStats.value?.cards)
    ? browseStats.value.cards
    : (browseStats.value?.previewCards || []);
  const { commanders } = splitCommanderCards(source);
  return sortDeckCards(commanders, "name");
});

const deckColorIdentity = computed(() => commanderColorIdentity(commanderCards.value));

const mainDeckCards = computed(() => {
  const { deckCards } = splitCommanderCards(browseStats.value?.cards || []);
  return deckCards;
});

const deckCardsReady = computed(() => Array.isArray(browseStats.value?.cards));

const isDeckEmpty = computed(() => {
  if (!deckCardsReady.value) {
    return Number(browseStats.value?.deckSize || 0) === 0;
  }
  return mainDeckCards.value.length === 0;
});

const showDeckCardsLoading = computed(() => (
  Boolean(deckId.value)
  && (loadingDeckCards.value || (!deckCardsReady.value && Number(browseStats.value?.deckSize || 0) > 0))
));

const filteredDeckCards = computed(() =>
  filterDeckCards(mainDeckCards.value, {
    typeFilter: deckTypeFilter.value,
    colorFilters: deckColorFilters.value,
    ownershipFilter: deckOwnershipFilter.value,
  }),
);

const filteredAllDeckCards = computed(() =>
  filterDeckCards(browseStats.value?.cards || [], {
    typeFilter: deckTypeFilter.value,
    colorFilters: deckColorFilters.value,
    ownershipFilter: deckOwnershipFilter.value,
  }),
);

const activeFilteredCards = computed(() => {
  if (deckCardsView.value === "stacks") {
    return filteredAllDeckCards.value;
  }
  if (deckCardsView.value === "overview") {
    return browseStats.value?.cards || [];
  }
  return filteredDeckCards.value;
});

const isFilterEmpty = computed(
  () => !isDeckEmpty.value && activeFilteredCards.value.length === 0,
);

const powerRefreshKey = computed(() =>
  (browseStats.value?.cards || [])
    .map((card) => `${card.cardName || card.name || ""}:${card.qty || 1}`)
    .join("|"),
);

const groupedBrowseCards = computed(() => {
  if (isDeckEmpty.value) {
    return buildEmptyDeckCardGroups();
  }
  return buildDeckCardGroups(filteredDeckCards.value, deckCardSort.value);
});

const groupedStackCards = computed(() => {
  if (!(browseStats.value?.cards || []).length) {
    return buildEmptyDeckCardGroups();
  }
  return buildDeckCardGroups(filteredAllDeckCards.value, deckCardSort.value);
});

const deckTypeFilterOptions = computed(() => collectDeckCardTypes(mainDeckCards.value));

const deckTypeCountByType = computed(() => deckTypeCounts(mainDeckCards.value));

function deckTypeFilterLabel(type) {
  const count = deckTypeCountByType.value.get(type) || 0;
  return `${deckTypeLabel(type)} (${count})`;
}

function openEmptyDeckAdd() {
  storagePickModal.value = {
    open: true,
    mode: "add",
    card: null,
    section: "main",
    cardType: "",
    typeLabel: "",
  };
}

function openTableTypeAdd(group) {
  storagePickModal.value = {
    open: true,
    mode: "add",
    card: null,
    section: group.section || "main",
    cardType: group.type || "",
    typeLabel: group.label || "",
  };
}

function closeStoragePickModal() {
  storagePickModal.value = {
    open: false,
    mode: "add",
    card: null,
    section: "main",
    cardType: "",
    typeLabel: "",
  };
}

function openCsvImport() {
  csvImportOpen.value = true;
}

function closeCsvImport() {
  csvImportOpen.value = false;
}

function openSwapModal(card) {
  if (!card || !deckId.value) {
    return;
  }
  storagePickModal.value = {
    open: true,
    mode: "swap",
    card,
    section: String(card.section || "main").trim().toLowerCase() || "main",
    cardType: "",
    typeLabel: "",
  };
}

async function onDeckCardSwapped(result) {
  closeStoragePickModal();
  await refreshDeckPage(result?.deckId || deckId.value);
}

function toggleColorFilter(color) {
  if (deckColorFilters.value.includes(color)) {
    deckColorFilters.value = deckColorFilters.value.filter((item) => item !== color);
    return;
  }
  deckColorFilters.value = [...deckColorFilters.value, color];
}

function clearColorFilters() {
  deckColorFilters.value = [];
}

async function loadBrowseIndex() {
  await runBrowseLoad(async () => {
    browseIndex.value = await api.getDeckBrowseIndex();
    mergeOwnershipPatchesIntoPages(browseIndex.value?.pages);
  });
}

function browseIndexCacheFresh() {
  return Boolean(getCachedEntry(cacheKeyFor("GET", "/decks/browse-index")));
}

function deckPageHasFullCards(deckKey = deckId.value) {
  const page = browseIndex.value?.pages?.[String(deckKey)];
  return Array.isArray(page?.cards);
}

const deckCardsLoadPromises = new Map();

async function ensureActiveDeckCardsLoaded({ force = false } = {}) {
  const key = String(deckId.value || "");
  if (!key || !browseIndex.value) {
    return;
  }
  if (!force && deckPageHasFullCards(key)) {
    return;
  }
  if (!force && deckCardsLoadPromises.has(key)) {
    return deckCardsLoadPromises.get(key);
  }
  loadingDeckCards.value = true;
  const promise = refreshDeckPage(key).finally(() => {
    deckCardsLoadPromises.delete(key);
    if (String(deckId.value) === key) {
      loadingDeckCards.value = false;
    }
  });
  deckCardsLoadPromises.set(key, promise);
  await promise;
}

function restoreScrollPosition(scrollY) {
  if (scrollY == null) {
    return;
  }
  nextTick(() => {
    requestAnimationFrame(() => {
      window.scrollTo(0, scrollY);
    });
  });
}

function applyDeckPageStats(deckKey, stats, { preserveScroll = true } = {}) {
  if (!browseIndex.value || !stats) {
    return;
  }
  const scrollY = preserveScroll ? window.scrollY : null;
  browseIndex.value = {
    ...browseIndex.value,
    pages: {
      ...browseIndex.value.pages,
      [String(deckKey)]: stats,
    },
  };
  mergeOwnershipPatchesIntoPages(browseIndex.value.pages);
  restoreScrollPosition(scrollY);
}

function patchDeckFromMutation(result) {
  if (!result?.card || !browseIndex.value?.pages) {
    return;
  }
  const deckKey = String(result.deckId || deckId.value);
  const page = browseIndex.value.pages[deckKey];
  if (!page?.cards) {
    return;
  }

  const matchesCard = (card) =>
    card.setCode === result.card.setCode
    && String(card.collectorNumber) === String(result.card.collectorNumber)
    && cardFinish(card) === cardFinish(result.card)
    && (!result.section || card.section === result.section);

  let cards = page.cards;
  if (result.removed || result.qty === 0) {
    cards = cards.filter((card) => !matchesCard(card));
  } else {
    const index = cards.findIndex(matchesCard);
    if (index >= 0) {
      cards = cards.map((card, cardIndex) => (
        cardIndex === index
          ? {
              ...card,
              qty: result.qty,
              ownedQty: result.ownedQty ?? card.ownedQty,
            }
          : card
      ));
    }
  }

  const deckSize = cards.reduce((sum, card) => sum + (Number(card.qty) || 0), 0);
  const ownedQty = cards.reduce((sum, card) => sum + (Number(card.ownedQty) || 0), 0);
  applyDeckPageStats(deckKey, {
    ...page,
    cards,
    deckSize,
    ownedQty,
    missingQty: Math.max(deckSize - ownedQty, 0),
    ownedCoverage: deckSize ? Math.round((ownedQty / deckSize) * 1000) / 10 : page.ownedCoverage,
  });
}

async function refreshDeckPage(deckKey = deckId.value) {
  if (!deckKey || !browseIndex.value) {
    return;
  }
  try {
    const payload = await api.getDeckBrowse(deckKey);
    applyDeckPageStats(deckKey, payload.stats);
  } catch {
    // Keep optimistic/local state if the silent refresh fails.
  }
}

async function onDeckCardAdded() {
  closeStoragePickModal();
  await refreshDeckPage();
}

function onDeckCardRemoved(result) {
  patchDeckFromMutation(result);
  void refreshDeckPage(result?.deckId);
}

function onDeckCardChanged(result) {
  patchDeckFromMutation(result);
  void refreshDeckPage(result?.deckId);
}

async function onDeckRenamed(updatedDeck) {
  if (updatedDeck && browseIndex.value?.decks) {
    browseIndex.value = {
      ...browseIndex.value,
      decks: browseIndex.value.decks.map((deck) =>
        String(deck.id) === String(updatedDeck.id) ? { ...deck, ...updatedDeck } : deck,
      ),
    };
  }
}

async function onDeckFavorited(updatedDeck) {
  if (updatedDeck && browseIndex.value?.decks) {
    browseIndex.value = {
      ...browseIndex.value,
      decks: browseIndex.value.decks.map((deck) =>
        String(deck.id) === String(updatedDeck.id) ? { ...deck, ...updatedDeck } : deck,
      ),
    };
  }
}

async function onDeckDeleted(deletedDeckId) {
  const deletedKey = String(deletedDeckId);
  if (browseIndex.value) {
    const pages = { ...(browseIndex.value.pages || {}) };
    delete pages[deletedKey];
    browseIndex.value = {
      ...browseIndex.value,
      decks: (browseIndex.value.decks || []).filter(
        (deck) => String(deck.id) !== deletedKey,
      ),
      pages,
    };
  }
  if (String(deckId.value) === deletedKey) {
    const remaining = visibleGalleryDecks().filter(
      (deck) => String(deck.id) !== deletedKey,
    );
    if (remaining.length) {
      selectBrowseDeck(String(remaining[0].id));
    } else {
      deckId.value = "";
      syncDeckRoute();
    }
  }
}

function openCreateDeck() {
  createDeckOpen.value = true;
}

async function onDeckCreated(deck) {
  if (!deck?.id) {
    await loadBrowseIndex();
    return;
  }
  try {
    const payload = await api.getDeckBrowse(deck.id);
    const existingDecks = browseIndex.value?.decks || [];
    const hasDeck = existingDecks.some((item) => String(item.id) === String(deck.id));
    browseIndex.value = {
      ...(browseIndex.value || {}),
      decks: hasDeck ? existingDecks : [...existingDecks, payload.deck || deck],
      pages: {
        ...(browseIndex.value?.pages || {}),
        [String(deck.id)]: payload.stats,
      },
    };
    mergeOwnershipPatchesIntoPages(browseIndex.value.pages);
  } catch {
    await loadBrowseIndex();
  }
  selectBrowseDeck(String(deck.id));
}

function cardRoute(card) {
  if (!card.setCode || !card.collectorNumber) {
    return null;
  }
  const query = cardRouteQuery(cardFinish(card));
  if (deckId.value) {
    query.deck = deckId.value;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query,
  };
}

async function refreshUnpricedMetadata() {
  if (!deckId.value || refreshingUnpricedMetadata.value) {
    return;
  }
  unpricedMetadataMessage.value = "";
  unpricedMetadataError.value = "";
  refreshingUnpricedMetadata.value = true;
  try {
    const result = await api.refreshDeckUnpricedMetadata(deckId.value);
    clearClientCache();
    unpricedMetadataMessage.value = result.message || "Set metadata refreshed.";
    await Promise.all([loadBrowseIndex(), refreshDeckPage()]);
    await ensureActiveDeckCardsLoaded({ force: true });
  } catch (error) {
    unpricedMetadataError.value = error?.message || "Could not refresh set metadata.";
  } finally {
    refreshingUnpricedMetadata.value = false;
  }
}

watch(deckId, () => {
  unpricedMetadataMessage.value = "";
  unpricedMetadataError.value = "";
});

function isOnDecksRoute() {
  return route.name === "decks" || route.path.startsWith("/collection/decks");
}

function visibleGalleryDecks() {
  return filterDecksForGallery(
    sortDecksForGallery(decks.value, browsePages.value),
    browsePages.value,
    deckGalleryFilter.value,
  );
}

function firstGalleryDeckId() {
  const visible = visibleGalleryDecks();
  return visible.length ? String(visible[0].id) : "";
}

function syncDeckIdFromRoute() {
  const requested = typeof route.query.deck === "string" ? route.query.deck.trim() : "";
  const visible = visibleGalleryDecks();
  if (requested && visible.some((deck) => String(deck.id) === requested)) {
    deckId.value = requested;
    return;
  }
  const nextId = firstGalleryDeckId();
  if (nextId) {
    deckId.value = nextId;
  } else {
    deckId.value = "";
  }
}

function ensureVisibleDeckSelected() {
  if (!browseIndex.value) {
    return;
  }
  const visible = visibleGalleryDecks();
  if (!visible.length) {
    if (deckId.value) {
      deckId.value = "";
      syncDeckRoute();
    }
    return;
  }
  if (!visible.some((deck) => String(deck.id) === String(deckId.value))) {
    selectBrowseDeck(String(visible[0].id));
  }
}

function syncDeckRoute() {
  // DecksView is KeepAlive'd: never rewrite the URL while another page is active.
  // Otherwise leaving /collection/decks?deck=<non-first> clears ?deck, the route watcher falls
  // back to the first gallery deck, and this replace hijacks the navigation.
  if (!isOnDecksRoute()) {
    return;
  }
  const desiredDeck = deckId.value ? String(deckId.value) : "";
  const currentDeck = typeof route.query.deck === "string" ? route.query.deck : "";
  if (currentDeck === desiredDeck) {
    return;
  }
  router.replace({
    path: "/collection/decks",
    query: desiredDeck ? { deck: desiredDeck } : {},
  });
}

function selectBrowseDeck(nextDeckId) {
  const changed = String(nextDeckId) !== String(deckId.value);
  deckId.value = nextDeckId;
  deckTypeFilter.value = "all";
  deckColorFilters.value = [];
  syncDeckRoute();
  if (changed) {
    void ensureActiveDeckCardsLoaded();
  }
}

function changeDeckCardsView(nextView) {
  deckCardsView.value = nextView;
  localStorage.setItem(DECK_CARDS_VIEW_KEY, nextView);
}

function deckCardOwnershipClass(card) {
  ownershipRevision.value;
  const qty = Number(card?.qty) || 0;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (isDeckCardFullyOwned(card)) {
    return "is-owned";
  }
  if (ownedQty > 0 && ownedQty < qty) {
    return "is-partial";
  }
  return "is-missing";
}

watch(deckTypeFilterOptions, (options) => {
  if (deckTypeFilter.value !== "all" && !options.includes(deckTypeFilter.value)) {
    deckTypeFilter.value = "all";
  }
});

watch(deckId, () => {
  syncDeckRoute();
});

watch(
  () => route.query.deck,
  () => {
    if (!isOnDecksRoute()) {
      return;
    }
    syncDeckIdFromRoute();
    if (deckId.value && !route.query.deck) {
      syncDeckRoute();
    }
  },
);

watch(deckId, () => {
  void ensureActiveDeckCardsLoaded();
});

watch(ownershipRevision, () => {
  mergeOwnershipPatchesIntoPages(browseIndex.value?.pages);
});

watch(
  [deckGalleryFilter, decks, () => browseIndex.value?.pages],
  () => {
    if (!isOnDecksRoute() || !hasMounted.value) {
      return;
    }
    ensureVisibleDeckSelected();
  },
);

onMounted(async () => {
  await loadBrowseIndex();
  syncDeckIdFromRoute();
  if (deckId.value && !route.query.deck) {
    syncDeckRoute();
  }
  await ensureActiveDeckCardsLoaded();
  hasMounted.value = true;
});

onActivated(async () => {
  if (!hasMounted.value) {
    return;
  }
  if (!browseIndex.value) {
    await loadBrowseIndex();
    if (isOnDecksRoute()) {
      syncDeckIdFromRoute();
      if (deckId.value && !route.query.deck) {
        syncDeckRoute();
      }
    }
    await ensureActiveDeckCardsLoaded();
    return;
  }
  if (!browseIndexCacheFresh()) {
    await loadBrowseIndex();
  }
  if (isOnDecksRoute()) {
    syncDeckIdFromRoute();
    if (deckId.value && !route.query.deck) {
      syncDeckRoute();
    }
  }
  await ensureActiveDeckCardsLoaded();
});
</script>

<template>
  <div class="decks-page">
    <div v-if="loadingBrowse && !browseIndex" class="storage-empty">
      <LoadingIndicator label="Loading decks…" />
    </div>

    <template v-else-if="browseIndex">
      <div class="deck-gallery-wrap">
        <GalleryLoadingOverlay
          :loading="loadingBrowse && !!browseIndex"
          label="Refreshing decks…"
        >
          <DeckGallery
            :decks="decks"
            :pages="browsePages"
            :active-deck-id="deckId"
            :on-renamed="onDeckRenamed"
            :on-deleted="onDeckDeleted"
            :on-favorited="onDeckFavorited"
            @select="selectBrowseDeck"
            @create="openCreateDeck"
            @build="router.push('/decks/build')"
          />
        </GalleryLoadingOverlay>
      </div>

      <div
        v-if="browseStats && activeBrowseDeck"
        class="deck-detail"
      >
        <section class="table-panel deck-cards-panel">
          <div class="deck-cards-sticky">
            <div class="deck-cards-sticky-head deck-cards-sticky-head--actions-only">
              <div class="deck-cards-sticky-actions">
                <div class="button-group deck-cards-view-group">
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: deckCardsView === 'overview' }"
                  @click="changeDeckCardsView('overview')"
                >
                  Overview
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: deckCardsView === 'images' }"
                  @click="changeDeckCardsView('images')"
                >
                  Images
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: deckCardsView === 'stacks' }"
                  @click="changeDeckCardsView('stacks')"
                >
                  Stacks
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: deckCardsView === 'table' }"
                  @click="changeDeckCardsView('table')"
                >
                  Table
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: deckCardsView === 'power' }"
                  @click="changeDeckCardsView('power')"
                >
                  Power
                </button>
              </div>
              <button
                type="button"
                class="btn btn-secondary btn-small deck-csv-import-trigger"
                @click="openCsvImport"
              >
                Quick import
              </button>
              <button
                type="button"
                class="btn btn-secondary btn-small"
                @click="router.push({ path: '/decks/build', query: { deck: String(deckId), mode: 'improve' } })"
              >
                Improve deck
              </button>
              <button
                type="button"
                class="btn btn-secondary btn-small"
                @click="router.push({ path: '/decks/build', query: { deck: String(deckId), mode: 'rebuild' } })"
              >
                Rebuild deck
              </button>
              </div>
            </div>

            <div
              v-if="deckCardsView !== 'power' && deckCardsView !== 'overview'"
              class="deck-cards-toolbar-compact"
            >
              <label class="manager-filter deck-cards-type-filter">
                <span class="deck-cards-filter-label">Type</span>
                <select :value="deckTypeFilter" @change="deckTypeFilter = $event.target.value">
                  <option value="all">All types</option>
                  <option
                    v-for="type in deckTypeFilterOptions"
                    :key="type"
                    :value="type"
                  >
                    {{ deckTypeFilterLabel(type) }}
                  </option>
                </select>
              </label>

              <div class="deck-cards-filter-group-compact">
                <span class="deck-cards-filter-label">Color</span>
                <div class="button-group deck-cards-filter-group deck-color-filter-group">
                  <button
                    v-for="color in DECK_COLOR_ORDER"
                    :key="color"
                    type="button"
                    class="filter-button deck-color-filter"
                    :class="{ active: deckColorFilters.includes(color) }"
                    :title="color === 'C' ? 'Colorless' : color"
                    @click="toggleColorFilter(color)"
                  >
                    <ManaSymbols :colors="color === 'C' ? [] : [color]" :size="18" />
                  </button>
                  <button
                    v-if="deckColorFilters.length"
                    type="button"
                    class="filter-button"
                    @click="clearColorFilters"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <div class="deck-cards-filter-group-compact">
                <span class="deck-cards-filter-label">Ownership</span>
                <div class="button-group deck-cards-filter-group">
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckOwnershipFilter === 'all' }"
                    @click="deckOwnershipFilter = 'all'"
                  >
                    All
                  </button>
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckOwnershipFilter === 'missing' }"
                    @click="deckOwnershipFilter = 'missing'"
                  >
                    Missing
                  </button>
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckOwnershipFilter === 'owned' }"
                    @click="deckOwnershipFilter = 'owned'"
                  >
                    Owned
                  </button>
                </div>
              </div>

              <div class="deck-cards-filter-group-compact">
                <span class="deck-cards-filter-label">Sort</span>
                <div class="button-group deck-cards-filter-group">
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckCardSort === 'name' }"
                    @click="deckCardSort = 'name'"
                  >
                    Name
                  </button>
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckCardSort === 'type' }"
                    @click="deckCardSort = 'type'"
                  >
                    Type
                  </button>
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckCardSort === 'color' }"
                    @click="deckCardSort = 'color'"
                  >
                    Color
                  </button>
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckCardSort === 'value' }"
                    @click="deckCardSort = 'value'"
                  >
                    Value
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div
            class="deck-cards-layout"
            :class="{
              'has-commander': commanderCards.length && !['stacks', 'overview', 'power'].includes(deckCardsView),
              'is-stacks-view': deckCardsView === 'stacks',
              'is-overview-view': deckCardsView === 'overview',
              'is-power-view': deckCardsView === 'power',
            }"
          >
              <div v-if="showDeckCardsLoading" class="storage-empty deck-cards-loading">
                <LoadingIndicator label="Loading deck cards…" />
              </div>
              <template v-else>
              <DeckCommanderPane
                v-if="!['stacks', 'overview', 'power'].includes(deckCardsView)"
                :cards="commanderCards"
                :default-deck-id="deckId"
                :show-deck-remove="true"
                :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
                @deck-removed="onDeckCardRemoved"
                @deck-changed="onDeckCardChanged"
              />

              <div class="deck-cards-main-pane">
                <p v-if="isFilterEmpty" class="storage-empty deck-cards-filter-empty">
                  No other cards match the current filters.
                </p>

                <DeckCardGrid
                  v-else-if="deckCardsView === 'images'"
                  :groups="groupedBrowseCards"
                  :default-deck-id="deckId"
                  :show-deck-remove="true"
                  :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
                  :color-identity="deckColorIdentity"
                  @deck-added="onDeckCardAdded"
                  @deck-removed="onDeckCardRemoved"
                  @deck-changed="onDeckCardChanged"
                />

                <DeckOverview
                  v-else-if="deckCardsView === 'overview'"
                  :cards="browseStats?.cards || []"
                  :stats="browseStats"
                  :deck-id="deckId"
                  :refresh-key="powerRefreshKey"
                  :refreshing-unpriced="refreshingUnpricedMetadata"
                  :unpriced-message="unpricedMetadataMessage"
                  :unpriced-error="unpricedMetadataError"
                  @refresh-unpriced="refreshUnpricedMetadata"
                />

                <DeckCardStacks
                  v-else-if="deckCardsView === 'stacks'"
                  :groups="groupedStackCards"
                  :default-deck-id="deckId"
                  :show-deck-remove="true"
                  :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
                  :color-identity="deckColorIdentity"
                  @deck-added="onDeckCardAdded"
                  @deck-removed="onDeckCardRemoved"
                  @deck-changed="onDeckCardChanged"
                />

                <DeckPowerPanel
                  v-else-if="deckCardsView === 'power'"
                  :deck-id="deckId"
                  :refresh-key="powerRefreshKey"
                  class="deck-power-panel--tab"
                />

                <table v-else-if="deckCardsView === 'table'" class="reports-table deck-cards-table">
                  <thead>
                    <tr>
                      <th>Mana</th>
                      <th>In deck</th>
                      <th>Card</th>
                      <th>Type</th>
                      <th>Role</th>
                      <th>Value</th>
                      <th>Owned</th>
                    </tr>
                  </thead>
                  <tbody v-if="isDeckEmpty">
                    <tr class="deck-cards-empty-row">
                      <td colspan="7">
                        <p class="storage-empty deck-cards-empty-message">This deck is empty.</p>
                        <button
                          type="button"
                          class="btn btn-primary btn-small"
                          @click="openEmptyDeckAdd"
                        >
                          Add cards
                        </button>
                      </td>
                    </tr>
                  </tbody>
                  <tbody v-else>
                    <template v-for="group in groupedBrowseCards" :key="group.key">
                      <tr
                        v-if="group.kind === 'section' && !group.cards?.length"
                        class="deck-cards-group-row deck-cards-section-row"
                      >
                        <td colspan="7">
                          <div class="deck-cards-group-heading">
                            <DeckTypeIcon :type="deckTypeIconType(group)" />
                            <span>{{ formatDeckGroupHeading(group) }}</span>
                          </div>
                        </td>
                      </tr>
                      <template v-else-if="group.cards?.length">
                        <tr
                          class="deck-cards-group-row"
                          :class="{ 'deck-cards-type-group-row': group.kind === 'type' }"
                        >
                          <td colspan="7">
                            <div class="deck-cards-group-heading">
                              <DeckTypeIcon :type="deckTypeIconType(group)" />
                              <span>{{ formatDeckGroupHeading(group) }}</span>
                              <button
                                v-if="group.kind === 'type' && deckId"
                                type="button"
                                class="deck-cards-group-add"
                                :title="`Add ${group.label.toLowerCase()} to deck`"
                                @click="openTableTypeAdd(group)"
                              >
                                +
                              </button>
                            </div>
                          </td>
                        </tr>
                        <tr
                          v-for="card in group.cards"
                          :key="`${group.key}-${card.section}-${card.cardName}-${card.setCode}-${card.collectorNumber}`"
                          class="deck-cards-row"
                          :class="deckCardOwnershipClass(card)"
                        >
                          <td><ManaCost :mana-cost="card.manaCost || ''" :size="18" /></td>
                          <td class="deck-cards-qty-cell">
                            <div class="deck-cards-qty-actions">
                              <DeckCardQtyControl
                                :card="card"
                                :deck-id="deckId"
                                :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
                                compact
                                inline
                                @changed="onDeckCardChanged"
                                @removed="onDeckCardRemoved"
                              />
                              <button
                                type="button"
                                class="deck-card-swap-btn"
                                aria-label="Swap card from storage"
                                title="Swap with owned card from storage"
                                @click.stop="openSwapModal(card)"
                              >
                                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                                  <path
                                    d="M6.99 11L3 15l3.99 4v-3H14v-2H6.99v-3zM21 9l-3.99-4v3H10v2h7.01v3L21 9z"
                                    fill="currentColor"
                                  />
                                </svg>
                              </button>
                            </div>
                          </td>
                          <td>
                            <CardPreview
                              :image-uri="card.imageUri"
                              :image-uri-back="card.imageUriBack || ''"
                            >
                              <span class="deck-cards-name-row">
                                <CardSetSymbol
                                  v-if="card.setCode"
                                  :set-code="card.setCode"
                                  :family-root="card.familyRoot || ''"
                                  :rarity="card.rarity || ''"
                                />
                                <RouterLink
                                  v-if="cardRoute(card)"
                                  :to="cardRoute(card)"
                                  class="reports-card-link"
                                >
                                  {{ card.cardName }}
                                </RouterLink>
                                <span v-else>{{ card.cardName }}</span>
                              </span>
                            </CardPreview>
                            <CardFinishBadge :card="card" compact />
                            <span
                              v-if="card.cheapestOwnedAlternative"
                              class="deck-cheapest-alternative"
                              :title="`Cheapest owned: ${card.cheapestOwnedAlternative.setCode} #${card.cheapestOwnedAlternative.collectorNumber} (${formatEuro(card.cheapestOwnedAlternative.currentValue)})`"
                            >
                              ·
                              <RouterLink
                                :to="{
                                  name: 'card',
                                  params: {
                                    setCode: card.cheapestOwnedAlternative.setCode,
                                    collectorNumber: card.cheapestOwnedAlternative.collectorNumber,
                                  },
                                  query: cardRouteQuery(card.cheapestOwnedAlternative.finish),
                                }"
                                class="reports-card-link"
                              >
                                {{ card.cheapestOwnedAlternative.setCode }}
                                #{{ card.cheapestOwnedAlternative.collectorNumber }}
                              </RouterLink>
                            </span>
                          </td>
                          <td class="deck-type-label">
                            <DeckTypeIcon :type="cardTypeGroup(card)" />
                            <span>{{ deckTypeLabel(cardTypeGroup(card)) }}</span>
                          </td>
                          <td class="deck-roles-cell">
                            <template v-if="formatCardRoles(card.roles).length">
                              <span
                                v-for="label in formatCardRoles(card.roles)"
                                :key="`${card.cardName}-${label}`"
                                class="deck-role-chip"
                              >{{ label }}</span>
                            </template>
                            <span v-else class="deck-roles-empty">—</span>
                          </td>
                          <td>{{ formatEuro(card.currentValue) }}</td>
                          <td class="manager-checkbox-cell deck-owned-cell">
                            <DeckOwnedToggle
                              :card="card"
                              :deck-id="deckId"
                              inline
                              @changed="onDeckCardChanged"
                            />
                          </td>
                        </tr>
                      </template>
                    </template>
                  </tbody>
                </table>
              </div>
              </template>
            </div>
        </section>
      </div>
    </template>

    <DeckSwapCardModal
      v-if="deckId"
      :open="storagePickModal.open"
      :mode="storagePickModal.mode"
      :deck-id="deckId"
      :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
      :card="storagePickModal.card"
      :section="storagePickModal.section"
      :card-type="storagePickModal.cardType"
      :type-label="storagePickModal.typeLabel"
      :color-identity="deckColorIdentity"
      @close="closeStoragePickModal"
      @added="onDeckCardAdded"
      @swapped="onDeckCardSwapped"
    />

    <DeckCsvImportModal
      v-if="deckId"
      :open="csvImportOpen"
      :deck-id="deckId"
      :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
      :deck-cards="browseStats?.cards || []"
      @close="closeCsvImport"
      @applied="onDeckCardAdded"
    />

    <CreateDeckModal
      :open="createDeckOpen"
      @close="createDeckOpen = false"
      @created="onDeckCreated"
    />
  </div>
</template>
