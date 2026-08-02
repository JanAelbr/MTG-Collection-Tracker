<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api";
import ArtStylePicker from "./ArtStylePicker.vue";
import FilterSidebarGroup from "./FilterSidebarGroup.vue";
import ManaSymbols from "./ManaSymbols.vue";
import MultiBrowseSelect from "./MultiBrowseSelect.vue";
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
import { SEARCH_ROLE_OPTIONS, formatCardRoleLabel } from "../utils/deckPower";
import {
  getFilterSectionPrefs,
  setFilterSectionExpanded,
} from "../utils/filterStorage";
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
  /** exact: selected pips must equal color identity; includes: any selected casting color */
  colorMode: { type: String, default: "exact" },
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
  showFinishFilter: { type: Boolean, default: true },
  /** When false, hide the Unowned ownership option (search uses Owned / All only). */
  showUnownedFilter: { type: Boolean, default: true },
  /** When false, ownership controls are provided elsewhere (e.g. search toolbar). */
  showOwnershipFilter: { type: Boolean, default: true },
  priceIssuesOnly: { type: Boolean, default: false },
  priceIssueCount: { type: Number, default: 0 },
  showPriceHealth: { type: Boolean, default: false },
  isTableView: { type: Boolean, default: false },
  /** When false, hide the Art style filter section (e.g. all-sets scope). */
  showArtStyleSection: { type: Boolean, default: true },
  /** When true, the art-style edit control is shown as active. */
  artStyleEditing: { type: Boolean, default: false },
  /** When false, hide the pencil that opens art-style rules editing. */
  showArtStyleEdit: { type: Boolean, default: true },
});

