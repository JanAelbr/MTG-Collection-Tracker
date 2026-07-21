<script setup>
import { computed, nextTick, onActivated, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DeckGallery from "../components/DeckGallery.vue";
import CreateDeckModal from "../components/CreateDeckModal.vue";
import DeckHero from "../components/DeckHero.vue";
import DeckPowerPanel from "../components/DeckPowerPanel.vue";
import DeckCardGrid from "../components/DeckCardGrid.vue";
import DeckCardStacks from "../components/DeckCardStacks.vue";
import DeckOverview from "../components/DeckOverview.vue";
import DeckAddCardModal from "../components/DeckAddCardModal.vue";
import DeckCsvImportModal from "../components/DeckCsvImportModal.vue";
import CardFinishBadge from "../components/CardFinishBadge.vue";
import DeckCommanderPane from "../components/DeckCommanderPane.vue";
import DeckTypeIcon from "../components/DeckTypeIcon.vue";
import CollectionSetLink from "../components/CollectionSetLink.vue";
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
  setOwnershipPatch,
} from "../composables/cardContextMenu";
import {
  DECK_CARDS_VIEW_KEY,
  GALLERY_SORT_KEY,
  getStoredDeckCardsView,
  getStoredGallerySort,
} from "../utils/deckBrowse";
import {
  buildDeckCardGroups,
  buildEmptyDeckCardGroups,
  cardTypeGroup,
  collectDeckCardTypes,
  deckTypeCounts,
  deckTypeIconType,
  deckTypeLabel,
  formatDeckGroupHeading,
  DECK_COLOR_ORDER,
  filterDeckCards,
  sortDeckCards,
  splitCommanderCards,
} from "../utils/deckCards";
import { cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import { formatCardRoles } from "../utils/deckPower";
import {
  formatEuro,
} from "../utils/format";

defineOptions({ name: "DecksView" });

const route = useRoute();
const router = useRouter();

const deckId = ref("");
const browseIndex = ref(null);
const gallerySort = ref(getStoredGallerySort());
const deckCardsView = ref(getStoredDeckCardsView());
const deckTypeFilter = ref("all");
const deckOwnershipFilter = ref("all");
const deckColorFilters = ref([]);
const deckCardSort = ref("name");
const deckDetailRef = ref(null);
const createDeckOpen = ref(false);
const emptyDeckAddOpen = ref(false);
const csvImportOpen = ref(false);
const ownedToggleBusy = ref("");
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

const unknownCards = computed(() => browseStats.value?.unknownCards || []);
const hasUnknownCards = computed(() => (browseStats.value?.unknownCount ?? 0) > 0);
const unpricedCardCount = computed(() => {
  const qty = Number(browseStats.value?.unknownQty);
  if (Number.isFinite(qty) && qty > 0) {
    return qty;
  }
  return Number(browseStats.value?.unknownCount) || 0;
});

const commanderCards = computed(() => {
  const source = Array.isArray(browseStats.value?.cards)
    ? browseStats.value.cards
    : (browseStats.value?.previewCards || []);
  const { commanders } = splitCommanderCards(source);
  return sortDeckCards(commanders, "name");
});

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
  emptyDeckAddOpen.value = true;
}

function closeEmptyDeckAdd() {
  emptyDeckAddOpen.value = false;
}

function openCsvImport() {
  csvImportOpen.value = true;
}

