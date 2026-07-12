<script setup>
import ArtStylePicker from "./ArtStylePicker.vue";
import ManaSymbols from "./ManaSymbols.vue";
import { DECK_COLOR_ORDER } from "../utils/deckCards";
import {
  COLLECTION_TYPE_LABELS,
  COLLECTION_TYPE_ORDER,
} from "../utils/collectionTypes";

defineProps({
  isAllView: { type: Boolean, default: true },
  isAllSetsView: { type: Boolean, default: false },
  artStyles: { type: Array, default: () => [] },
  setCode: { type: String, default: "" },
  artStyle: { type: String, default: "" },
  managerArtStylesEditorLink: { type: Object, default: null },
  ownedFilter: { type: String, default: "owned" },
  foilFilter: { type: String, default: "all" },
  typeFilter: { type: String, default: "all" },
  colorFilters: { type: Array, default: () => [] },
  allCardsSort: { type: String, default: "value" },
  allCardsSortDir: { type: String, default: "desc" },
});

const emit = defineEmits([
  "update:artStyle",
  "set-owned-filter",
  "set-foil-filter",
  "type-filter-change",
  "toggle-color-filter",
  "clear-color-filters",
  "update-sort",
  "toggle-sort-dir",
]);
</script>

<template>
  <div class="collection-all-filters">
    <div v-if="!isAllSetsView && artStyles.length" class="filter-sidebar-section">
      <div class="filter-sidebar-label-row">
        <p class="filter-sidebar-label">Art style</p>
        <RouterLink
          v-if="isAllView && managerArtStylesEditorLink"
          :to="managerArtStylesEditorLink"
          class="filter-sidebar-edit-link"
          title="Edit art styles"
          aria-label="Edit art styles in Set Manager"
        >
          <svg class="filter-sidebar-edit-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
              d="M4 20h4l10.5-10.5a1.8 1.8 0 0 0 0-2.5L16 4.5a1.8 1.8 0 0 0-2.5 0L3 15v5z"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linejoin="round"
            />
            <path
              d="M13.5 6.5l4 4"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
        </RouterLink>
      </div>
      <ArtStylePicker
        :model-value="artStyle"
        layout="list"
        :set-code="setCode"
        :art-styles="artStyles"
        @update:model-value="emit('update:artStyle', $event)"
      />
    </div>

    <div v-if="isAllView" class="filter-sidebar-section filter-sidebar-section--compact-filters">
      <div class="filter-sidebar-compact-filter">
        <p class="filter-sidebar-label">Ownership</p>
        <div class="button-group collection-ownership-group">
          <button
            type="button"
            class="filter-button"
            :class="{ active: ownedFilter === 'owned' }"
            @click="emit('set-owned-filter', 'owned')"
          >
            Owned
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: ownedFilter === 'all' }"
            @click="emit('set-owned-filter', 'all')"
          >
            All
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: ownedFilter === 'unowned' }"
            @click="emit('set-owned-filter', 'unowned')"
          >
            Unowned
          </button>
        </div>
      </div>

      <div class="filter-sidebar-compact-filter">
        <p class="filter-sidebar-label">Finish</p>
        <div class="button-group collection-finish-group">
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'all' }"
            @click="emit('set-foil-filter', 'all')"
          >
            All
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'nonfoil' }"
            @click="emit('set-foil-filter', 'nonfoil')"
          >
            Non-foil
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'foil' }"
            @click="emit('set-foil-filter', 'foil')"
          >
            Foil
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: foilFilter === 'etched' }"
            @click="emit('set-foil-filter', 'etched')"
          >
            Etched
          </button>
        </div>
      </div>
    </div>

    <div v-if="isAllView" class="filter-sidebar-section">
      <p class="filter-sidebar-label">Type</p>
      <label class="manager-filter collection-type-filter">
        <select :value="typeFilter" @change="emit('type-filter-change', $event)">
          <option value="all">All types</option>
          <option v-for="type in COLLECTION_TYPE_ORDER" :key="type" :value="type">
            {{ COLLECTION_TYPE_LABELS[type] }}
          </option>
        </select>
      </label>

      <p class="filter-sidebar-label">Color</p>
      <div class="button-group collection-color-group">
        <button
          v-for="color in DECK_COLOR_ORDER"
          :key="color"
          type="button"
          class="filter-button collection-color-filter"
          :class="{ active: colorFilters.includes(color) }"
          :title="color === 'C' ? 'Colorless' : color"
          @click="emit('toggle-color-filter', color)"
        >
          <ManaSymbols :colors="color === 'C' ? [] : [color]" :size="18" />
        </button>
        <button
          v-if="colorFilters.length"
          type="button"
          class="filter-button"
          @click="emit('clear-color-filters')"
        >
          Clear
        </button>
      </div>
    </div>

    <div v-if="isAllView" class="filter-sidebar-section">
      <label class="manager-filter">
        <span>Sort by</span>
        <div class="collection-sort-row">
          <select :value="allCardsSort" @change="emit('update-sort', $event)">
            <option value="number">Collector number</option>
            <option value="value">Value</option>
            <option value="changePct">Price change (%)</option>
            <option value="changeEuro">Price change (€)</option>
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
    </div>
  </div>
</template>
