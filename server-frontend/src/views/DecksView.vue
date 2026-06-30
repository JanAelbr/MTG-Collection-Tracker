<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DeckGallery from "../components/DeckGallery.vue";
import DeckCardGrid from "../components/DeckCardGrid.vue";
import ManaSymbols from "../components/ManaSymbols.vue";
import { api } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import {
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
} from "../utils/deckCards";
import { cardFinish, cardRouteQuery } from "../utils/finishes";
import {
  formatDeckOwned,
  formatDeckValueRange,
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

const { loading: loadingBrowse, run: runBrowseLoad } = useAsyncLoad();

const decks = computed(() => browseIndex.value?.decks || []);
const browsePages = computed(() => browseIndex.value?.pages || {});
const browseStats = computed(() => browsePages.value[String(deckId.value)] || null);
const activeBrowseDeck = computed(
  () => decks.value.find((deck) => String(deck.id) === String(deckId.value)) || null,
);

const filteredBrowseCards = computed(() =>
  filterDeckCards(browseStats.value?.cards || [], {
    typeFilter: deckTypeFilter.value,
    colorFilters: deckColorFilters.value,
  }),
);

const groupedBrowseCards = computed(() =>
  buildDeckCardGroups(filteredBrowseCards.value, deckCardSort.value),
);

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

function cardRoute(card) {
  if (!card.setCode || !card.collectorNumber) {
    return null;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
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

function selectBrowseDeck(nextDeckId) {
  deckId.value = nextDeckId;
  deckTypeFilter.value = "all";
  deckColorFilters.value = [];
  syncDeckRoute();
}

function changeGallerySort(nextSort) {
  gallerySort.value = nextSort;
  localStorage.setItem(GALLERY_SORT_KEY, nextSort);
}

function changeDeckCardsView(nextView) {
  deckCardsView.value = nextView;
  localStorage.setItem(DECK_CARDS_VIEW_KEY, nextView);
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
          <LoadingIndicator v-if="loadingBrowse" compact label="Refreshing…" />
        </div>

        <DeckGallery
          :decks="decks"
          :pages="browsePages"
          :active-deck-id="deckId"
          :sort-by="gallerySort"
          @select="selectBrowseDeck"
        />
      </div>

      <template v-if="browseStats && activeBrowseDeck">
        <div class="deck-summary-row">
          <div class="deck-summary-item">
            <span class="deck-summary-label">Value</span>
            <strong class="deck-summary-value">
              {{ formatDeckValueRange(browseStats.ownedCurrent, browseStats.current) }}
            </strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">Owned value</span>
            <strong class="deck-summary-value">{{ formatEuro(browseStats.ownedCurrent) }}</strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">Deck size</span>
            <strong class="deck-summary-value">{{ browseStats.deckSize || 0 }}</strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">Owned</span>
            <strong class="deck-summary-value">
              {{ formatDeckOwned(browseStats.ownedQty, browseStats.deckSize) || "—" }}
            </strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">Missing</span>
            <strong class="deck-summary-value">{{ browseStats.missingQty || 0 }}</strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">Tracked</span>
            <strong class="deck-summary-value">
              {{
                browseStats.trackedCoverage != null
                  ? `${browseStats.trackedCoverage}% priced`
                  : "Unknown"
              }}
            </strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">Purchase price</span>
            <strong class="deck-summary-value">{{ formatEuro(browseStats.purchasePrice) }}</strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">Profit / loss</span>
            <strong class="deck-summary-value">{{ formatProfit(browseStats.profit) }}</strong>
          </div>

          <div class="deck-summary-item">
            <span class="deck-summary-label">ROI</span>
            <strong class="deck-summary-value">
              {{ formatRoi(browseStats.profit, browseStats.purchasePrice || browseStats.invested) }}
            </strong>
          </div>
        </div>

        <section class="table-panel deck-cards-panel">
          <div class="deck-cards-toolbar">
            <h2>{{ activeBrowseDeck.label }}</h2>
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

          <div class="deck-cards-filters">
            <div class="deck-cards-filter-row">
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

            <div class="deck-cards-filter-row">
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

            <div class="deck-cards-filter-row">
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

          <p v-if="!filteredBrowseCards.length" class="storage-empty">
            No cards match the current filters.
          </p>

          <DeckCardGrid v-else-if="deckCardsView === 'images'" :groups="groupedBrowseCards" />

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
                    <td>{{ card.ownedQty > 0 ? `${card.ownedQty} / ${card.qty}` : "—" }}</td>
                    <td>{{ formatProfit(card.profitLoss) }}</td>
                  </tr>
                </template>
              </template>
            </tbody>
          </table>
        </section>
      </template>
    </template>
  </div>
</template>
