<script setup>
import { computed } from "vue";
import CollectionGalleryScaleControl from "./CollectionGalleryScaleControl.vue";
import { COLLECTION_LENSES } from "../utils/collectionLenses";
import { formatEuro } from "../utils/format";

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
});

const emit = defineEmits([
  "update:searchQuery",
  "select-lens",
  "toggle-bulk-mode",
  "bulk-mark-owned",
  "bulk-clear-selection",
  "open-mobile-filters",
  "update:cardScale",
]);

const matchSummary = computed(() => {
  if (!props.scopeCount) {
    return "No cards in scope";
  }
  if (props.filteredCount === props.scopeCount) {
    return `${props.filteredCount} cards in scope`;
  }
  const missingInView = props.scopeStats?.missingCount ?? 0;
  return `${props.filteredCount} shown · ${props.scopeCount} in scope · ${missingInView} missing`;
});

const missingValueLabel = computed(() => {
  const value = props.scopeStats?.missingValue ?? 0;
  return value > 0 ? formatEuro(value) : "";
});
</script>

<template>
  <div class="collection-all-toolbar">
    <div class="collection-all-toolbar-row">
      <label class="collection-all-search">
        <span class="visually-hidden">Search in set</span>
        <input
          :value="searchQuery"
          type="search"
          placeholder="Search name or #…"
          autocomplete="off"
          @input="emit('update:searchQuery', $event.target.value)"
        >
      </label>
      <button
        type="button"
        class="btn btn-secondary btn-small collection-all-filters-btn"
        :aria-expanded="mobileFiltersOpen ? 'true' : 'false'"
        @click="emit('open-mobile-filters')"
      >
        Filters
      </button>
      <button
        type="button"
        class="btn btn-secondary btn-small"
        :class="{ 'is-active': bulkSelectMode }"
        @click="emit('toggle-bulk-mode')"
      >
        {{ bulkSelectMode ? "Done" : "Select" }}
      </button>
      <CollectionGalleryScaleControl
        class="collection-gallery-toolbar-scale"
        :model-value="cardScale"
        :options="scaleOptions"
        @update:model-value="emit('update:cardScale', $event)"
      />
    </div>

    <div class="collection-all-toolbar-row collection-all-lenses">
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

    <div class="collection-all-toolbar-row collection-all-summary">
      <p class="collection-gallery-toolbar-stats">{{ matchSummary }}</p>
      <p v-if="missingValueLabel" class="collection-all-missing-value">
        Missing value: {{ missingValueLabel }}
      </p>
    </div>

    <div v-if="bulkSelectMode && selectedCount" class="collection-bulk-bar">
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
