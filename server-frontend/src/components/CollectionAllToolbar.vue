<script setup>
import { computed } from "vue";
import CollectionGalleryScaleControl from "./CollectionGalleryScaleControl.vue";
import { useCatalogChrome } from "../composables/useCatalogChrome";
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
  scaleOptions: { type: Array, default: () => [75, 100, 125, 150, 175, 200, 225, 250] },
  mobileFiltersOpen: { type: Boolean, default: false },
  viewMode: { type: String, default: "gallery" },
  tableModeAvailable: { type: Boolean, default: false },
  statsModeAvailable: { type: Boolean, default: false },
  showLenses: { type: Boolean, default: true },
  showBulk: { type: Boolean, default: true },
  showFiltersButton: { type: Boolean, default: true },
  showViewMode: { type: Boolean, default: true },
  showSort: { type: Boolean, default: true },
  /** collection: number/value; search: name/value/cmc/rarity (+ newest) */
  sortMode: { type: String, default: "collection" },
  allCardsSort: { type: String, default: "value" },
  allCardsSortDir: { type: String, default: "desc" },
  /** Color/price section headers in catalog gallery. */
  rollup: { type: Boolean, default: true },
  showRollup: { type: Boolean, default: false },
  /** Toggle that hides navbar, set browser, filters, and lens chips. */
  showChromeToggle: { type: Boolean, default: false },
  /** Update prices for the selected non-favourite set. */
  showSetPriceSync: { type: Boolean, default: false },
  setPriceSyncBusy: { type: Boolean, default: false },
  /** Wash tile backgrounds by price band. */
  priceTileTint: { type: Boolean, default: false },
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
  "update:rollup",
  "update:priceTileTint",
  "trigger-set-price-sync",
]);

const { catalogChromeExpanded, toggleCatalogChromeExpanded } = useCatalogChrome();

const isTableView = computed(() => props.viewMode === "table");
const isStatsView = computed(() => props.viewMode === "stats");
const hideGalleryChrome = computed(() => isTableView.value || isStatsView.value);
const hideFilterTags = computed(
  () => hideGalleryChrome.value || catalogChromeExpanded.value,
);
const chromeToggleLabel = computed(() =>
  catalogChromeExpanded.value
    ? "Restore navigation and filters"
    : "Expand catalog",
);
const setPriceSyncLabel = "Update prices for this set. Favourite sets and owned cards update automatically on price sync; other sets only when you ask.";

const resolvedPlaceholder = computed(() => {
  if (props.searchPlaceholder) {
    return props.searchPlaceholder;
  }
  return isTableView.value ? "Search cards…" : "Search name or #…";
});

const matchSummary = computed(() => {
  if (props.summaryText) {
    if (hideGalleryChrome.value && !props.showSummaryInTable) {
      return null;
    }
    return props.summaryText;
  }
  if (hideGalleryChrome.value) {
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
  if (props.summaryText || hideGalleryChrome.value) {
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
  if (mode === "stats" && !props.statsModeAvailable) {
    return;
  }
  if (props.viewMode !== mode) {
    emit("update:viewMode", mode);
  }
}
</script>

<template>
  <div
    class="collection-all-toolbar"
    :class="{ 'collection-all-toolbar--chrome-expanded': catalogChromeExpanded }"
  >
    <div class="collection-all-toolbar-row collection-all-toolbar-row--primary">
      <button
        v-if="showChromeToggle"
        type="button"
        class="btn btn-secondary collection-chrome-toggle"
        :aria-pressed="catalogChromeExpanded ? 'true' : 'false'"
        :aria-label="chromeToggleLabel"
        :title="chromeToggleLabel"
        @click="toggleCatalogChromeExpanded"
      >
        <svg
          class="collection-chrome-toggle-icon"
          viewBox="0 0 24 24"
          aria-hidden="true"
          focusable="false"
        >
          <path
            v-if="catalogChromeExpanded"
            d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <path
            v-else
            d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
      <button
        v-if="showSetPriceSync"
        type="button"
        class="btn btn-secondary collection-chrome-toggle"
        :disabled="setPriceSyncBusy"
        :aria-label="setPriceSyncLabel"
        :title="setPriceSyncLabel"
        @click="emit('trigger-set-price-sync')"
      >
        <svg
          class="collection-chrome-toggle-icon"
          viewBox="0 0 24 24"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M4 12a8 8 0 0 1 13.66-5.66M20 4v6h-6M20 12a8 8 0 0 1-13.66 5.66M4 20v-6h6"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
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
        v-if="showSort && !hideGalleryChrome"
        class="collection-all-sort"
      >
        <span class="visually-hidden">Sort by</span>
        <div class="collection-sort-row">
          <select :value="allCardsSort" @change="emit('update-sort', $event)">
            <template v-if="sortMode === 'search'">
              <option value="newest">Newest set</option>
              <option value="name">Name</option>
              <option value="value">Value</option>
              <option value="cmc">CMC</option>
              <option value="power">Power</option>
              <option value="toughness">Toughness</option>
              <option value="rarity">Rarity</option>
            </template>
            <template v-else>
              <option value="number">Collector number</option>
              <option value="value">Value</option>
            </template>
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
      <button
        v-if="showFiltersButton"
        type="button"
        class="btn btn-secondary btn-small collection-all-filters-btn"
        :aria-expanded="mobileFiltersOpen ? 'true' : 'false'"
        @click="emit('open-mobile-filters')"
      >
        Filters
      </button>
      <div v-if="showRollup && !hideGalleryChrome" class="collection-all-toolbar-checks">
        <label
          class="collection-all-toolbar-check"
          title="Group gallery by color or price"
        >
          <input
            type="checkbox"
            :checked="rollup"
            @change="emit('update:rollup', $event.target.checked)"
          >
          <span>Roll-up</span>
        </label>
        <label
          class="collection-all-toolbar-check"
          title="Tint card tiles by price"
        >
          <input
            type="checkbox"
            :checked="priceTileTint"
            @change="emit('update:priceTileTint', $event.target.checked)"
          >
          <span>Price colors</span>
        </label>
      </div>
      <CollectionGalleryScaleControl
        v-if="!hideGalleryChrome"
        class="collection-gallery-toolbar-scale"
        :model-value="cardScale"
        :options="scaleOptions"
        @update:model-value="emit('update:cardScale', $event)"
      />
      <div
        v-if="showViewMode"
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
        <button
          type="button"
          class="filter-button"
          :class="{ active: viewMode === 'stats' }"
          :disabled="!statsModeAvailable"
          :title="statsModeAvailable ? 'Stats view' : 'Select a set for stats view'"
          @click="setViewMode('stats')"
        >
          Stats
        </button>
      </div>
    </div>

    <div v-if="showLenses && !hideFilterTags" class="collection-all-toolbar-row collection-all-lenses">
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

    <div v-if="showBulk && !hideGalleryChrome && bulkSelectMode && selectedCount" class="collection-bulk-bar">
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
