<script setup>
import "../styles/print-cards.css";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import { api, ignoreAborted } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { usePrintList } from "../composables/printList";
import { usePricingSettings } from "../composables/pricingSettings";
import { cardSelectionKey } from "../utils/collectionScopeStats";
import { cardFinish } from "../utils/finishes";

const PAGE_SIZE = 50;
const OWNED_ALL = "all";
const OWNED_OWNED = "owned";

const searchInput = ref("");
const searchQuery = ref("");
const ownedFilter = ref(OWNED_ALL);
const accumulatedCards = ref([]);
const totalMatches = ref(0);
const loadedPages = ref(0);
const loadingMore = ref(false);
const loadError = ref("");
const { loading, run } = useAsyncLoad();
const { collectionCardScale } = usePricingSettings();
const printList = usePrintList();
let searchTimer = null;
let requestToken = 0;

const cards = computed(() => accumulatedCards.value);
const listCards = computed(() => printList.items.value);
const selectedCards = computed(() => printList.selectedCards.value);
const listSelectedKeys = computed(() => printList.selectedKeys.value);
const gallerySelectedKeys = computed(() => new Set(
  listCards.value.map((card) => cardSelectionKey(card)),
));
const listCount = computed(() => printList.count.value);
const selectedCount = computed(() => printList.selectedCount.value);
const totalPages = computed(() => Math.max(1, Math.ceil(totalMatches.value / PAGE_SIZE)));
const hasMore = computed(() => loadedPages.value < totalPages.value);
const showUnownedBadge = computed(() => ownedFilter.value === OWNED_ALL);

function filterParams() {
  return {
    report: "all",
    setCode: "All",
    ownedFilter: ownedFilter.value,
    foilFilter: "all",
    search: searchQuery.value.trim(),
    sort: "number",
    sortDir: "asc",
  };
}

function resetResults() {
  accumulatedCards.value = [];
  totalMatches.value = 0;
  loadedPages.value = 0;
}

