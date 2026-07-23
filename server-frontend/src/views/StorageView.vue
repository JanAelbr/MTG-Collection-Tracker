<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { api } from "../api";
import BrowseSelect from "../components/BrowseSelect.vue";
import CollectionCardGrid from "../components/CollectionCardGrid.vue";
import CollectionGalleryScaleControl from "../components/CollectionGalleryScaleControl.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import StorageLocationIcon from "../components/StorageLocationIcon.vue";
import StorageBreakdownPanel from "../components/StorageBreakdownPanel.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import VirtualizedStorageTable from "../components/VirtualizedStorageTable.vue";
import { savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { filterCollectionCards } from "../utils/collectionFilters";
import {
  defaultCollectionSortDir,
  groupCollectionCardsBySet,
  sortCollectionCards,
} from "../utils/collectionSort";
import { cardDisplayName } from "../utils/finishes";
import { formatEuro, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import {
  storageFiltersFromRoute,
  storageLocationFromRoute,
  storageRouteQuery,
} from "../utils/storageScope";
import { STORAGE_LOCATION_SECTIONS } from "../utils/storageLocationGroups";

const route = useRoute();
const router = useRouter();

const {
  settings: pricingSettings,
  collectionCardScale,
  fetchPricingSettings: loadPricingSettings,
} = usePricingSettings();

const locations = ref([]);
const selectedSlug = ref("");
const cardsPayload = ref(null);
const breakdownPayload = ref(null);
const setsCatalog = ref([]);
const defaultStorageSaving = ref(false);
const { loading: loadingCards, run: runCardsLoad } = useAsyncLoad();
const { loading: loadingBreakdown, run: runBreakdownLoad } = useAsyncLoad();

const searchQuery = ref("");
const foilFilter = ref("all");
const setFilter = ref("");
const cardsSort = ref("value");
const cardsSortDir = ref(defaultCollectionSortDir("value"));
const viewMode = ref("gallery");
const groupBySet = ref(true);
/** Set codes currently expanded; empty = all collapsed (default). */
const expandedSetCodes = ref(new Set());
const syncingRoute = ref(false);

const editor = reactive({
  open: false,
  locationType: "storage",
  label: "",
  description: "",
});

const inlineLabel = ref("");
const inlineDescription = ref("");
const inlineSaving = ref(false);
const inlineError = ref("");
const inlineLabelRef = ref(null);
const inlineDescRef = ref(null);

const FINISH_OPTIONS = [
  { id: "all", label: "All finishes" },
  { id: "nonfoil", label: "Nonfoil" },
  { id: "foil", label: "Foil" },
  { id: "etched", label: "Etched" },
];

const SORT_OPTIONS = [
  { id: "value", label: "Value" },
  { id: "name", label: "Name" },
  { id: "number", label: "Number" },
  { id: "set", label: "Set" },
  { id: "artStyle", label: "Art style" },
  { id: "finish", label: "Finish" },
  { id: "copies", label: "Copies" },
];

const selectedLocation = computed(() =>
  locations.value.find((item) => item.slug === selectedSlug.value),
);

const canInlineEdit = computed(() => {
  const type = selectedLocation.value?.locationType;
  return type === "storage" || type === "binder";
});

const isDeckLocation = computed(
  () => selectedLocation.value?.locationType === "deck",
);

const visibleLocations = computed(() =>
  locations.value.filter(
    (location) => location.cardCount > 0 || location.isCustom || location.isSystem,
  ),
);

const LOCATION_TYPE_SECTIONS = STORAGE_LOCATION_SECTIONS.map((section) => {
  if (section.type === "deck") {
    return {
      ...section,
      collapsible: true,
      defaultCollapsed: true,
    };
  }
  return {
    ...section,
    canCreate: true,
  };
});

const sectionExpanded = reactive(
  Object.fromEntries(
    LOCATION_TYPE_SECTIONS.filter((section) => section.collapsible).map((section) => [
      section.type,
      !section.defaultCollapsed,
    ]),
  ),
);

function isSectionExpanded(section) {
  if (!section.collapsible) {
    return true;
  }
  return sectionExpanded[section.type] ?? true;
}

function toggleSection(section) {
  if (!section.collapsible) {
    return;
  }
  sectionExpanded[section.type] = !sectionExpanded[section.type];
}

const groupedVisibleLocations = computed(() =>
  LOCATION_TYPE_SECTIONS.map((section) => ({
    ...section,
    locations: visibleLocations.value.filter(
      (location) => location.locationType === section.type,
    ),
  })).filter((section) => section.locations.length > 0 || section.canCreate),
);

function createLocationLabel(sectionType) {
  return sectionType === "binder" ? "New binder" : "New storage";
}

function isDefaultStorage(location) {
  if (!location || location.locationType !== "storage") {
    return false;
  }
  const current = pricingSettings.value?.defaultStorageLocation ?? "storage:general";
  return location.slug === current;
}

async function toggleDefaultStorage(location) {
  if (!location || location.locationType !== "storage" || defaultStorageSaving.value) {
    return;
  }
  if (isDefaultStorage(location)) {
    return;
  }
  defaultStorageSaving.value = true;
  try {
    await savePricingSettings({ defaultStorageLocation: location.slug });
  } catch (error) {
    window.alert(error.message || "Could not set default storage.");
  } finally {
    defaultStorageSaving.value = false;
  }
}

function lineTotal(card) {
  if (card.currentValue == null || Number.isNaN(card.currentValue)) {
    return null;
  }
  return card.currentValue * card.copyCount;
}

function applyFiltersFromRoute(routeRef = route) {
  const filters = storageFiltersFromRoute(routeRef);
  searchQuery.value = filters.searchQuery;
  foilFilter.value = filters.foilFilter;
  setFilter.value = filters.setFilter;
  cardsSort.value = filters.sort;
  cardsSortDir.value = filters.sortDir;
  viewMode.value = filters.viewMode;
  groupBySet.value = filters.groupBySet;
}

function pushStorageQuery() {
  const nextQuery = storageRouteQuery({
    location: selectedSlug.value,
    foilFilter: foilFilter.value,
    setFilter: setFilter.value,
    sort: cardsSort.value,
    sortDir: cardsSortDir.value,
    searchQuery: searchQuery.value,
    viewMode: viewMode.value,
    groupBySet: groupBySet.value,
  });
  const current = route.query || {};
  const keys = new Set([...Object.keys(current), ...Object.keys(nextQuery)]);
  let changed = false;
  for (const key of keys) {
    if (String(current[key] ?? "") !== String(nextQuery[key] ?? "")) {
      changed = true;
      break;
    }
  }
  if (!changed) {
    return;
  }
  syncingRoute.value = true;
  router.replace({ query: nextQuery }).finally(() => {
    syncingRoute.value = false;
  });
}

const locationCards = computed(() => {
  const cards = cardsPayload.value?.cards || [];
  return cards.map((card) => ({
    ...card,
    ownedQty: card.copyCount,
  }));
});

const setsByCode = computed(() => {
  const map = new Map();
  for (const set of setsCatalog.value) {
    const code = String(set.setCode || "").trim().toUpperCase();
    if (code) {
      map.set(code, set);
    }
  }
  return map;
});

const breakdownSetIcons = computed(() => {
  const icons = {};
  for (const [code, set] of setsByCode.value) {
    icons[code] = resolveSetIconUri(set);
  }
  return icons;
});

const breakdownSetLabels = computed(() => {
  const labels = {};
  for (const [code] of setsByCode.value) {
    labels[code] = setLabelForCode(code);
  }
  for (const row of breakdownPayload.value?.bySet || []) {
    const code = String(row.setCode || "").trim().toUpperCase();
    if (code && !labels[code]) {
      labels[code] = setLabelForCode(code);
    }
  }
  return labels;
});

const isBreakdownView = computed(() => viewMode.value === "breakdown");

const setCodesInLocation = computed(() => {
  const codes = new Set();
  for (const card of locationCards.value) {
    const code = String(card.setCode || "").trim().toUpperCase();
    if (code) {
      codes.add(code);
    }
  }
  return [...codes].sort((left, right) => left.localeCompare(right));
});

function setMetaForCode(code) {
  const normalized = String(code || "").trim().toUpperCase();
  if (!normalized) {
    return null;
  }
  return setsByCode.value.get(normalized) || { setCode: normalized, label: normalized };
}

function setLabelForCode(code) {
  return setShortName(setMetaForCode(code)) || String(code || "").toUpperCase();
}

function setIconForCode(code) {
  return resolveSetIconUri(setMetaForCode(code));
}

const setFilterOptions = computed(() => {
  const options = [
    {
      value: "",
      label: "All sets",
      iconSrc: null,
      searchText: "all sets",
    },
  ];
  for (const code of setCodesInLocation.value) {
    const set = setMetaForCode(code);
    const label = setShortName(set) || code;
    options.push({
      value: code,
      label,
      iconSrc: resolveSetIconUri(set),
      searchText: [code, label, set?.label].filter(Boolean).join(" "),
    });
  }
  return options;
});

const filteredCards = computed(() =>
  filterCollectionCards(locationCards.value, {
    setCode: setFilter.value || "All",
    searchQuery: searchQuery.value,
    foilFilter: foilFilter.value,
    ownedFilter: "all",
  }),
);

const sortedCards = computed(() =>
  sortCollectionCards(filteredCards.value, {
    sort: cardsSort.value,
    dir: cardsSortDir.value,
    allowSet: true,
  }),
);

const setGroups = computed(() => {
  if (!groupBySet.value) {
    return [];
  }
  return groupCollectionCardsBySet(filteredCards.value, {
    sort: cardsSort.value,
    dir: cardsSortDir.value,
    allowSet: true,
  }).map((group) => {
    let copyCount = 0;
    let totalValue = 0;
    let hasPriced = false;
    for (const card of group.cards) {
      copyCount += Number(card.copyCount) || 0;
      const line = lineTotal(card);
      if (line != null) {
        totalValue += line;
        hasPriced = true;
      }
    }
    return {
      ...group,
      printCount: group.cards.length,
      copyCount,
      totalValue: hasPriced ? totalValue : null,
    };
  });
});

const anySetGroupExpanded = computed(() =>
  setGroups.value.some((group) => expandedSetCodes.value.has(group.setCode)),
);

function defaultExpandedSetCodes(groups = setGroups.value) {
  if (groups.length === 1) {
    return new Set([groups[0].setCode]);
  }
  return new Set();
}

function applyDefaultSetGroupExpansion() {
  expandedSetCodes.value = defaultExpandedSetCodes();
}

function isSetGroupExpanded(setCode) {
  return expandedSetCodes.value.has(setCode);
}

function toggleSetGroup(setCode) {
  const next = new Set(expandedSetCodes.value);
  if (next.has(setCode)) {
    next.delete(setCode);
  } else {
    next.add(setCode);
  }
  expandedSetCodes.value = next;
}

function expandAllSetGroups() {
  expandedSetCodes.value = new Set(setGroups.value.map((group) => group.setCode));
}

function collapseAllSetGroups() {
  expandedSetCodes.value = new Set();
}

function setGroupMetaText(group) {
  const printLabel = `${group.printCount} ${group.printCount === 1 ? "print" : "prints"}`;
  if (group.totalValue == null) {
    return printLabel;
  }
  return `${printLabel} · ${formatEuro(group.totalValue)}`;
}

/**
 * "Expand all groups" can otherwise dump every owned card across every set
 * into the DOM at once. Small groups keep their natural auto-fit height
 * (most groups); large ones get a bounded, truly virtualized viewport.
 */
const GROUP_VIRTUALIZE_THRESHOLD = 40;
const GROUP_TABLE_MAX_VISIBLE_ROWS = 12;

function isLargeSetGroup(group) {
  return (group?.cards?.length || 0) > GROUP_VIRTUALIZE_THRESHOLD;
}

function setGroupTableRowVar(group) {
  return isLargeSetGroup(group)
    ? Math.min(group.cards.length, GROUP_TABLE_MAX_VISIBLE_ROWS)
    : group.cards.length;
}

const setGroupCodesKey = computed(() =>
  setGroups.value.map((group) => group.setCode).join("|"),
);

const scopePrintCount = computed(() => locationCards.value.length);

const matchSummaryText = computed(() => {
  const shown = sortedCards.value.length;
  const scope = scopePrintCount.value;
  if (!scope) {
    return "No prints in this location";
  }
  if (shown === scope) {
    return `${shown} prints`;
  }
  return `${shown} shown · ${scope} prints`;
});

async function loadLocations(preferredSlug = "") {
  const payload = await api.listStorageLocations();
  locations.value = payload.locations || [];
  const nextSlug =
    preferredSlug ||
    selectedSlug.value ||
    payload.defaultLocation ||
    locations.value[0]?.slug ||
    "";
  selectedSlug.value = nextSlug;
}

async function loadCards() {
  if (viewMode.value === "breakdown") {
    return;
  }
  if (!selectedSlug.value) {
    cardsPayload.value = null;
    return;
  }
  await runCardsLoad(async () => {
    cardsPayload.value = await api.getStorageLocationCards(selectedSlug.value);
  });
}

async function loadBreakdown() {
  if (!selectedSlug.value) {
    breakdownPayload.value = null;
    return;
  }
  await runBreakdownLoad(async () => {
    breakdownPayload.value = await api.getStorageBreakdown(selectedSlug.value);
  });
}

function openCreateEditor(locationType = "storage") {
  editor.open = true;
  editor.locationType = locationType;
  editor.label = "";
  editor.description = "";
}

function closeEditor() {
  editor.open = false;
}

async function saveEditor() {
  const label = editor.label.trim();
  if (!label) {
    return;
  }
  const created = await api.createStorageLocation({
    label,
    description: editor.description.trim(),
    locationType: editor.locationType,
  });
  closeEditor();
  await loadLocations(created.slug);
}

function syncInlineFields(location) {
  if (!location) {
    inlineLabel.value = "";
    inlineDescription.value = "";
    return;
  }
  inlineLabel.value = location.label;
  inlineDescription.value = location.description || "";
  inlineError.value = "";
}

async function saveInlineLabel() {
  const location = selectedLocation.value;
  if (!location || !canInlineEdit.value || inlineSaving.value) {
    return;
  }
  const label = inlineLabel.value.trim();
  if (!label) {
    inlineLabel.value = location.label;
    inlineError.value = "Name is required.";
    return;
  }
  if (label === location.label) {
    return;
  }
  await saveInlineFields({ label });
}

async function saveInlineDescription() {
  const location = selectedLocation.value;
  if (!location || !canInlineEdit.value || inlineSaving.value) {
    return;
  }
  const description = inlineDescription.value.trim();
  if (description === (location.description || "")) {
    return;
  }
  await saveInlineFields({ description });
}

async function saveInlineFields(body) {
  const location = selectedLocation.value;
  if (!location) {
    return;
  }
  inlineSaving.value = true;
  inlineError.value = "";
  try {
    await api.updateStorageLocation(location.slug, body);
    await loadLocations(location.slug);
    syncInlineFields(selectedLocation.value);
  } catch (error) {
    inlineError.value = error.message || "Could not save.";
    syncInlineFields(location);
  } finally {
    inlineSaving.value = false;
  }
}

function onInlineLabelKeydown(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    inlineLabelRef.value?.blur();
  }
  if (event.key === "Escape") {
    inlineLabel.value = selectedLocation.value?.label || "";
    inlineLabelRef.value?.blur();
  }
}

function onInlineDescKeydown(event) {
  if (event.key === "Escape") {
    inlineDescription.value = selectedLocation.value?.description || "";
    inlineDescRef.value?.blur();
  }
}

async function deleteLocation(location) {
  if (!location.canDelete) {
    return;
  }
  if (!window.confirm(`Delete empty storage "${location.label}"?`)) {
    return;
  }
  await api.deleteStorageLocation(location.slug);
  await loadLocations();
}

async function removeOneCopy(card) {
  const instanceId = card.instanceIds?.[card.instanceIds.length - 1];
  if (!instanceId) {
    return;
  }
  if (!window.confirm(`Remove one copy of ${cardDisplayName(card)}?`)) {
    return;
  }
  await api.deleteInstance(instanceId);
  await loadLocations(selectedSlug.value);
}

function selectLocation(slug) {
  if (slug !== selectedSlug.value) {
    searchQuery.value = "";
    setFilter.value = "";
  }
  selectedSlug.value = slug;
}

function onSortChange(event) {
  const next = event.target.value;
  cardsSort.value = next;
  cardsSortDir.value = defaultCollectionSortDir(next);
}

function onColumnSort(field) {
  if (!field) {
    return;
  }
  if (cardsSort.value === field) {
    cardsSortDir.value = cardsSortDir.value === "asc" ? "desc" : "asc";
    return;
  }
  cardsSort.value = field;
  cardsSortDir.value = defaultCollectionSortDir(field);
}

function toggleSortDir() {
  cardsSortDir.value = cardsSortDir.value === "asc" ? "desc" : "asc";
}

function setViewMode(mode) {
  if (viewMode.value !== mode) {
    viewMode.value = mode;
  }
}

function toggleGroupBySet() {
  groupBySet.value = !groupBySet.value;
  if (groupBySet.value) {
    applyDefaultSetGroupExpansion();
  }
}

async function onCardScaleChange(scale) {
  await savePricingSettings({ collectionCardScale: Number(scale) });
}

watch(selectedSlug, () => {
  if (viewMode.value === "breakdown") {
    loadBreakdown();
  } else {
    loadCards();
  }
  pushStorageQuery();
});

watch(viewMode, (mode, previous) => {
  if (mode === previous) {
    return;
  }
  if (mode === "breakdown") {
    loadBreakdown();
  } else if (previous === "breakdown") {
    loadCards();
  }
});

watch(selectedLocation, (location) => {
  syncInlineFields(location);
  if (location?.locationType === "deck") {
    sectionExpanded.deck = true;
  }
});

watch(setCodesInLocation, (codes) => {
  if (setFilter.value && !codes.includes(setFilter.value)) {
    setFilter.value = "";
  }
});

watch(setGroupCodesKey, () => {
  if (!groupBySet.value) {
    return;
  }
  applyDefaultSetGroupExpansion();
});

watch(
  [searchQuery, foilFilter, setFilter, cardsSort, cardsSortDir, viewMode, groupBySet],
  () => {
    if (syncingRoute.value) {
      return;
    }
    pushStorageQuery();
  },
);

watch(
  () => route.query,
  () => {
    if (syncingRoute.value) {
      return;
    }
    const location = storageLocationFromRoute(route);
    applyFiltersFromRoute(route);
    if (location && location !== selectedSlug.value) {
      selectedSlug.value = location;
    }
  },
);

async function loadSetsCatalog() {
  try {
    const payload = await api.getReportsMeta();
    setsCatalog.value = (payload.sets || []).filter((set) => set.setCode && set.setCode !== "All");
  } catch {
    setsCatalog.value = [];
  }
}

onMounted(async () => {
  applyFiltersFromRoute(route);
  const preferredLocation = storageLocationFromRoute(route);
  await Promise.all([
    loadLocations(preferredLocation),
    loadPricingSettings(true),
    loadSetsCatalog(),
  ]);
  if (viewMode.value === "breakdown") {
    await loadBreakdown();
  }
  pushStorageQuery();
});
</script>

<template>
  <div class="storage-page collection-page">
    <div class="storage-layout">
      <nav class="storage-location-nav" aria-label="Storage locations">
        <section
          v-for="section in groupedVisibleLocations"
          :key="section.type"
          class="storage-location-section"
          :class="{ 'storage-location-section--collapsed': !isSectionExpanded(section) }"
        >
          <button
            v-if="section.collapsible"
            type="button"
            class="storage-location-section-heading storage-location-section-toggle"
            :aria-expanded="isSectionExpanded(section) ? 'true' : 'false'"
            @click="toggleSection(section)"
          >
            <StorageLocationIcon :type="section.type" />
            <span class="storage-location-section-title">{{ section.label }}</span>
            <span class="storage-location-section-count">{{ section.locations.length }}</span>
            <span class="storage-location-section-chevron" aria-hidden="true">▾</span>
          </button>
          <h3 v-else class="storage-location-section-heading">
            <StorageLocationIcon :type="section.type" />
            <span class="storage-location-section-title">{{ section.label }}</span>
            <button
              v-if="section.canCreate"
              type="button"
              class="storage-location-section-add"
              :aria-label="createLocationLabel(section.type)"
              :title="createLocationLabel(section.type)"
              @click="openCreateEditor(section.type)"
            >
              +
            </button>
          </h3>
          <div
            v-for="location in section.locations"
            v-show="isSectionExpanded(section)"
            :key="location.slug"
            class="storage-location-link"
            :class="{ active: location.slug === selectedSlug }"
          >
            <button
              type="button"
              class="storage-location-select"
              @click="selectLocation(location.slug)"
            >
              <span class="storage-location-link-main">
                <StorageLocationIcon :type="location.locationType" />
                <span class="storage-location-label">{{ location.label }}</span>
              </span>
            </button>
            <button
              v-if="location.locationType === 'storage'"
              type="button"
              class="storage-location-default"
              :class="{ 'is-default': isDefaultStorage(location) }"
              :disabled="defaultStorageSaving"
              :aria-pressed="isDefaultStorage(location) ? 'true' : 'false'"
              :aria-label="isDefaultStorage(location) ? `${location.label} is default storage` : `Set ${location.label} as default storage`"
              :title="isDefaultStorage(location) ? 'Default storage' : 'Set as default storage'"
              @click="toggleDefaultStorage(location)"
            >
              {{ isDefaultStorage(location) ? "★" : "☆" }}
            </button>
            <span class="storage-location-count">{{ location.cardCount }}</span>
          </div>
        </section>
      </nav>

      <div class="storage-detail">
        <div v-if="selectedLocation" class="storage-detail-header">
          <div class="storage-detail-title-row">
            <div class="storage-detail-title-main">
              <StorageLocationIcon
                :type="selectedLocation.locationType"
                class="storage-detail-type-icon"
              />
              <input
                v-if="canInlineEdit"
                ref="inlineLabelRef"
                v-model="inlineLabel"
                class="storage-inline-title"
                type="text"
                maxlength="120"
                :disabled="inlineSaving"
                aria-label="Storage name"
                @blur="saveInlineLabel"
                @keydown="onInlineLabelKeydown"
              >
              <h2 v-else>{{ selectedLocation.label }}</h2>
            </div>

            <div class="storage-detail-actions">
              <button
                v-if="selectedLocation.locationType === 'storage'"
                type="button"
                class="storage-location-default storage-location-default--detail"
                :class="{ 'is-default': isDefaultStorage(selectedLocation) }"
                :disabled="defaultStorageSaving"
                :aria-pressed="isDefaultStorage(selectedLocation) ? 'true' : 'false'"
                :aria-label="isDefaultStorage(selectedLocation) ? 'Default storage' : 'Set as default storage'"
                :title="isDefaultStorage(selectedLocation) ? 'Default storage' : 'Set as default storage'"
                @click="toggleDefaultStorage(selectedLocation)"
              >
                {{ isDefaultStorage(selectedLocation) ? "★ Default" : "☆ Set default" }}
              </button>
              <button
                v-if="selectedLocation.canDelete"
                type="button"
                class="btn btn-danger"
                @click="deleteLocation(selectedLocation)"
              >
                Delete
              </button>
            </div>
          </div>

          <p v-if="isDeckLocation" class="storage-deck-hint">
            Deck storage is updated automatically when you mark cards owned on the deck.
          </p>

          <textarea
            v-if="canInlineEdit"
            ref="inlineDescRef"
            v-model="inlineDescription"
            class="storage-inline-description"
            rows="2"
            maxlength="500"
            placeholder="Add a description…"
            :disabled="inlineSaving"
            aria-label="Storage description"
            @blur="saveInlineDescription"
            @keydown="onInlineDescKeydown"
          />
          <p
            v-else-if="selectedLocation.description"
            class="storage-location-description"
          >
            {{ selectedLocation.description }}
          </p>

          <p v-if="inlineError" class="storage-inline-error">{{ inlineError }}</p>

          <p class="storage-location-stats">
            {{ cardsPayload?.totalCopies ?? selectedLocation.cardCount }} copies ·
            {{ cardsPayload?.uniquePrints ?? selectedLocation.uniquePrints }} unique prints
          </p>
        </div>

        <div class="storage-detail-toolbar">
          <div class="storage-toolbar-row">
            <template v-if="!isBreakdownView">
            <label class="storage-toolbar-search">
              <span class="visually-hidden">Search cards</span>
              <input
                v-model="searchQuery"
                type="search"
                placeholder="Search name or #…"
                autocomplete="off"
              >
            </label>

            <BrowseSelect
              v-model="setFilter"
              class="storage-toolbar-set-select"
              :options="setFilterOptions"
              filterable
              show-icons
              optional-icons
              hide-arrows
              empty-icon-label="All"
              placeholder="All sets"
              aria-label="Filter by set"
              portal-panel
            />

            <label class="storage-toolbar-select">
              <span class="visually-hidden">Finish</span>
              <select v-model="foilFilter" aria-label="Filter by finish">
                <option
                  v-for="option in FINISH_OPTIONS"
                  :key="option.id"
                  :value="option.id"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>

            <div class="storage-sort-row">
              <label class="visually-hidden" for="storage-sort">Sort by</label>
              <select id="storage-sort" :value="cardsSort" @change="onSortChange">
                <option
                  v-for="option in SORT_OPTIONS"
                  :key="option.id"
                  :value="option.id"
                >
                  {{ option.label }}
                </option>
              </select>
              <button
                type="button"
                class="btn btn-secondary collection-sort-dir"
                :title="cardsSortDir === 'asc' ? 'Ascending' : 'Descending'"
                @click="toggleSortDir"
              >
                {{ cardsSortDir === "asc" ? "↑" : "↓" }}
              </button>
            </div>

            <p class="storage-toolbar-summary">{{ matchSummaryText }}</p>
            </template>
            <p v-else class="storage-toolbar-summary">Analytics for this location</p>

            <div class="storage-toolbar-end">
              <button
                v-if="!isBreakdownView"
                type="button"
                class="filter-button"
                :class="{ active: groupBySet }"
                :aria-pressed="groupBySet"
                @click="toggleGroupBySet"
              >
                Group by set
              </button>

              <button
                v-if="!isBreakdownView && groupBySet && setGroups.length"
                type="button"
                class="btn btn-secondary btn-small storage-set-groups-toggle"
                @click="anySetGroupExpanded ? collapseAllSetGroups() : expandAllSetGroups()"
              >
                {{ anySetGroupExpanded ? "Collapse all" : "Expand all" }}
              </button>

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
                  @click="setViewMode('table')"
                >
                  Table
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: viewMode === 'breakdown' }"
                  @click="setViewMode('breakdown')"
                >
                  Breakdown
                </button>
              </div>

              <CollectionGalleryScaleControl
                v-if="viewMode === 'gallery'"
                class="collection-gallery-toolbar-scale"
                :model-value="collectionCardScale"
                :options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150]"
                @update:model-value="onCardScaleChange"
              />
            </div>
          </div>
        </div>

        <div v-if="isBreakdownView && loadingBreakdown" class="storage-empty">
          <LoadingIndicator label="Loading breakdown…" />
        </div>

        <StorageBreakdownPanel
          v-else-if="isBreakdownView"
          :breakdown="breakdownPayload"
          :set-icons="breakdownSetIcons"
          :set-labels="breakdownSetLabels"
        />

        <div v-else-if="loadingCards" class="storage-empty">
          <LoadingIndicator label="Loading cards…" />
        </div>

        <div
          v-else-if="!scopePrintCount"
          class="storage-empty"
        >
          No cards in this location.
        </div>

        <div
          v-else-if="!sortedCards.length"
          class="storage-empty"
        >
          No cards match the current search or filters.
        </div>

        <GalleryLoadingOverlay
          v-else-if="viewMode === 'gallery'"
          :loading="false"
          class="storage-gallery-wrap collection-gallery-panel"
        >
          <div v-if="groupBySet" class="storage-grouped-scroll">
            <section
              v-for="group in setGroups"
              :key="group.setCode"
              class="storage-set-group"
              :class="{ 'is-collapsed': !isSetGroupExpanded(group.setCode) }"
            >
              <button
                type="button"
                class="storage-set-group-header"
                :aria-expanded="isSetGroupExpanded(group.setCode)"
                @click="toggleSetGroup(group.setCode)"
              >
                <span class="storage-set-group-chevron" aria-hidden="true">▾</span>
                <img
                  v-if="setIconForCode(group.setCode)"
                  :src="setIconForCode(group.setCode)"
                  alt=""
                  class="storage-set-group-icon"
                >
                <h3 class="storage-set-group-title">
                  {{ setLabelForCode(group.setCode) }}
                </h3>
                <span class="storage-set-group-meta">{{ setGroupMetaText(group) }}</span>
              </button>
              <div
                v-if="isSetGroupExpanded(group.setCode)"
                class="storage-set-group-gallery"
                :class="{ 'is-scrollable-group': isLargeSetGroup(group) }"
              >
                <VirtualizedCollectionCardGrid
                  v-if="isLargeSetGroup(group)"
                  :cards="group.cards"
                  :card-scale="collectionCardScale"
                />
                <CollectionCardGrid
                  v-else
                  :cards="group.cards"
                  :card-scale="collectionCardScale"
                />
              </div>
            </section>
          </div>
          <VirtualizedCollectionCardGrid
            v-else
            :cards="sortedCards"
            :card-scale="collectionCardScale"
            show-set-label
            :set-label-for="setLabelForCode"
          />
        </GalleryLoadingOverlay>

        <div
          v-else-if="groupBySet"
          class="table-panel cards-panel storage-cards-panel storage-grouped-scroll"
        >
          <section
            v-for="group in setGroups"
            :key="group.setCode"
            class="storage-set-group"
            :class="{ 'is-collapsed': !isSetGroupExpanded(group.setCode) }"
          >
            <button
              type="button"
              class="storage-set-group-header"
              :aria-expanded="isSetGroupExpanded(group.setCode)"
              @click="toggleSetGroup(group.setCode)"
            >
              <span class="storage-set-group-chevron" aria-hidden="true">▾</span>
              <img
                v-if="setIconForCode(group.setCode)"
                :src="setIconForCode(group.setCode)"
                alt=""
                class="storage-set-group-icon"
              >
              <h3 class="storage-set-group-title">
                {{ setLabelForCode(group.setCode) }}
              </h3>
              <span class="storage-set-group-meta">{{ setGroupMetaText(group) }}</span>
            </button>
            <div
              v-if="isSetGroupExpanded(group.setCode)"
              class="storage-set-group-table"
              :style="{ '--storage-group-rows': setGroupTableRowVar(group) }"
            >
              <VirtualizedStorageTable
                :cards="group.cards"
                :sort-field="cardsSort"
                :sort-dir="cardsSortDir"
                :show-remove="!isDeckLocation"
                :line-total="lineTotal"
                :set-label-for="setLabelForCode"
                :set-icon-for="setIconForCode"
                @sort="onColumnSort"
                @remove-one="removeOneCopy"
              />
            </div>
          </section>
        </div>

        <div
          v-else
          class="table-panel cards-panel storage-cards-panel"
        >
          <VirtualizedStorageTable
            :cards="sortedCards"
            :sort-field="cardsSort"
            :sort-dir="cardsSortDir"
            :show-remove="!isDeckLocation"
            :line-total="lineTotal"
            :set-label-for="setLabelForCode"
            :set-icon-for="setIconForCode"
            @sort="onColumnSort"
            @remove-one="removeOneCopy"
          />
        </div>
      </div>
    </div>

    <div v-if="editor.open" class="modal-backdrop" @click.self="closeEditor">
      <form class="modal-card" @submit.prevent="saveEditor">
        <h3>{{ editor.locationType === "binder" ? "New binder" : "New storage" }}</h3>
        <label>
          <span>Type</span>
          <select v-model="editor.locationType">
            <option value="storage">Storage</option>
            <option value="binder">Binder</option>
          </select>
        </label>
        <label>
          <span>Label</span>
          <input v-model="editor.label" type="text" maxlength="120" required>
        </label>
        <label>
          <span>Description</span>
          <textarea v-model="editor.description" rows="3" maxlength="500" />
        </label>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary" @click="closeEditor">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary">Create</button>
        </div>
      </form>
    </div>
  </div>
</template>
