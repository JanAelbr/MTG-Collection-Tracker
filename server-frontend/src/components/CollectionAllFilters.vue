<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "../api";
import ArtStylePicker from "./ArtStylePicker.vue";
import ManaSymbols from "./ManaSymbols.vue";
import StorageLocationIcon from "./StorageLocationIcon.vue";
import { DECK_COLOR_ORDER } from "../utils/deckCards";
import { STORAGE_LOCATION_SECTIONS } from "../utils/storageLocationGroups";
import {
  COLLECTION_TYPE_LABELS,
  COLLECTION_TYPE_ORDER,
} from "../utils/collectionTypes";
import {
  COLLECTION_RARITY_LABELS,
  COLLECTION_RARITY_ORDER,
} from "../utils/collectionRarities";
import { SEARCH_ROLE_OPTIONS } from "../utils/deckPower";
import { hasSelectableArtStyles } from "../utils/format";

const props = defineProps({
  isAllView: { type: Boolean, default: true },
  isAllSetsView: { type: Boolean, default: false },
  artStyles: { type: Array, default: () => [] },
  setCode: { type: String, default: "" },
  artStyle: { type: String, default: "" },
  ownedFilter: { type: String, default: "owned" },
  foilFilter: { type: String, default: "all" },
  typeFilter: { type: String, default: "all" },
  colorFilters: { type: Array, default: () => [] },
  storageFilters: { type: Array, default: () => [] },
  roleFilters: { type: Array, default: () => [] },
  rarityFilter: { type: String, default: "all" },
  cmcMin: { type: String, default: "" },
  cmcMax: { type: String, default: "" },
  priceMin: { type: String, default: "" },
  priceMax: { type: String, default: "" },
  powerMin: { type: String, default: "" },
  toughnessMin: { type: String, default: "" },
  allCardsSort: { type: String, default: "value" },
  allCardsSortDir: { type: String, default: "desc" },
  showSort: { type: Boolean, default: true },
  /** collection: number/value; search: newest/name/value/cmc */
  sortMode: { type: String, default: "collection" },
  showStorageFilter: { type: Boolean, default: true },
  showRoleFilter: { type: Boolean, default: false },
  /** When false, hide the Unowned ownership option (search uses Owned / All only). */
  showUnownedFilter: { type: Boolean, default: true },
  /** When false, ownership controls are provided elsewhere (e.g. search toolbar). */
  showOwnershipFilter: { type: Boolean, default: true },
  priceIssuesOnly: { type: Boolean, default: false },
  priceIssueCount: { type: Number, default: 0 },
  showPriceHealth: { type: Boolean, default: false },
  isTableView: { type: Boolean, default: false },
});

const emit = defineEmits([
  "update:artStyle",
  "set-owned-filter",
  "set-foil-filter",
  "type-filter-change",
  "toggle-color-filter",
  "clear-color-filters",
  "toggle-storage-filter",
  "clear-storage-filters",
  "toggle-role-filter",
  "clear-role-filters",
  "rarity-filter-change",
  "update:cmcMin",
  "update:cmcMax",
  "update:priceMin",
  "update:priceMax",
  "update:powerMin",
  "update:toughnessMin",
  "update-sort",
  "toggle-sort-dir",
  "update:priceIssuesOnly",
  "open-art-style-editor",
]);

const storageLocations = ref([]);
const storageLoading = ref(false);

const sectionedStorageLocations = computed(() =>
  STORAGE_LOCATION_SECTIONS.map((section) => ({
    ...section,
    locations: storageLocations.value.filter(
      (location) => location.locationType === section.type,
    ),
  })).filter((section) => section.locations.length),
);

const showArtStylePicker = computed(() => hasSelectableArtStyles(props.artStyles));

onMounted(async () => {
  storageLoading.value = true;
  try {
    const payload = await api.listStorageLocations();
    storageLocations.value = payload.locations || payload || [];
  } finally {
    storageLoading.value = false;
  }
});
</script>