function applyPayload(payload, { append = false } = {}) {
  const incoming = payload.cards || [];
  if (!append) {
    accumulatedCards.value = incoming;
  } else if (incoming.length) {
    const seen = new Set(accumulatedCards.value.map((card) => cardSelectionKey(card)));
    const unique = incoming.filter((card) => {
      const key = cardSelectionKey(card);
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
    if (unique.length) {
      accumulatedCards.value = [...accumulatedCards.value, ...unique];
    }
  }
  totalMatches.value = payload.totalMatches ?? totalMatches.value;
  loadedPages.value = payload.page ?? (append ? loadedPages.value + 1 : 1);
}

async function fetchPage(pageNum) {
  const token = ++requestToken;
  const payload = await ignoreAborted(api.getReportCards({
    ...filterParams(),
    page: pageNum,
    pageSize: PAGE_SIZE,
  }));
  if (!payload || token !== requestToken) {
    return null;
  }
  return payload;
}

async function loadResults() {
  loadError.value = "";
  await run(async (isCurrent) => {
    resetResults();
    try {
      const payload = await fetchPage(1);
      if (!isCurrent() || !payload) {
        return;
      }
      applyPayload(payload, { append: false });
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      loadError.value = error?.message || "Could not load cards.";
      resetResults();
    }
  });
}

async function loadMore() {
  if (loadingMore.value || loading.value || !hasMore.value) {
    return;
  }
  loadingMore.value = true;
  try {
    const payload = await fetchPage(loadedPages.value + 1);
    if (payload) {
      applyPayload(payload, { append: true });
    }
  } finally {
    loadingMore.value = false;
  }
}

function scheduleSearch() {
  if (searchTimer) {
    clearTimeout(searchTimer);
  }
  searchTimer = setTimeout(() => {
    searchQuery.value = searchInput.value.trim();
  }, 250);
}

function setOwnedFilter(next) {
  if (ownedFilter.value === next) {
    return;
  }
  ownedFilter.value = next;
}

function toggleListMembership(card) {
  printList.toggle(card);
}

function clearList() {
  printList.clear();
}

function removeFromList(card) {
  printList.remove(card);
}

function togglePrintSelected(card) {
  printList.toggleSelected(card);
}

function selectAllForPrint() {
  printList.selectAll();
}

function clearPrintSelection() {
  printList.clearSelection();
}

function printCards() {
  if (!selectedCards.value.length) {
    return;
  }
  window.print();
}

function printTileKey(card) {
  return `print-${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`;
}

watch([searchQuery, ownedFilter], () => {
  loadResults();
});

onMounted(() => {
  loadResults();
});

onUnmounted(() => {
  if (searchTimer) {
    clearTimeout(searchTimer);
  }
});
</script>

<template>
  <div class="print-cards-page collection-page">
    <div class="print-cards-no-print">
      <header class="print-cards-page-header">
        <h1>Cards</h1>
        <p class="print-cards-page-intro">
          Add prints from anywhere via right-click, or click cards here. Select which queued cards to print.
        </p>
      </header>

      <div class="print-cards-page-toolbar">
        <label class="print-cards-page-search">
          <span class="sr-only">Search cards</span>
          <input
            v-model="searchInput"
            type="search"
            placeholder="Search cards"
            autocomplete="off"
            spellcheck="false"
            @input="scheduleSearch"
          />
        </label>

        <div class="print-cards-scope" role="group" aria-label="Ownership filter">
          <button
            type="button"
            class="print-cards-mode-btn"
            :class="{ 'is-active': ownedFilter === OWNED_ALL }"
            @click="setOwnedFilter(OWNED_ALL)"
          >
            All
          </button>
          <button
            type="button"
            class="print-cards-mode-btn"
            :class="{ 'is-active': ownedFilter === OWNED_OWNED }"
            @click="setOwnedFilter(OWNED_OWNED)"
          >
            Owned
          </button>
        </div>

        <div class="print-cards-page-actions">
          <span v-if="listCount" class="print-cards-page-selection-count">
            {{ selectedCount }} of {{ listCount }} selected
          </span>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!listCount"
            @click="selectAllForPrint"
          >
            Select all
          </button>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!selectedCount"
            @click="clearPrintSelection"
          >
            Clear selection
          </button>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!listCount"
            @click="clearList"
          >
            Clear list
          </button>
          <button
            type="button"
            class="btn btn-primary btn-small"
            :disabled="!selectedCount"
            @click="printCards"
          >
            Print / Save PDF
          </button>
        </div>
      </div>

      <p v-if="loadError" class="print-cards-page-error">{{ loadError }}</p>
      <p v-else-if="!loading" class="print-cards-page-muted">
        {{ totalMatches }} print{{ totalMatches === 1 ? "" : "s" }}
        <template v-if="searchQuery"> matching “{{ searchQuery }}”</template>
      </p>
    </div>

    <div v-if="loading && !cards.length" class="print-cards-page-empty print-cards-no-print">
      <LoadingIndicator label="Loading cards…" />
    </div>

    <div v-else class="print-cards-layout print-cards-no-print">
      <div class="print-cards-gallery">
        <p v-if="!cards.length" class="print-cards-page-empty">
          No cards match this filter.
        </p>
        <VirtualizedCollectionCardGrid
          v-else
          :cards="cards"
          :card-scale="collectionCardScale"
          :show-unowned-badge="showUnownedBadge"
          :show-set-label="true"
          :show-favorites="false"
          :selectable="true"
          :selected-keys="gallerySelectedKeys"
          :has-more="hasMore"
          zoom-only
          @toggle-select="toggleListMembership"
          @load-more="loadMore"
        />
        <p v-if="loadingMore" class="print-cards-page-muted">Loading more…</p>
      </div>

      <aside class="print-cards-queue" aria-label="Print list">
        <h2 class="print-cards-queue-heading">Print list</h2>
        <p v-if="!listCards.length" class="print-cards-preview-empty">
          Right-click any card to add it, or click cards in the gallery.
        </p>
        <div v-else class="print-cards-list" role="list">
          <div
            v-for="card in listCards"
            :key="cardSelectionKey(card)"
            class="print-cards-list-item"
            role="listitem"
            :class="{ 'is-selected': listSelectedKeys.has(cardSelectionKey(card)) }"
          >
            <input
              type="checkbox"
              class="print-cards-list-checkbox"
              :checked="listSelectedKeys.has(cardSelectionKey(card))"
              :aria-label="`Include ${printList.displayLabel(card)} in print`"
              @click.prevent="togglePrintSelected(card)"
            />
            <button
              type="button"
              class="print-cards-thumb print-cards-list-thumb"
              :title="printList.displayLabel(card)"
              @click="togglePrintSelected(card)"
            >
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="printList.displayLabel(card)"
                loading="lazy"
              />
              <span v-else class="print-cards-thumb-fallback">{{ printList.displayLabel(card) }}</span>
            </button>
            <button
              type="button"
              class="print-cards-list-remove"
              :aria-label="`Remove ${printList.displayLabel(card)} from print list`"
              title="Remove from list"
              @click="removeFromList(card)"
            >
              ×
            </button>
          </div>
        </div>
      </aside>
    </div>

    <div class="print-cards-print-sheet" aria-hidden="true">
      <div
        v-for="card in selectedCards"
        :key="printTileKey(card)"
        class="print-cards-print-tile"
      >
        <img
          v-if="card.imageUri"
          :src="card.imageUri"
          :alt="printList.displayLabel(card)"
        />
        <div v-else class="print-cards-print-fallback">
          {{ printList.displayLabel(card) }}
        </div>
      </div>
    </div>
  </div>
</template>
