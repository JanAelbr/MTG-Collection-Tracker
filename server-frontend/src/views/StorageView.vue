<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { api } from "../api";
import BrowseSelect from "../components/BrowseSelect.vue";
import CollectionGalleryScaleControl from "../components/CollectionGalleryScaleControl.vue";
import CollectionGroupTree from "../components/CollectionGroupTree.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import ManaSymbols from "../components/ManaSymbols.vue";
import StorageGroupGallery from "../components/StorageGroupGallery.vue";
import StorageLocationIcon from "../components/StorageLocationIcon.vue";
import StorageBreakdownPanel from "../components/StorageBreakdownPanel.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import VirtualizedStorageTable from "../components/VirtualizedStorageTable.vue";
import ListForSaleModal from "../components/ListForSaleModal.vue";
import { savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { applyListingResultToCard } from "../composables/cardContextMenu";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { filterCollectionCards } from "../utils/collectionFilters";
import {
  defaultCollectionSortDir,
  sortCollectionCards,
} from "../utils/collectionSort";
import { DECK_COLOR_ORDER } from "../utils/deckCards";
import { getStoredColorFilterMode, storeColorFilterMode } from "../utils/filterStorage";
import { cardDisplayName } from "../utils/finishes";
import { formatEuro, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import {
  collectGroupPaths,
  groupHasChildren,
  groupSearchCards,
  SEARCH_GROUP_BY_OPTIONS,
} from "../utils/searchResults";
import {
  normalizeStorageGroupByLevels,
  storageFiltersFromRoute,
  storageLocationsFromRoute,
  storageRouteQuery,
} from "../utils/storageScope";
import {
  mergeStorageBreakdownPayloads,
  mergeStorageCardPayloads,
} from "../utils/storageMerge";
import { STORAGE_LOCATION_SECTIONS } from "../utils/storageLocationGroups";

const route = useRoute();
const router = useRouter();

const {
  settings: pricingSettings,
  collectionCardScale,
  fetchPricingSettings: loadPricingSettings,
} = usePricingSettings();

const locations = ref([]);
const selectedSlugs = ref([]);
const cardsPayload = ref(null);
const breakdownPayload = ref(null);
const setsCatalog = ref([]);
const defaultStorageSaving = ref(false);
const { loading: loadingCards, run: runCardsLoad } = useAsyncLoad();
const { loading: loadingBreakdown, run: runBreakdownLoad } = useAsyncLoad();

const searchQuery = ref("");
const setFilter = ref("");
const colorFilters = ref([]);
const colorMode = ref(getStoredColorFilterMode());
const cardsSort = ref("value");
const cardsSortDir = ref(defaultCollectionSortDir("value"));
const viewMode = ref("gallery");
const groupByLevels = ref(["set"]);
/** Group paths currently expanded; empty = all collapsed (default). */
const expandedGroupKeys = ref(new Set());
const syncingRoute = ref(false);

const editor = reactive({
  open: false,
  locationType: "storage",
  label: "",
  description: "",
});

const saleModal = ref(null);

const inlineLabel = ref("");
const inlineDescription = ref("");
const inlineSaving = ref(false);
const inlineError = ref("");
const inlineLabelRef = ref(null);
const inlineDescRef = ref(null);

const SORT_OPTIONS = [
  { id: "value", label: "Value" },
  { id: "name", label: "Name" },
  { id: "number", label: "Number" },
  { id: "set", label: "Set" },
  { id: "cmc", label: "CMC" },
  { id: "rarity", label: "Rarity" },
  { id: "power", label: "Power" },
  { id: "toughness", label: "Toughness" },
  { id: "artStyle", label: "Art style" },
  { id: "finish", label: "Finish" },
  { id: "copies", label: "Copies" },
];

const selectedLocations = computed(() => {
  const bySlug = new Map(locations.value.map((item) => [item.slug, item]));
  return selectedSlugs.value
    .map((slug) => bySlug.get(slug))
    .filter(Boolean);
});

const selectedLocation = computed(() =>
  selectedLocations.value.length === 1 ? selectedLocations.value[0] : null,
);

const isMultiLocation = computed(() => selectedSlugs.value.length > 1);

const selectedLocationLabels = computed(() =>
  selectedLocations.value.map((location) => location.label).join(", "),
);

const selectedSlugKey = computed(() => selectedSlugs.value.join("|"));

const canInlineEdit = computed(() => {
  const type = selectedLocation.value?.locationType;
  return Boolean(selectedLocation.value) && (type === "storage" || type === "binder");
});

const isDeckLocation = computed(
  () => selectedLocations.value.some((location) => location.locationType === "deck"),
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
  const filters = storageFiltersFromRoute(routeRef, {
    colorModeFallback: getStoredColorFilterMode(),
  });
  searchQuery.value = filters.searchQuery;
  setFilter.value = filters.setFilter;
  colorFilters.value = [...filters.colorFilters];
  colorMode.value = filters.colorMode;
  cardsSort.value = filters.sort;
  cardsSortDir.value = filters.sortDir;
  viewMode.value = filters.viewMode;
  groupByLevels.value = filters.groupByLevels?.length
    ? [...filters.groupByLevels]
    : [];
}

function pushStorageQuery() {
  const nextQuery = storageRouteQuery({
    location: selectedSlugs.value,
    setFilter: setFilter.value,
    sort: cardsSort.value,
    sortDir: cardsSortDir.value,
    searchQuery: searchQuery.value,
    viewMode: viewMode.value,
    groupByLevels: groupByLevels.value,
    colorFilters: colorFilters.value,
    colorMode: colorMode.value,
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
    searchMode: "storage",
    colorFilters: colorFilters.value,
    colorMode: colorMode.value,
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

const isGrouped = computed(() => groupByLevels.value.length > 0);

function enrichCardGroups(groups) {
  return (groups || []).map((group) => {
    const childGroups = groupHasChildren(group)
      ? enrichCardGroups(group.groups)
      : [];
    const cards = childGroups.length
      ? group.cards
      : sortCollectionCards(group.cards, {
        sort: cardsSort.value,
        dir: cardsSortDir.value,
        allowSet: true,
      });
    let copyCount = 0;
    let totalValue = 0;
    let hasPriced = false;
    for (const card of group.cards || []) {
      copyCount += Number(card.copyCount) || 0;
      const line = lineTotal(card);
      if (line != null) {
        totalValue += line;
        hasPriced = true;
      }
    }
    return {
      ...group,
      cards,
      groups: childGroups,
      printCount: (group.cards || []).length,
      copyCount,
      totalValue: hasPriced ? totalValue : null,
    };
  });
}

const cardGroups = computed(() => {
  if (!isGrouped.value) {
    return [];
  }
  return enrichCardGroups(groupSearchCards(filteredCards.value, groupByLevels.value, {
    setLabelFor: setLabelForCode,
  }));
});

const anyGroupExpanded = computed(() =>
  collectGroupPaths(cardGroups.value).some((path) => expandedGroupKeys.value.has(path)),
);

function defaultExpandedGroupKeys(groups = cardGroups.value) {
  if (groups.length === 1) {
    return new Set([groups[0].path]);
  }
  return new Set();
}

function applyDefaultGroupExpansion() {
  expandedGroupKeys.value = defaultExpandedGroupKeys();
}

function isGroupExpanded(path) {
  return expandedGroupKeys.value.has(path);
}

function toggleGroup(path) {
  const next = new Set(expandedGroupKeys.value);
  if (next.has(path)) {
    next.delete(path);
  } else {
    next.add(path);
  }
  expandedGroupKeys.value = next;
}

function expandAllGroups() {
  expandedGroupKeys.value = new Set(collectGroupPaths(cardGroups.value));
}

function collapseAllGroups() {
  expandedGroupKeys.value = new Set();
}

function groupMetaText(group) {
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

function isLargeGroup(group) {
  return (group?.cards?.length || 0) > GROUP_VIRTUALIZE_THRESHOLD;
}

function groupTableRowVar(group) {
  return isLargeGroup(group)
    ? Math.min(group.cards.length, GROUP_TABLE_MAX_VISIBLE_ROWS)
    : group.cards.length;
}

const groupKeysKey = computed(() =>
  `${groupByLevels.value.join(",")}:${collectGroupPaths(cardGroups.value).join("|")}`,
);

function groupByOptionsForLevel(levelIndex) {
  const used = new Set(groupByLevels.value.slice(0, levelIndex));
  return SEARCH_GROUP_BY_OPTIONS.filter(
    (option) => option.value === "none" || !used.has(option.value),
  );
}

function onGroupLevelChange(levelIndex, event) {
  const nextValue = String(event?.target?.value || "none");
  const next = groupByLevels.value.slice(0, levelIndex);
  if (nextValue !== "none") {
    next.push(nextValue);
  }
  groupByLevels.value = next;
  if (isGrouped.value) {
    applyDefaultGroupExpansion();
  }
}

const scopePrintCount = computed(() => locationCards.value.length);

const matchSummaryText = computed(() => {
  const shown = sortedCards.value.length;
  const scope = scopePrintCount.value;
  if (!scope) {
    return isMultiLocation.value
      ? "No prints in these locations"
      : "No prints in this location";
  }
  if (shown === scope) {
    return `${shown} prints`;
  }
  return `${shown} shown · ${scope} prints`;
});

function normalizePreferredSlugs(preferred = "") {
  if (Array.isArray(preferred)) {
    return preferred.map((slug) => String(slug || "").trim()).filter(Boolean);
  }
  return String(preferred || "")
    .split(",")
    .map((slug) => slug.trim())
    .filter(Boolean);
}

function resolveSelectedSlugs(preferred = []) {
  const known = new Set(locations.value.map((location) => location.slug));
  const preferredSlugs = normalizePreferredSlugs(preferred).filter((slug) => known.has(slug));
  if (preferredSlugs.length) {
    return preferredSlugs;
  }
  const current = selectedSlugs.value.filter((slug) => known.has(slug));
  if (current.length) {
    return current;
  }
  const fallback =
    locations.value.find((location) => location.slug === (pricingSettings.value?.defaultStorageLocation || ""))?.slug
    || locations.value[0]?.slug
    || "";
  return fallback ? [fallback] : [];
}

async function loadLocations(preferred = "") {
  const payload = await api.listStorageLocations();
  locations.value = payload.locations || [];
  let preferredList = normalizePreferredSlugs(preferred);
  if (!preferredList.length && payload.defaultLocation) {
    preferredList = [payload.defaultLocation];
  }
  selectedSlugs.value = resolveSelectedSlugs(preferredList);
}

async function loadCards() {
  if (viewMode.value === "breakdown") {
    return;
  }
  if (!selectedSlugs.value.length) {
    cardsPayload.value = null;
    return;
  }
  await runCardsLoad(async () => {
    const payloads = await Promise.all(
      selectedSlugs.value.map((slug) => api.getStorageLocationCards(slug)),
    );
    cardsPayload.value = mergeStorageCardPayloads(payloads);
  });
}

async function loadBreakdown() {
  if (!selectedSlugs.value.length) {
    breakdownPayload.value = null;
    return;
  }
  await runBreakdownLoad(async () => {
    const payloads = await Promise.all(
      selectedSlugs.value.map((slug) => api.getStorageBreakdown(slug)),
    );
    breakdownPayload.value = mergeStorageBreakdownPayloads(payloads);
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
  await loadLocations(selectedSlugs.value);
}

function listOneForSale(card) {
  if (card.forSale && card.listingId) {
    saleModal.value = {
      card,
      instanceId: card.listedInstanceId ?? null,
      listingId: card.listingId,
      listingPrice: card.listingPrice ?? null,
    };
    return;
  }
  const instanceId = card.instanceIds?.[card.instanceIds.length - 1];
  if (!instanceId) {
    return;
  }
  saleModal.value = {
    card,
    instanceId,
    listingId: null,
    listingPrice: null,
  };
}

function closeSaleModal() {
  saleModal.value = null;
}

async function onSaleModalSaved(result) {
  const card = saleModal.value?.card;
  if (card) {
    applyListingResultToCard(card, result);
  }
  await loadLocations(selectedSlugs.value);
}

function selectLocation(slug, event = null) {
  const multi = Boolean(event?.ctrlKey || event?.metaKey);
  if (multi) {
    const index = selectedSlugs.value.indexOf(slug);
    if (index >= 0) {
      if (selectedSlugs.value.length <= 1) {
        return;
      }
      selectedSlugs.value = selectedSlugs.value.filter((item) => item !== slug);
      return;
    }
    selectedSlugs.value = [...selectedSlugs.value, slug];
    return;
  }
  if (selectedSlugs.value.length !== 1 || selectedSlugs.value[0] !== slug) {
    searchQuery.value = "";
    setFilter.value = "";
    colorFilters.value = [];
  }
  selectedSlugs.value = [slug];
}

function isLocationSelected(slug) {
  return selectedSlugs.value.includes(slug);
}

function sectionLocationSlugs(section) {
  return (section?.locations || [])
    .map((location) => location.slug)
    .filter(Boolean);
}

function isSectionFullySelected(section) {
  const slugs = sectionLocationSlugs(section);
  if (!slugs.length) {
    return false;
  }
  const selected = new Set(selectedSlugs.value);
  return slugs.every((slug) => selected.has(slug));
}

function selectAllInSection(section, event = null) {
  event?.preventDefault?.();
  event?.stopPropagation?.();
  const slugs = sectionLocationSlugs(section);
  if (!slugs.length) {
    return;
  }
  if (isSectionFullySelected(section)) {
    // Already all selected for this type — keep a single location so the page stays usable.
    selectedSlugs.value = [slugs[0]];
    return;
  }
  if (section.collapsible) {
    sectionExpanded[section.type] = true;
  }
  searchQuery.value = "";
  setFilter.value = "";
  colorFilters.value = [];
  selectedSlugs.value = [...slugs];
}

function toggleColorFilter(color) {
  if (colorFilters.value.includes(color)) {
    colorFilters.value = colorFilters.value.filter((item) => item !== color);
    return;
  }
  colorFilters.value = [...colorFilters.value, color];
}

function clearColorFilters() {
  colorFilters.value = [];
}

function setColorMode(next) {
  const mode = next === "includes" ? "includes" : "exact";
  if (colorMode.value === mode) {
    return;
  }
  colorMode.value = mode;
  storeColorFilterMode(mode);
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

async function onCardScaleChange(scale) {
  await savePricingSettings({ collectionCardScale: Number(scale) });
}

watch(selectedSlugKey, () => {
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

watch(selectedLocations, (next) => {
  syncInlineFields(selectedLocation.value);
  if (next.some((location) => location.locationType === "deck")) {
    sectionExpanded.deck = true;
  }
});

watch(setCodesInLocation, (codes) => {
  if (setFilter.value && !codes.includes(setFilter.value)) {
    setFilter.value = "";
  }
});

watch(groupKeysKey, () => {
  if (!isGrouped.value) {
    return;
  }
  applyDefaultGroupExpansion();
});

watch(
  [searchQuery, setFilter, colorFilters, colorMode, cardsSort, cardsSortDir, viewMode, groupByLevels],
  () => {
    if (syncingRoute.value) {
      return;
    }
    pushStorageQuery();
  },
  { deep: true },
);

watch(
  () => route.query,
  () => {
    if (syncingRoute.value) {
      return;
    }
    const routeSlugs = storageLocationsFromRoute(route);
    applyFiltersFromRoute(route);
    if (routeSlugs.length && routeSlugs.join("|") !== selectedSlugKey.value) {
      selectedSlugs.value = resolveSelectedSlugs(routeSlugs);
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
  const preferredLocations = storageLocationsFromRoute(route);
  await Promise.all([
    loadLocations(preferredLocations),
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
        <p class="storage-multi-hint">Ctrl/⌘+click to select multiple</p>
        <section
          v-for="section in groupedVisibleLocations"
          :key="section.type"
          class="storage-location-section"
          :class="{ 'storage-location-section--collapsed': !isSectionExpanded(section) }"
        >
          <div
            v-if="section.collapsible"
            class="storage-location-section-heading"
          >
            <button
              type="button"
              class="storage-location-section-toggle"
              :aria-expanded="isSectionExpanded(section) ? 'true' : 'false'"
              @click="toggleSection(section)"
            >
              <StorageLocationIcon :type="section.type" />
              <span class="storage-location-section-title">{{ section.label }}</span>
              <span class="storage-location-section-count">{{ section.locations.length }}</span>
              <span class="storage-location-section-chevron" aria-hidden="true">▾</span>
            </button>
            <button
              type="button"
              class="storage-location-section-select-all"
              :class="{ active: isSectionFullySelected(section) }"
              :disabled="!section.locations.length"
              :aria-pressed="isSectionFullySelected(section) ? 'true' : 'false'"
              :aria-label="isSectionFullySelected(section)
                ? `Clear ${section.label} selection`
                : `Select all ${section.label}`"
              :title="isSectionFullySelected(section)
                ? `Clear ${section.label} selection`
                : `Select all ${section.label}`"
              @click="selectAllInSection(section, $event)"
            >
              All
            </button>
          </div>
          <h3 v-else class="storage-location-section-heading">
            <StorageLocationIcon :type="section.type" />
            <span class="storage-location-section-title">{{ section.label }}</span>
            <button
              type="button"
              class="storage-location-section-select-all"
              :class="{ active: isSectionFullySelected(section) }"
              :disabled="!section.locations.length"
              :aria-pressed="isSectionFullySelected(section) ? 'true' : 'false'"
              :aria-label="isSectionFullySelected(section)
                ? `Clear ${section.label} selection`
                : `Select all ${section.label}`"
              :title="isSectionFullySelected(section)
                ? `Clear ${section.label} selection`
                : `Select all ${section.label}`"
              @click="selectAllInSection(section, $event)"
            >
              All
            </button>
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
            :class="{ active: isLocationSelected(location.slug) }"
          >
            <button
              type="button"
              class="storage-location-select"
              :aria-pressed="isLocationSelected(location.slug) ? 'true' : 'false'"
              @click="selectLocation(location.slug, $event)"
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
        <div v-if="isMultiLocation" class="storage-detail-header">
          <div class="storage-detail-title-row">
            <div class="storage-detail-title-main">
              <h2>{{ selectedLocations.length }} locations</h2>
            </div>
          </div>
          <p class="storage-location-description">{{ selectedLocationLabels }}</p>
          <p class="storage-location-stats">
            {{ cardsPayload?.totalCopies ?? selectedLocations.reduce((sum, location) => sum + (location.cardCount || 0), 0) }} copies ·
            {{ cardsPayload?.uniquePrints ?? "—" }} unique prints
          </p>
        </div>

        <div v-else-if="selectedLocation" class="storage-detail-header">
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
                placeholder="Words AND · punctuation flexible…"
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

            <div class="storage-color-filter" role="group" aria-label="Color identity">
              <div class="storage-color-filter-pips">
                <button
                  v-for="color in DECK_COLOR_ORDER"
                  :key="color"
                  type="button"
                  class="storage-color-filter-btn"
                  :class="{ active: colorFilters.includes(color) }"
                  :title="color === 'C' ? 'Colorless' : color"
                  :aria-pressed="colorFilters.includes(color) ? 'true' : 'false'"
                  @click="toggleColorFilter(color)"
                >
                  <ManaSymbols :colors="color === 'C' ? [] : [color]" :size="14" />
                </button>
              </div>
              <button
                v-if="colorFilters.length"
                type="button"
                class="storage-color-filter-clear"
                title="Clear color filters"
                aria-label="Clear color filters"
                @click="clearColorFilters"
              >
                ×
              </button>
              <label class="storage-color-mode-toggle" title="Exact color identity only">
                <input
                  type="checkbox"
                  :checked="colorMode === 'exact'"
                  @change="setColorMode($event.target.checked ? 'exact' : 'includes')"
                >
                <span>Exact</span>
              </label>
            </div>

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
              <div
                v-if="!isBreakdownView"
                class="storage-group-by-stack"
              >
                <label class="storage-group-by">
                  <span>Group by</span>
                  <select
                    :value="groupByLevels[0] || 'none'"
                    aria-label="Group storage cards"
                    @change="onGroupLevelChange(0, $event)"
                  >
                    <option
                      v-for="option in groupByOptionsForLevel(0)"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label
                  v-if="groupByLevels[0]"
                  class="storage-group-by"
                >
                  <span>Then</span>
                  <select
                    :value="groupByLevels[1] || 'none'"
                    aria-label="Then group by"
                    @change="onGroupLevelChange(1, $event)"
                  >
                    <option
                      v-for="option in groupByOptionsForLevel(1)"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label
                  v-if="groupByLevels[1]"
                  class="storage-group-by"
                >
                  <span>Then</span>
                  <select
                    :value="groupByLevels[2] || 'none'"
                    aria-label="Then group by again"
                    @change="onGroupLevelChange(2, $event)"
                  >
                    <option
                      v-for="option in groupByOptionsForLevel(2)"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>
              </div>

              <button
                v-if="!isBreakdownView && isGrouped && cardGroups.length"
                type="button"
                class="btn btn-secondary btn-small storage-set-groups-toggle"
                @click="anyGroupExpanded ? collapseAllGroups() : expandAllGroups()"
              >
                {{ anyGroupExpanded ? "Collapse all" : "Expand all" }}
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
                :options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150, 175, 200, 225, 250]"
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
          <div v-if="isGrouped" class="storage-grouped-scroll">
            <CollectionGroupTree
              :groups="cardGroups"
              :is-expanded="isGroupExpanded"
              :set-icon-for="setIconForCode"
              :meta-text-for="groupMetaText"
              @toggle="toggleGroup"
            >
              <template #leaf="{ group }">
                <StorageGroupGallery
                  :cards="group.cards"
                  :card-scale="collectionCardScale"
                  :scrollable="isLargeGroup(group)"
                />
              </template>
            </CollectionGroupTree>
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
          v-else-if="isGrouped"
          class="table-panel cards-panel storage-cards-panel storage-grouped-scroll"
        >
          <CollectionGroupTree
            :groups="cardGroups"
            :is-expanded="isGroupExpanded"
            :set-icon-for="setIconForCode"
            :meta-text-for="groupMetaText"
            @toggle="toggleGroup"
          >
            <template #leaf="{ group }">
              <div
                class="storage-set-group-table"
                :style="{ '--storage-group-rows': groupTableRowVar(group) }"
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
                  @list-for-sale="listOneForSale"
                />
              </div>
            </template>
          </CollectionGroupTree>
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
            @list-for-sale="listOneForSale"
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

    <ListForSaleModal
      :open="Boolean(saleModal)"
      :card="saleModal?.card || null"
      :instance-id="saleModal?.instanceId ?? null"
      :listing-id="saleModal?.listingId ?? null"
      :listing-price="saleModal?.listingPrice ?? null"
      @close="closeSaleModal"
      @saved="onSaleModalSaved"
    />
  </div>
</template>
