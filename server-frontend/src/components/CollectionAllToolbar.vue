<script setup>
import { computed } from "vue";
import CollectionGalleryScaleControl from "./CollectionGalleryScaleControl.vue";
import { COLLECTION_LENSES } from "../utils/collectionLenses";
import { formatDeckValueRange } from "../utils/format";

const props = defineProps({
  searchQuery: { type: String, default: "" },
  activeLens: { type: String, default: "" },
  filteredCount: { type: Number, default: 0 },
  scopeCount: { type: Number, default: 0 },
  scopeStats: { type: Object, default: null },
  bulkSelectMode: { type: Boolean, default: false },
  selectedCount: { type: Number, default: 0 },
  bulkBusy: { type: Boolean, default: false },
  cardScale: { type: Number, default: 100 },
  scaleOptions: { type: Array, default: () => [75, 100, 125, 150] },
  mobileFiltersOpen: { type: Boolean, default: false },
  viewMode: { type: String, default: "gallery" },
  tableModeAvailable: { type: Boolean, default: false },
  showLenses: { type: Boolean, default: true },
  showBulk: { type: Boolean, default: true },
  showFiltersButton: { type: Boolean, default: true },
  showSort: { type: Boolean, default: true },
  allCardsSort: { type: String, default: "value" },
  allCardsSortDir: { type: String, default: "desc" },
  /** When set, replaces the default collection match summary text. */
  summaryText: { type: String, default: "" },
  showSummaryInTable: { type: Boolean, default: false },
  searchPlaceholder: { type: String, default: "" },
});

const emit = defineEmits([
  "update:searchQuery",
  "update:viewMode",
  "select-lens",
  "toggle-bulk-mode",
  "bulk-mark-owned",
  "bulk-clear-selection",
  "open-mobile-filters",
  "update:cardScale",
  "update-sort",
  "toggle-sort-dir",
]);

const isTableView = computed(() => props.viewMode === "table");

const resolvedPlaceholder = computed(() => {
  if (props.searchPlaceholder) {
    return props.searchPlaceholder;
  }
  return isTableView.value ? "Search cards…" : "Search name or #…";
});

const matchSummary = computed(() => {
  if (props.summaryText) {
    if (isTableView.value && !props.showSummaryInTable) {
      return null;
    }
    return props.summaryText;
  }
  if (isTableView.value) {
    return null;
  }
  if (!props.scopeCount) {
    return "No cards in scope";
  }
  if (props.filteredCount === props.scopeCount) {
    return `${props.filteredCount} cards in scope`;
  }
  const missingInView = props.scopeStats?.missingCount ?? 0;
  return `${props.filteredCount} shown · ${props.scopeCount} in scope · ${missingInView} missing`;
});

const scopeValueLabel = computed(() => {
  if (props.summaryText || isTableView.value) {
    return "";
  }
  const ownedValue = props.scopeStats?.ownedValue ?? 0;
  const totalValue = props.scopeStats?.totalValue ?? 0;
  if (!(totalValue > 0 || ownedValue > 0)) {
    return "";
  }
  return formatDeckValueRange(ownedValue, totalValue);
});

function setViewMode(mode) {
  if (mode === "table" && !props.tableModeAvailable) {
    return;
  }
  if (props.viewMode !== mode) {
    emit("update:viewMode", mode);
  }
}
</script>

<template>
  <div class="collection-all-toolbar">
    <div class="collection-all-toolbar-row">
      <label class="collection-all-search">
        <span class="visually-hidden">Search cards</span>
        <input
          :value="searchQuery"
          type="search"
          :placeholder="resolvedPlaceholder"
          autocomplete="off"
          @input="emit('update:searchQuery', $event.target.value)"
        >
      </label>
      <label
        v-if="showSort && !isTableView"
        class="collection-all-sort"
      >
        <span class="visually-hidden">Sort by</span>
        <div class="collection-sort-row">
          <select :value="allCardsSort" @change="emit('update-sort', $event)">
            <option value="number">Collector number</option>
            <option value="value">Value</option>
          </select>
          <button
            type="button"
            class="btn btn-secondary collection-sort-dir"
            :title="allCardsSortDir === 'asc' ? 'Ascending' : 'Descending'"
            :aria-label="`Sort ${allCardsSortDir === 'asc' ? 'ascending' : 'descending'}`"
            @click="emit('toggle-sort-dir')"
          >
            {{ allCardsSortDir === "asc" ? "↑" : "↓" }}
          </button>
        </div>
      </label>
      <div
        class="button-group collection-view-mode-group"
        role="group"
        aria-label="View mode"
      >
        <button
          type="button"
          class="filter-button"
          :class="{ active: viewMode === 'gallery' }"
          @click="setViewMode('gallery')"
        >
          Gallery
        </button>
        <button
          type="button"
          class="filter-button"
          :class="{ active: viewMode === 'table' }"
          :disabled="!tableModeAvailable"
          :title="tableModeAvailable ? 'Table view' : 'Select a specific set for table view'"
          @click="setViewMode('table')"
        >
          Table
        </button>
      </div>
      <button
        v-if="showFiltersButton"
        type="button"
        class="btn btn-secondary btn-small collection-all-filters-btn"
        :aria-expanded="mobileFiltersOpen ? 'true' : 'false'"
        @click="emit('open-mobile-filters')"
      >
        Filters
      </button>
      <button
        v-if="showBulk && !isTableView"
        type="button"
        class="btn btn-secondary btn-small"
        :class="{ 'is-active': bulkSelectMode }"
        @click="emit('toggle-bulk-mode')"
      >
        {{ bulkSelectMode ? "Done" : "Select" }}
      </button>
      <CollectionGalleryScaleControl
        v-if="!isTableView"
        class="collection-gallery-toolbar-scale"
        :model-value="cardScale"
        :options="scaleOptions"
        @update:model-value="emit('update:cardScale', $event)"
      />
    </div>

    <div v-if="showLenses && !isTableView" class="collection-all-toolbar-row collection-all-lenses">
      <button
        v-for="lens in COLLECTION_LENSES"
        :key="lens.id"
        type="button"
        class="collection-lens-chip"
        :class="{ active: activeLens === lens.id }"
        @click="emit('select-lens', lens.id)"
      >
        {{ lens.label }}
      </button>
    </div>

    <div v-if="matchSummary" class="collection-all-toolbar-row collection-all-summary">
      <p class="collection-gallery-toolbar-stats">{{ matchSummary }}</p>
      <p v-if="scopeValueLabel" class="collection-all-scope-value">
        Owned / all value: {{ scopeValueLabel }}
      </p>
    </div>

    <div v-if="showBulk && !isTableView && bulkSelectMode && selectedCount" class="collection-bulk-bar">
      <span>{{ selectedCount }} selected</span>
      <button
        type="button"
        class="btn btn-primary btn-small"
        :disabled="bulkBusy"
        @click="emit('bulk-mark-owned')"
      >
        Mark owned
      </button>
      <button
        type="button"
        class="btn btn-secondary btn-small"
        :disabled="bulkBusy"
        @click="emit('bulk-clear-selection')"
      >
        Clear
      </button>
    </div>
  </div>
</template>