const emit = defineEmits([
  "update:artStyle",
  "set-owned-filter",
  "set-foil-filter",
  "type-filter-change",
  "toggle-color-filter",
  "clear-color-filters",
  "update:colorMode",
  "toggle-storage-filter",
  "clear-storage-filters",
  "set-storage-filters",
  "toggle-role-filter",
  "clear-role-filters",
  "set-role-filters",
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
const sectionExpanded = reactive(getFilterSectionPrefs());

const sectionedStorageLocations = computed(() =>
  STORAGE_LOCATION_SECTIONS.map((section) => ({
    ...section,
    locations: storageLocations.value.filter(
      (location) => location.locationType === section.type,
    ),
  })).filter((section) => section.locations.length),
);

const storageSelectOptions = computed(() =>
  sectionedStorageLocations.value.flatMap((section) =>
    section.locations.map((location) => ({
      value: location.slug,
      label: location.label,
      group: section.label,
      locationType: location.locationType,
    })),
  ),
);

const roleSelectOptions = computed(() =>
  SEARCH_ROLE_OPTIONS.map((role) => ({
    value: role.id,
    label: role.label,
  })),
);

const showArtStylePicker = computed(() => hasSelectableArtStyles(props.artStyles));

const showCardGroup = computed(() => props.isAllView && !props.isTableView);

const showRoleGroup = computed(
  () => props.isAllView && !props.isTableView && props.showRoleFilter,
);

const showStorageGroup = computed(
  () => props.isAllView && !props.isTableView && props.showStorageFilter,
);

const showDetailsGroup = computed(() => props.isAllView && !props.isTableView);

const cardGroupSummary = computed(() => {
  const parts = [];
  if (props.typeFilter && props.typeFilter !== "all") {
    parts.push(COLLECTION_TYPE_LABELS[props.typeFilter] || props.typeFilter);
  }
  if (props.colorFilters.length) {
    parts.push(props.colorFilters.join(""));
  }
  return parts.join(" · ");
});

const roleGroupSummary = computed(() => {
  if (!props.roleFilters.length) {
    return "";
  }
  if (props.roleFilters.length === 1) {
    return formatCardRoleLabel(props.roleFilters[0]);
  }
  return `${props.roleFilters.length} roles`;
});

const storageGroupSummary = computed(() => {
  if (!props.storageFilters.length) {
    return "";
  }
  if (props.storageFilters.length === 1) {
    const match = storageSelectOptions.value.find(
      (option) => option.value === props.storageFilters[0],
    );
    return match?.label || props.storageFilters[0];
  }
  return `${props.storageFilters.length} locations`;
});

const detailsGroupSummary = computed(() => {
  const parts = [];
  if (props.rarityFilter && props.rarityFilter !== "all") {
    parts.push(COLLECTION_RARITY_LABELS[props.rarityFilter] || props.rarityFilter);
  }
  if (props.cmcMin || props.cmcMax) {
    parts.push(`CMC ${props.cmcMin || "…"}–${props.cmcMax || "…"}`);
  }
  if (props.priceMin || props.priceMax) {
    parts.push(`€${props.priceMin || "…"}–${props.priceMax || "…"}`);
  }
  if (props.powerMin || props.toughnessMin) {
    parts.push(`P/T ≥${props.powerMin || "0"}/≥${props.toughnessMin || "0"}`);
  }
  return parts.join(" · ");
});

function toggleSection(id) {
  const next = !sectionExpanded[id];
  sectionExpanded[id] = next;
  setFilterSectionExpanded(id, next);
}

function onStorageFiltersChange(values) {
  emit("set-storage-filters", Array.isArray(values) ? [...values] : []);
}

function onRoleFiltersChange(values) {
  emit("set-role-filters", Array.isArray(values) ? [...values] : []);
}

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
    <div v-if="showArtStyleSection && !isAllSetsView" class="filter-sidebar-section">
      <div class="filter-sidebar-label-row">
        <p class="filter-sidebar-label">Art style</p>
        <button
          v-if="showArtStyleEdit && isAllView && !isAllSetsView"
          type="button"
          class="filter-sidebar-edit-link"
          :class="{ active: artStyleEditing }"
          :title="artStyleEditing ? 'Close art style editor' : 'Edit art styles'"
          :aria-label="artStyleEditing ? 'Close art style editor' : 'Edit art styles'"
          :aria-pressed="artStyleEditing ? 'true' : 'false'"
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

    <div
      v-if="isAllView && !isTableView && (showOwnershipFilter || showFinishFilter)"
      class="filter-sidebar-section filter-sidebar-section--compact-filters"
    >
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

      <div v-if="showFinishFilter" class="filter-sidebar-compact-filter">
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

    <div v-if="isAllView && isTableView && showFinishFilter" class="filter-sidebar-section">
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

    <FilterSidebarGroup
      v-if="showCardGroup"
      title="Card"
      :summary="cardGroupSummary"
      :expanded="sectionExpanded.card"
      @toggle="toggleSection('card')"
    >
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
      <label class="manager-price-health-toggle collection-color-mode-toggle">
        <input
          type="checkbox"
          :checked="colorMode === 'exact'"
          @change="emit('update:colorMode', $event.target.checked ? 'exact' : 'includes')"
        >
        <span>Exact color identity only</span>
      </label>
    </FilterSidebarGroup>

    <FilterSidebarGroup
      v-if="showRoleGroup"
      title="Role"
      :summary="roleGroupSummary"
      :expanded="sectionExpanded.role"
      @toggle="toggleSection('role')"
    >
      <MultiBrowseSelect
        class="collection-multi-filter-select"
        :model-value="roleFilters"
        :options="roleSelectOptions"
        filterable
        portal-panel
        placeholder="Any role"
        aria-label="Filter by card role"
        @update:model-value="onRoleFiltersChange"
      />
    </FilterSidebarGroup>

    <FilterSidebarGroup
      v-if="showStorageGroup"
      title="Storage"
      :summary="storageGroupSummary"
      :expanded="sectionExpanded.storage"
      @toggle="toggleSection('storage')"
    >
      <p v-if="storageLoading" class="collection-storage-filter-status">Loading…</p>
      <MultiBrowseSelect
        v-else
        class="collection-multi-filter-select"
        :model-value="storageFilters"
        :options="storageSelectOptions"
        filterable
        portal-panel
        placeholder="Any storage"
        aria-label="Filter by storage location"
        @update:model-value="onStorageFiltersChange"
      />
    </FilterSidebarGroup>

    <FilterSidebarGroup
      v-if="showDetailsGroup"
      title="Details"
      :summary="detailsGroupSummary"
      :expanded="sectionExpanded.details"
      @toggle="toggleSection('details')"
    >
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
    </FilterSidebarGroup>

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
              <option value="power">Power</option>
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
    </div>
  </div>
</template>