<template>
  <div class="collection-all-filters">
    <div v-if="!isAllSetsView" class="filter-sidebar-section">
      <div class="filter-sidebar-label-row">
        <p class="filter-sidebar-label">Art style</p>
        <button
          v-if="isAllView && !isAllSetsView"
          type="button"
          class="filter-sidebar-edit-link"
          title="Edit art styles"
          aria-label="Edit art styles"
          @click="emit('open-art-style-editor')"
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
        </button>
      </div>
      <ArtStylePicker
        v-if="showArtStylePicker"
        :model-value="artStyle"
        layout="list"
        :set-code="setCode"
        :art-styles="artStyles"
        @update:model-value="emit('update:artStyle', $event)"
      />
    </div>

    <div v-if="isAllView && !isTableView" class="filter-sidebar-section filter-sidebar-section--compact-filters">
      <div v-if="showOwnershipFilter" class="filter-sidebar-compact-filter">
        <p class="filter-sidebar-label">Ownership</p>
        <div
          class="button-group collection-ownership-group"
          :class="{ 'collection-ownership-group--binary': !showUnownedFilter }"
        >
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
            v-if="showUnownedFilter"
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

    <div v-if="isAllView && isTableView" class="filter-sidebar-section">
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

    <div v-if="isAllView && !isTableView && showStorageFilter" class="filter-sidebar-section">
      <div class="filter-sidebar-label-row">
        <p class="filter-sidebar-label">Storage</p>
        <button
          v-if="storageFilters.length"
          type="button"
          class="filter-button collection-storage-filter-clear"
          @click="emit('clear-storage-filters')"
        >
          Clear
        </button>
      </div>
      <p v-if="storageLoading" class="collection-storage-filter-status">Loading…</p>
      <div v-else class="collection-storage-filter-list">
        <template v-for="section in sectionedStorageLocations" :key="section.type">
          <p class="collection-storage-filter-section">{{ section.label }}</p>
          <label
            v-for="location in section.locations"
            :key="location.slug"
            class="collection-storage-filter-item"
          >
            <input
              type="checkbox"
              :checked="storageFilters.includes(location.slug)"
              @change="emit('toggle-storage-filter', location.slug)"
            >
            <StorageLocationIcon :location-type="location.locationType" />
            <span class="collection-storage-filter-label">{{ location.label }}</span>
          </label>
        </template>
      </div>
    </div>

    <div v-if="isAllView && !isTableView && showRoleFilter" class="filter-sidebar-section">
      <div class="filter-sidebar-label-row">
        <p class="filter-sidebar-label">Role</p>
        <button
          v-if="roleFilters.length"
          type="button"
          class="filter-button collection-storage-filter-clear"
          @click="emit('clear-role-filters')"
        >
          Clear
        </button>
      </div>
      <div class="collection-storage-filter-list collection-role-filter-list">
        <label
          v-for="role in SEARCH_ROLE_OPTIONS"
          :key="role.id"
          class="collection-storage-filter-item"
        >
          <input
            type="checkbox"
            :checked="roleFilters.includes(role.id)"
            @change="emit('toggle-role-filter', role.id)"
          >
          <span class="collection-storage-filter-label">{{ role.label }}</span>
        </label>
      </div>
    </div>

    <div v-if="isAllView && !isTableView" class="filter-sidebar-section">
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

    <div v-if="isAllView && !isTableView" class="filter-sidebar-section">
      <p class="filter-sidebar-label">Rarity</p>
      <label class="manager-filter collection-type-filter">
        <select :value="rarityFilter" @change="emit('rarity-filter-change', $event)">
          <option value="all">All rarities</option>
          <option v-for="rarity in COLLECTION_RARITY_ORDER" :key="rarity" :value="rarity">
            {{ COLLECTION_RARITY_LABELS[rarity] }}
          </option>
        </select>
      </label>

      <p class="filter-sidebar-label">Mana value</p>
      <div class="collection-detail-filter-grid">
        <label class="manager-filter">
          <span>Min CMC</span>
          <input
            :value="cmcMin"
            type="number"
            min="0"
            step="1"
            inputmode="numeric"
            placeholder="Any"
            @input="emit('update:cmcMin', $event.target.value)"
          >
        </label>
        <label class="manager-filter">
          <span>Max CMC</span>
          <input
            :value="cmcMax"
            type="number"
            min="0"
            step="1"
            inputmode="numeric"
            placeholder="Any"
            @input="emit('update:cmcMax', $event.target.value)"
          >
        </label>
      </div>

      <p class="filter-sidebar-label">Price (€)</p>
      <div class="collection-detail-filter-grid">
        <label class="manager-filter">
          <span>≥ Min</span>
          <input
            :value="priceMin"
            type="number"
            min="0"
            step="0.01"
            inputmode="decimal"
            placeholder="Any"
            @input="emit('update:priceMin', $event.target.value)"
          >
        </label>
        <label class="manager-filter">
          <span>≤ Max</span>
          <input
            :value="priceMax"
            type="number"
            min="0"
            step="0.01"
            inputmode="decimal"
            placeholder="Any"
            @input="emit('update:priceMax', $event.target.value)"
          >
        </label>
      </div>

      <p class="filter-sidebar-label">Power / toughness</p>
      <div class="collection-detail-filter-grid">
        <label class="manager-filter">
          <span>Min power</span>
          <input
            :value="powerMin"
            type="number"
            min="0"
            step="1"
            inputmode="numeric"
            placeholder="Any"
            @input="emit('update:powerMin', $event.target.value)"
          >
        </label>
        <label class="manager-filter">
          <span>Min toughness</span>
          <input
            :value="toughnessMin"
            type="number"
            min="0"
            step="1"
            inputmode="numeric"
            placeholder="Any"
            @input="emit('update:toughnessMin', $event.target.value)"
          >
        </label>
      </div>
    </div>

    <div v-if="isAllView && showPriceHealth" class="filter-sidebar-section">
      <p class="filter-sidebar-label">Price health</p>
      <label class="manager-price-health-toggle">
        <input
          type="checkbox"
          :checked="priceIssuesOnly"
          @change="emit('update:priceIssuesOnly', $event.target.checked)"
        >
        <span>Show owned cards with URL/price issues only</span>
      </label>
      <p v-if="priceIssueCount" class="manager-price-health-count">
        {{ priceIssueCount }} owned
        {{ priceIssueCount === 1 ? "card has" : "cards have" }}
        pricing issues in this set.
      </p>
    </div>

    <div v-if="showSort && !isTableView" class="filter-sidebar-section">
      <label class="manager-filter">
        <span>Sort by</span>
        <div class="collection-sort-row">
          <select :value="allCardsSort" @change="emit('update-sort', $event)">
            <template v-if="sortMode === 'search'">
              <option value="newest">Newest set</option>
              <option value="name">Name</option>
              <option value="value">Value</option>
              <option value="cmc">CMC</option>
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
    </div>
  </div>
</template>