function closeCsvImport() {
  csvImportOpen.value = false;
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
  emptyDeckAddOpen.value = false;
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

function deckOwnedToggleKey(card) {
  return `${card.section}-${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`;
}

function deckCardCanMarkOwned(card) {
  return Boolean(card?.setCode && card?.collectorNumber != null && String(card.collectorNumber).trim());
}

async function toggleDeckOwned(card, owned) {
  if (!deckId.value || !deckCardCanMarkOwned(card)) {
    return;
  }
  const busyKey = deckOwnedToggleKey(card);
  ownedToggleBusy.value = busyKey;
  try {
    const result = await api.setDeckCardOwned(deckId.value, {
      setCode: card.setCode,
      collectorNumber: card.collectorNumber,
      finish: cardFinish(card),
      section: card.section || "main",
      owned,
    });
    setOwnershipPatch(
      card.setCode,
      card.collectorNumber,
      cardFinish(card),
      {
        owned: (result.ownedQty ?? 0) > 0,
        ownedCount: result.ownedQty ?? 0,
      },
    );
    patchDeckFromMutation(result);
    clearClientCache();
    void refreshDeckPage(result?.deckId);
  } catch (error) {
    window.alert(error?.message || "Could not update owned status.");
  } finally {
    if (ownedToggleBusy.value === busyKey) {
      ownedToggleBusy.value = "";
    }
  }
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
    const remaining = browseIndex.value?.decks || [];
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

function unknownCardRoute(card) {
  const setCode = card.setCode || card.set_code || "";
  const collectorNumber = String(card.collectorNumber ?? card.collector_number ?? "");
  if (!setCode || !collectorNumber) {
    return null;
  }
  return {
    name: "card",
    params: { setCode, collectorNumber },
    query: cardRouteQuery(card.finish ?? card.foil ?? 0),
  };
}

function unknownCardName(card) {
  return card.cardName || card.card_name || "Unknown";
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

function syncDeckIdFromRoute() {
  if (typeof route.query.deck === "string") {
    deckId.value = route.query.deck;
    return;
  }
  if (!deckId.value && decks.value.length) {
    deckId.value = String(decks.value[0].id);
  }
}

function syncDeckRoute() {
  router.replace({
    path: "/decks",
    query: deckId.value ? { deck: deckId.value } : {},
  });
}

function scrollDeckDetailIntoView() {
  nextTick(() => {
    deckDetailRef.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function scrollAfterDeckSwitch() {
  nextTick(() => {
    if (browseStats.value && deckDetailRef.value) {
      scrollDeckDetailIntoView();
      return;
    }
    const stop = watch(
      () => Boolean(browseStats.value && deckDetailRef.value),
      (ready) => {
        if (!ready) {
          return;
        }
        scrollDeckDetailIntoView();
        stop();
      },
      { flush: "post" },
    );
  });
}

function selectBrowseDeck(nextDeckId) {
  const changed = String(nextDeckId) !== String(deckId.value);
  deckId.value = nextDeckId;
  deckTypeFilter.value = "all";
  deckColorFilters.value = [];
  syncDeckRoute();
  if (changed) {
    scrollAfterDeckSwitch();
    void ensureActiveDeckCardsLoaded();
  }
}

function changeGallerySort(nextSort) {
  gallerySort.value = nextSort;
  localStorage.setItem(GALLERY_SORT_KEY, nextSort);
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

function deckCardOwnedLabel(card) {
  ownershipRevision.value;
  const qty = Number(card?.qty) || 0;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (isDeckCardFullyOwned(card)) {
    return "—";
  }
  if (ownedQty > 0 && ownedQty < qty) {
    return `${ownedQty} / ${card.qty}`;
  }
  return "—";
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
    syncDeckIdFromRoute();
  },
);

watch(deckId, () => {
  void ensureActiveDeckCardsLoaded();
});

watch(ownershipRevision, () => {
  mergeOwnershipPatchesIntoPages(browseIndex.value?.pages);
});

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
    syncDeckIdFromRoute();
    await ensureActiveDeckCardsLoaded();
    return;
  }
  if (!browseIndexCacheFresh()) {
    await loadBrowseIndex();
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
        <div class="deck-gallery-toolbar">
          <button type="button" class="btn btn-secondary btn-small" @click="openCreateDeck">
            New deck
          </button>
          <button type="button" class="btn btn-primary btn-small" @click="router.push('/decks/build')">
            Build deck
          </button>
          <span class="deck-gallery-toolbar-label">Sort by</span>
          <div class="button-group deck-gallery-sort-group">
            <button
              type="button"
              class="filter-button"
              :class="{ active: gallerySort === 'year' }"
              @click="changeGallerySort('year')"
            >
              Year
            </button>
            <button
              type="button"
              class="filter-button"
              :class="{ active: gallerySort === 'value' }"
              @click="changeGallerySort('value')"
            >
              Value
            </button>
          </div>
        </div>

        <GalleryLoadingOverlay
          :loading="loadingBrowse && !!browseIndex"
          label="Refreshing decks…"
        >
          <DeckGallery
            :decks="decks"
            :pages="browsePages"
            :active-deck-id="deckId"
            :sort-by="gallerySort"
            :on-renamed="onDeckRenamed"
            :on-deleted="onDeckDeleted"
            @select="selectBrowseDeck"
            @create="openCreateDeck"
          />
        </GalleryLoadingOverlay>
      </div>

      <div
        v-if="browseStats && activeBrowseDeck"
        ref="deckDetailRef"
        class="deck-detail"
      >
        <DeckHero :deck="activeBrowseDeck" :stats="browseStats" :deck-id="deckId" />

        <details
          v-if="hasUnknownCards"
          class="table-panel deck-unknown-panel"
          aria-label="Unpriced cards"
        >
          <summary class="deck-unknown-summary">
            <div class="deck-unknown-head">
              <h2>Unpriced cards ({{ unpricedCardCount }})</h2>
              <button
                type="button"
                class="btn btn-secondary btn-small"
                :disabled="refreshingUnpricedMetadata"
                @click.stop="refreshUnpricedMetadata"
              >
                {{ refreshingUnpricedMetadata ? "Refreshing…" : "Refresh set metadata" }}
              </button>
            </div>
          </summary>
          <p class="deck-unknown-intro">
            These deck cards have no current market price.
            Re-import Scryfall catalog data for the affected sets, then run a price sync if needed.
          </p>
          <p v-if="unpricedMetadataMessage" class="deck-unknown-status">{{ unpricedMetadataMessage }}</p>
          <p v-if="unpricedMetadataError" class="deck-unknown-status error">{{ unpricedMetadataError }}</p>
          <table class="reports-table deck-unknown-table">
            <thead>
              <tr>
                <th>Set</th>
                <th>#</th>
                <th>Name</th>
                <th>Qty</th>
                <th>Finish</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(card, index) in unknownCards"
                :key="`${card.set_code || card.setCode}-${card.collector_number || card.collectorNumber}-${index}`"
              >
                <td>
                  <CollectionSetLink
                    :set-code="card.setCode || card.set_code || ''"
                  />
                </td>
                <td>{{ card.collectorNumber ?? card.collector_number ?? "—" }}</td>
                <td>
                  <RouterLink
                    v-if="unknownCardRoute(card)"
                    :to="unknownCardRoute(card)"
                    class="reports-card-link"
                  >
                    {{ unknownCardName(card) }}
                  </RouterLink>
                  <span v-else>{{ unknownCardName(card) }}</span>
                </td>
                <td>{{ card.qty ?? 1 }}</td>
                <td>{{ finishLabel(card.finish ?? card.foil ?? 0) }}</td>
              </tr>
            </tbody>
          </table>
        </details>

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
                  @deck-added="onDeckCardAdded"
                  @deck-removed="onDeckCardRemoved"
                  @deck-changed="onDeckCardChanged"
                />

                <DeckOverview
                  v-else-if="deckCardsView === 'overview'"
                  :cards="browseStats?.cards || []"
                  :deck-id="deckId"
                  :refresh-key="powerRefreshKey"
                />

                <DeckCardStacks
                  v-else-if="deckCardsView === 'stacks'"
                  :groups="groupedStackCards"
                  :default-deck-id="deckId"
                  :show-deck-remove="true"
                  :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
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
                      <th>Qty</th>
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
                          <td class="deck-cards-qty">{{ card.qty }}</td>
                          <td>
                            <CardPreview
                              :image-uri="card.imageUri"
                              :image-uri-back="card.imageUriBack || ''"
                            >
                              <RouterLink
                                v-if="cardRoute(card)"
                                :to="cardRoute(card)"
                                class="reports-card-link"
                              >
                                {{ card.cardName }}
                              </RouterLink>
                              <span v-else>{{ card.cardName }}</span>
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
                            <template v-if="deckCardCanMarkOwned(card)">
                              <input
                                type="checkbox"
                                :checked="isDeckCardFullyOwned(card)"
                                :disabled="ownedToggleBusy === deckOwnedToggleKey(card)"
                                :aria-label="`Mark ${card.cardName} as owned in deck`"
                                @change="toggleDeckOwned(card, $event.target.checked)"
                              />
                              <span
                                v-if="!isDeckCardFullyOwned(card) && effectiveDeckOwnedQty(card) > 0"
                                class="deck-owned-partial"
                              >
                                {{ deckCardOwnedLabel(card) }}
                              </span>
                            </template>
                            <span v-else>{{ deckCardOwnedLabel(card) }}</span>
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

    <DeckAddCardModal
      v-if="deckId"
      :open="emptyDeckAddOpen"
      :deck-id="deckId"
      :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
      section="main"
      @close="closeEmptyDeckAdd"
      @added="onDeckCardAdded"
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
