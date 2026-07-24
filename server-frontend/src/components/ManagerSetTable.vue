<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import CardPreview from "./CardPreview.vue";
import CardSetSymbol from "./CardSetSymbol.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import StorageLocationSelect from "./StorageLocationSelect.vue";
import { api } from "../api";
import {
  cardPriceIssueTitle,
  copyCountForFinish,
  formatLocationsSummary,
  locationsForFinish,
  managerCardPrice,
} from "../composables/useManagerSetTable";
import { finishLabel } from "../utils/finishes";
import { formatEuro } from "../utils/format";

const MAX_OWNED_COPIES = 99;

const props = defineProps({
  setCode: { type: String, default: "" },
  finishRows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  hasMore: { type: Boolean, default: false },
  totalMatches: { type: Number, default: 0 },
  allVisibleSelected: { type: Boolean, default: false },
  isRowSelected: { type: Function, required: true },
  sortField: { type: String, default: "number" },
  sortDir: { type: String, default: "asc" },
  priceStrategy: { type: String, default: "trend" },
});

const emit = defineEmits([
  "update:allVisibleSelected",
  "toggle-row",
  "set-copy-count",
  "assign-storage",
  "load-more",
  "open-storage-modal",
  "update-single-storage",
  "sort",
]);

const storageLocations = ref([]);
const assignLocationSlug = ref("");
const loadMoreSentinelRef = ref(null);
let loadMoreObserver = null;

/**
 * `finishRows` groups multiple physical <tr>s per card via `rowspan`, so we
 * can't slice by raw row index without risking cutting a rowspan group in
 * half (which would visually corrupt the table). Instead we render a bounded
 * number of complete card groups and reveal more as the user scrolls near the
 * bottom — the same incremental-reveal idea as the existing "load more"
 * sentinel below, just for rows already fetched but not yet rendered. This
 * keeps "select all" / long scroll sessions on big sets from dumping
 * thousands of <tr> elements into the DOM at once.
 */
const RENDER_CHUNK_GROUPS = 60;
const renderGroupLimit = ref(RENDER_CHUNK_GROUPS);

const cardGroups = computed(() => {
  const groups = [];
  let current = null;
  for (const row of props.finishRows) {
    if (row.isFirstFinishRow || !current) {
      current = [];
      groups.push(current);
    }
    current.push(row);
  }
  return groups;
});

const visibleFinishRows = computed(() =>
  cardGroups.value.slice(0, renderGroupLimit.value).flat(),
);

const hasMoreToReveal = computed(() => renderGroupLimit.value < cardGroups.value.length);

watch(
  () => props.loading,
  (isLoading) => {
    if (isLoading) {
      renderGroupLimit.value = RENDER_CHUNK_GROUPS;
    }
  },
);

async function loadStorageLocations() {
  const payload = await api.listStorageLocations();
  storageLocations.value = payload.locations || [];
  assignLocationSlug.value = payload.defaultLocation || storageLocations.value[0]?.slug || "";
}

function onSelectAllChange(event) {
  emit("update:allVisibleSelected", event.target.checked);
}

function onAssignStorage() {
  emit("assign-storage", assignLocationSlug.value);
}

function onCopyCountChange(row, event) {
  emit("set-copy-count", row.card, row.finish, event.target.value);
}

function onToggleRow(row) {
  emit("toggle-row", row);
}

function storageSummary(row) {
  return formatLocationsSummary(locationsForFinish(row.card, row.finish));
}

function ownedCount(row) {
  return copyCountForFinish(row.card, row.finish);
}

function singleStorageSlug(row) {
  const locations = locationsForFinish(row.card, row.finish);
  return locations[0]?.slug || assignLocationSlug.value || "";
}

function onSingleStorageChange(row, slug) {
  emit("update-single-storage", row.card, row.finish, slug);
}

function openStorageModal(row) {
  emit("open-storage-modal", row.card, row.finish);
}

function cardRoute(card) {
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
  };
}

const sortableColumns = [
  { field: "number", label: "#" },
  { field: "name", label: "Card" },
  { field: "artStyle", label: "Art Style" },
  { field: "value", label: "Price" },
];

function sortIndicator(field) {
  if (props.sortField !== field) {
    return "";
  }
  return props.sortDir === "asc" ? "↑" : "↓";
}

function onSortColumn(field) {
  emit("sort", field);
}

function cardPriceLabel(card, finish = 0) {
  return formatEuro(managerCardPrice(card, props.priceStrategy, finish));
}

const visibleRowCount = computed(() => props.finishRows.length);

function disconnectLoadMoreObserver() {
  loadMoreObserver?.disconnect();
  loadMoreObserver = null;
}

async function setupLoadMoreObserver() {
  disconnectLoadMoreObserver();
  await nextTick();
  const sentinel = loadMoreSentinelRef.value;
  if (!sentinel || (!props.hasMore && !hasMoreToReveal.value)) {
    return;
  }
  loadMoreObserver = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) {
        return;
      }
      if (hasMoreToReveal.value) {
        renderGroupLimit.value = Math.min(
          cardGroups.value.length,
          renderGroupLimit.value + RENDER_CHUNK_GROUPS,
        );
        return;
      }
      if (props.hasMore) {
        emit("load-more");
      }
    },
    { rootMargin: "240px" },
  );
  loadMoreObserver.observe(sentinel);
}

watch(
  () => [props.hasMore, hasMoreToReveal.value, props.finishRows.length, props.loading],
  () => {
    setupLoadMoreObserver();
  },
);

onMounted(loadStorageLocations);

onBeforeUnmount(disconnectLoadMoreObserver);
</script>

