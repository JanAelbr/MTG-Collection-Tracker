<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DeckGallery from "../components/DeckGallery.vue";
import CreateDeckModal from "../components/CreateDeckModal.vue";
import DeckHero from "../components/DeckHero.vue";
import DeckCardGrid from "../components/DeckCardGrid.vue";
import DeckCommanderPane from "../components/DeckCommanderPane.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import ManaSymbols from "../components/ManaSymbols.vue";
import { api } from "../api";
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
  GALLERY_SORT_KEY,
  getStoredDeckCardsView,
  getStoredGallerySort,
} from "../utils/deckBrowse";
import {
  buildDeckCardGroups,
  cardTypeGroup,
  DECK_COLOR_ORDER,
  DECK_TYPE_LABELS,
  DECK_TYPE_ORDER,
  filterDeckCards,
  sortDeckCards,
  splitCommanderCards,
} from "../utils/deckCards";
import { cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import {
  formatDeckOwned,
  formatEuro,
  formatProfit,
  formatRoi,
} from "../utils/format";

const route = useRoute();
const router = useRouter();

const deckId = ref("");
const browseIndex = ref(null);
const gallerySort = ref(getStoredGallerySort());
const deckCardsView = ref(getStoredDeckCardsView());
const deckTypeFilter = ref("all");
const deckColorFilters = ref([]);
const deckCardSort = ref("name");
const deckDetailRef = ref(null);
const createDeckOpen = ref(false);

const { loading: loadingBrowse, run: runBrowseLoad } = useAsyncLoad();

const decks = computed(() => browseIndex.value?.decks || []);
const browsePages = computed(() => browseIndex.value?.pages || {});
const browseStats = computed(() => browsePages.value[String(deckId.value)] || null);
const activeBrowseDeck = computed(
  () => decks.value.find((deck) => String(deck.id) === String(deckId.value)) || null,
);

const unknownCards = computed(() => browseStats.value?.unknownCards || []);
const hasUnknownCards = computed(() => (browseStats.value?.unknownCount ?? 0) > 0);

const commanderCards = computed(() => {
  const { commanders } = splitCommanderCards(browseStats.value?.cards || []);
  return sortDeckCards(commanders, "name");
});

const filteredDeckCards = computed(() => {
  const { deckCards } = splitCommanderCards(browseStats.value?.cards || []);
  return filterDeckCards(deckCards, {
    typeFilter: deckTypeFilter.value,
    colorFilters: deckColorFilters.value,
  });
});

const groupedBrowseCards = computed(() =>
  buildDeckCardGroups(filteredDeckCards.value, deckCardSort.value),
);

function profitClass(value) {
  if (value == null || Number.isNaN(value)) {
    return "";
  }
  return value >= 0 ? "reports-gain" : "reports-loss";
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

watch(deckId, () => {
  syncDeckRoute();
});

watch(
  () => route.query.deck,
  () => {
    syncDeckIdFromRoute();
  },
);

watch(ownershipRevision, () => {
  mergeOwnershipPatchesIntoPages(browseIndex.value?.pages);
});

onMounted(async () => {
  await loadBrowseIndex();
  syncDeckIdFromRoute();
  if (deckId.value && !route.query.deck) {
    syncDeckRoute();
  }
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
        <DeckHero :deck="activeBrowseDeck" :stats="browseStats" />

        <div class="deck-secondary-stats">
          <div class="deck-secondary-stat">
            <span class="deck-secondary-stat-label">Purchase price</span>
            <strong>{{ formatEuro(browseStats.purchasePrice) }}</strong>
          </div>
          <div class="deck-secondary-stat">
            <span class="deck-secondary-stat-label">Profit / loss</span>
            <strong :class="profitClass(browseStats.profit)">
              {{ formatProfit(browseStats.profit) }}
            </strong>
          </div>
          <div class="deck-secondary-stat">
            <span class="deck-secondary-stat-label">ROI</span>
            <strong>
              {{ formatRoi(browseStats.profit, browseStats.purchasePrice || browseStats.invested) }}
            </strong>
          </div>
          <div class="deck-secondary-stat">
            <span class="deck-secondary-stat-label">Priced</span>
            <strong>
              {{
                browseStats.trackedCoverage != null
                  ? `${browseStats.trackedCoverage}%`
                  : "Unknown"
              }}
            </strong>
          </div>
          <div class="deck-secondary-stat">
            <span class="deck-secondary-stat-label">Owned</span>
            <strong>{{ formatDeckOwned(browseStats.ownedQty, browseStats.deckSize) || "—" }}</strong>
          </div>
        </div>

        <section
          v-if="hasUnknownCards"
          class="table-panel deck-unknown-panel"
          aria-label="Unpriced cards"
        >
          <h2>Unpriced cards</h2>
          <p class="deck-unknown-intro">
            {{ browseStats.unknownCount }}
            {{ browseStats.unknownCount === 1 ? "card has" : "cards have" }}
            no current market price in this deck list.
          </p>
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
                <td>{{ card.setCode || card.set_code || "—" }}</td>
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
        </section>

        <section class="table-panel deck-cards-panel">
          <div class="deck-cards-sticky">
            <div class="deck-cards-sticky-head deck-cards-sticky-head--actions-only">
              <div class="deck-cards-sticky-actions">
                <div class="button-group deck-cards-view-group">
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
                  :class="{ active: deckCardsView === 'table' }"
                  @click="changeDeckCardsView('table')"
                >
                  Table
                </button>
              </div>
              </div>
            </div>

            <div class="deck-cards-toolbar-compact">
              <div class="deck-cards-filter-group-compact">
                <span class="deck-cards-filter-label">Type</span>
                <div class="button-group deck-cards-filter-group">
                  <button
                    type="button"
                    class="filter-button"
                    :class="{ active: deckTypeFilter === 'all' }"
                    @click="deckTypeFilter = 'all'"
                  >
                    All
                  </button>
                  <button
                    v-for="type in DECK_TYPE_ORDER"
                    :key="type"
                    type="button"
                    class="filter-button"
                    :class="{ active: deckTypeFilter === type }"
                    @click="deckTypeFilter = type"
                  >
                    {{ DECK_TYPE_LABELS[type] }}
                  </button>
                </div>
              </div>

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
            :class="{ 'has-commander': commanderCards.length }"
          >
              <DeckCommanderPane
                :cards="commanderCards"
                :default-deck-id="deckId"
                :show-deck-remove="true"
                :deck-name="activeBrowseDeck?.label || activeBrowseDeck?.name || ''"
                @deck-removed="onDeckCardRemoved"
                @deck-changed="onDeckCardChanged"
              />

              <div class="deck-cards-main-pane">
                <p v-if="!filteredDeckCards.length" class="storage-empty deck-cards-filter-empty">
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

                <table v-else class="reports-table deck-cards-table">
                  <thead>
                    <tr>
                      <th>Color</th>
                      <th>Qty</th>
                      <th>Card</th>
                      <th>Type</th>
                      <th>Value</th>
                      <th>Owned</th>
                      <th>Gain / loss</th>
                    </tr>
                  </thead>
                  <tbody>
                    <template v-for="group in groupedBrowseCards" :key="group.key">
                      <tr
                        v-if="group.kind === 'section' && !group.cards?.length"
                        class="deck-cards-group-row deck-cards-section-row"
                      >
                        <td colspan="7">{{ group.label }}</td>
                      </tr>
                      <template v-else-if="group.cards?.length">
                        <tr class="deck-cards-group-row">
                          <td colspan="7">{{ group.label }}</td>
                        </tr>
                        <tr
                          v-for="card in group.cards"
                          :key="`${group.key}-${card.section}-${card.cardName}-${card.setCode}-${card.collectorNumber}`"
                          class="deck-cards-row"
                          :class="deckCardOwnershipClass(card)"
                        >
                          <td><ManaSymbols :colors="card.colors" :size="18" /></td>
                          <td>{{ card.qty }}</td>
                          <td>
                            <RouterLink
                              v-if="cardRoute(card)"
                              :to="cardRoute(card)"
                              class="reports-card-link"
                            >
                              {{ card.cardName }}
                            </RouterLink>
                            <span v-else>{{ card.cardName }}</span>
                          </td>
                          <td>{{ DECK_TYPE_LABELS[cardTypeGroup(card)] }}</td>
                          <td>{{ formatEuro(card.currentValue) }}</td>
                          <td>{{ deckCardOwnedLabel(card) }}</td>
                          <td>{{ formatProfit(card.profitLoss) }}</td>
                        </tr>
                      </template>
                    </template>
                  </tbody>
                </table>
              </div>
            </div>
        </section>
      </div>
    </template>

    <CreateDeckModal
      :open="createDeckOpen"
      @close="createDeckOpen = false"
      @created="onDeckCreated"
    />
  </div>
</template>