<template>
  <div class="manager-set-table">
    <div class="manager-toolbar-actions">
      <label class="manager-select-all">
        <input
          type="checkbox"
          :checked="allVisibleSelected"
          @change="onSelectAllChange"
        >
        Select all
      </label>

      <label class="manager-filter manager-filter-storage">
        <span>Assign to</span>
        <StorageLocationSelect
          v-model="assignLocationSlug"
          :locations="storageLocations"
          :include-types="['storage', 'binder']"
          aria-label="Assign storage location"
        />
      </label>
      <button type="button" class="btn btn-secondary" @click="onAssignStorage">
        Assign storage
      </button>
    </div>

    <p v-if="setCode" class="manager-stats">
      Showing {{ visibleRowCount }} finish rows from {{ totalMatches }} cards
    </p>

    <div v-if="loading && !finishRows.length" class="storage-empty">
      <LoadingIndicator label="Loading cards…" />
    </div>

    <div v-else-if="!finishRows.length" class="storage-empty">
      No cards found for this set.
    </div>

    <div v-else class="table-panel cards-panel manager-cards-panel">
      <table class="manager-table manager-table-compact">
        <thead>
          <tr>
            <th></th>
            <th
              v-for="column in sortableColumns"
              :key="column.field"
              class="manager-table-sort-header"
            >
              <button
                type="button"
                class="manager-table-sort-button"
                :aria-label="`Sort by ${column.label}${sortIndicator(column.field) ? ` (${props.sortDir === 'asc' ? 'ascending' : 'descending'})` : ''}`"
                @click="onSortColumn(column.field)"
              >
                <span>{{ column.label }}</span>
                <span
                  v-if="sortIndicator(column.field)"
                  class="manager-table-sort-indicator"
                  aria-hidden="true"
                >
                  {{ sortIndicator(column.field) }}
                </span>
              </button>
            </th>
            <th>Finish</th>
            <th>Qty</th>
            <th>Storage</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in visibleFinishRows" :key="row.rowKey">
            <td>
              <input
                type="checkbox"
                :checked="isRowSelected(row)"
                @change="onToggleRow(row)"
              >
            </td>
            <td
              v-if="row.isFirstFinishRow"
              :rowspan="row.finishRowCount"
              class="manager-table-grouped-cell"
            >
              {{ row.card.collectorNumber }}
            </td>
            <td
              v-if="row.isFirstFinishRow"
              :rowspan="row.finishRowCount"
              class="manager-table-grouped-cell"
            >
              <CardPreview
                :image-uri="row.card.imageUri"
                :image-uri-back="row.card.imageUriBack || ''"
              >
                <span class="manager-card-name-row">
                  <CardSetSymbol :set-code="row.card.setCode" :rarity="row.card.rarity || ''" />
                  <RouterLink :to="cardRoute(row.card)" class="reports-card-link">
                    {{ row.card.name }}
                  </RouterLink>
                </span>
              </CardPreview>
            </td>
            <td
              v-if="row.isFirstFinishRow"
              :rowspan="row.finishRowCount"
              class="manager-table-grouped-cell"
            >
              {{ row.card.artStyle || "—" }}
            </td>
            <td
              v-if="row.isFirstFinishRow"
              :rowspan="row.finishRowCount"
              class="manager-table-grouped-cell manager-price-cell"
            >
              <div class="manager-price-value-row">
                <span class="manager-price-value">{{ cardPriceLabel(row.card, row.finish) }}</span>
                <span
                  v-if="row.card.priceIssues?.length"
                  class="manager-price-health-badge"
                  :title="cardPriceIssueTitle(row.card)"
                >
                  ⚠
                </span>
                <span
                  v-else
                  class="manager-price-health-ok"
                  title="Pricing looks OK for owned finishes"
                >
                  ✓
                </span>
              </div>
            </td>
            <td class="manager-finish-label-cell">{{ finishLabel(row.finish) }}</td>
            <td class="manager-copy-count-cell">
              <input
                type="number"
                class="manager-copy-count-input"
                min="0"
                :max="MAX_OWNED_COPIES"
                :value="ownedCount(row)"
                :aria-label="`${finishLabel(row.finish)} copy count`"
                @change="onCopyCountChange(row, $event)"
              >
            </td>
            <td class="manager-storage-cell">
              <template v-if="ownedCount(row) <= 0">
                <span class="manager-finish-unavailable">—</span>
              </template>
              <template v-else-if="ownedCount(row) === 1">
                <StorageLocationSelect
                  class="manager-storage-inline-select"
                  :model-value="singleStorageSlug(row)"
                  :locations="storageLocations"
                  :include-types="['storage', 'binder']"
                  :aria-label="`${finishLabel(row.finish)} storage location`"
                  @update:model-value="(slug) => onSingleStorageChange(row, slug)"
                />
              </template>
              <template v-else>
                <div class="manager-storage-multi">
                  <span class="manager-storage-summary" :title="storageSummary(row)">
                    {{ storageSummary(row) }}
                  </span>
                  <button
                    type="button"
                    class="btn btn-secondary btn-small manager-storage-manage-btn"
                    @click="openStorageModal(row)"
                  >
                    Manage
                  </button>
                </div>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
      <div
        v-if="hasMore || hasMoreToReveal"
        ref="loadMoreSentinelRef"
        class="manager-load-more-sentinel"
        aria-hidden="true"
      />
      <p v-if="loadingMore" class="collection-search-load-more-status">
        <LoadingIndicator compact label="Loading more cards…" />
      </p>
    </div>
  </div>
</template>
