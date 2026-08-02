<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ignoreAborted } from "../api";
import CollectionAllFilters from "../components/CollectionAllFilters.vue";
import CollectionAllToolbar from "../components/CollectionAllToolbar.vue";
import CollectionMobileFilterSheet from "../components/CollectionMobileFilterSheet.vue";
import FilterSidebar from "../components/FilterSidebar.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import {
  mergeOwnershipPatchesIntoCards,
  reconcileOwnershipPatches,
} from "../composables/cardContextMenu";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { parseOptionalNumber } from "../utils/collectionFilters";
import { SEARCH_ROLE_OPTIONS, formatCardRoleLabel } from "../utils/deckPower";
import {
  defaultRolesSortDirForField,
  normalizeRolesRole,
  normalizeRolesSort,
  rolesFiltersFromRoute,
  rolesRouteQuery,
} from "../utils/setScope";
import { getStoredColorFilterMode, storeColorFilterMode } from "../utils/filterStorage";

const PAGE_SIZE = 25;

const route = useRoute();
const router = useRouter();

const roleCounts = ref([]);
const accumulatedCards = ref([]);
const totalMatches = ref(0);
const loadedPages = ref(0);
const loadingMore = ref(false);
const activeRole = ref("");
const rolesSort = ref("name");
const rolesSortDir = ref("asc");
const storageFilters = ref([]);
const foilFilter = ref("all");
const typeFilter = ref("all");
const colorFilters = ref([]);
const colorMode = ref(getStoredColorFilterMode());
const rarityFilter = ref("all");
const searchQuery = ref("");
const cmcMin = ref("");
const cmcMax = ref("");
const priceMin = ref("");
const priceMax = ref("");
const powerMin = ref("");
const toughnessMin = ref("");
const mobileFiltersOpen = ref(false);
const routeSyncReady = ref(false);
const virtualGridRef = ref(null);
const { loading, run } = useAsyncLoad();
const { collectionCardScale, settings: pricingSettings } = usePricingSettings();
let searchRequestToken = 0;
let searchDebounceTimer = null;

const countByRole = computed(() => {
  const map = new Map();
  for (const row of roleCounts.value) {
    map.set(row.id, Number(row.count) || 0);
  }
  return map;
});

const roleOptions = computed(() =>
  SEARCH_ROLE_OPTIONS.map((role) => ({
    ...role,
    count: countByRole.value.get(role.id) || 0,
  })),
);

const activeRoleLabel = computed(() => formatCardRoleLabel(activeRole.value) || "Role");
const cards = computed(() => accumulatedCards.value);
const totalPages = computed(() => Math.max(1, Math.ceil(totalMatches.value / PAGE_SIZE)));
const hasMoreResults = computed(() => loadedPages.value < totalPages.value);
const hasActiveRole = computed(() => Boolean(activeRole.value));

const toolbarSummary = computed(() => {
  if (!hasActiveRole.value) {
    return "Select a role";
  }
  if (loading.value && !cards.value.length) {
    return `Loading ${activeRoleLabel.value.toLowerCase()}…`;
  }
  if (!totalMatches.value) {
    return `No owned cards with role ${activeRoleLabel.value}`;
  }
  return `${activeRoleLabel.value} · showing ${cards.value.length} of ${totalMatches.value} owned`;
});

function currentFiltersPayload() {
  return {
    role: activeRole.value,
    sort: rolesSort.value,
    sortDir: rolesSortDir.value,
    storageFilters: storageFilters.value,
    foilFilter: foilFilter.value,
    typeFilter: typeFilter.value,
    colorFilters: colorFilters.value,
    colorMode: colorMode.value,
    rarityFilter: rarityFilter.value,
    searchQuery: searchQuery.value.trim(),
    cmcMin: parseOptionalNumber(cmcMin.value),
    cmcMax: parseOptionalNumber(cmcMax.value),
    priceMin: parseOptionalNumber(priceMin.value),
    priceMax: parseOptionalNumber(priceMax.value),
    powerMin: parseOptionalNumber(powerMin.value),
    toughnessMin: parseOptionalNumber(toughnessMin.value),
  };
}

function applyRouteState() {
  const filters = rolesFiltersFromRoute(route);
  activeRole.value = filters.role;
  rolesSort.value = filters.sort;
  rolesSortDir.value = filters.sortDir;
  storageFilters.value = [...(filters.storageFilters || [])];
  foilFilter.value = filters.foilFilter;
  typeFilter.value = filters.typeFilter;
  colorFilters.value = [...(filters.colorFilters || [])];
  colorMode.value = filters.colorMode || getStoredColorFilterMode();
  rarityFilter.value = filters.rarityFilter;
  searchQuery.value = filters.searchQuery || "";
  cmcMin.value = filters.cmcMin != null ? String(filters.cmcMin) : "";
  cmcMax.value = filters.cmcMax != null ? String(filters.cmcMax) : "";
  priceMin.value = filters.priceMin != null ? String(filters.priceMin) : "";
  priceMax.value = filters.priceMax != null ? String(filters.priceMax) : "";
  powerMin.value = filters.powerMin != null ? String(filters.powerMin) : "";
  toughnessMin.value = filters.toughnessMin != null ? String(filters.toughnessMin) : "";
}

function syncRoute() {
  if (!routeSyncReady.value) {
    return;
  }
  const nextQuery = rolesRouteQuery(currentFiltersPayload());
  const current = rolesRouteQuery(rolesFiltersFromRoute(route));
  if (JSON.stringify(nextQuery) === JSON.stringify(current)) {
    return;
  }
  router.replace({ path: "/collection/roles", query: nextQuery });
}

function pickDefaultRole(rows) {
  const withCount = (rows || []).find((row) => Number(row.count) > 0);
  if (withCount?.id) {
    return withCount.id;
  }
  return SEARCH_ROLE_OPTIONS[0]?.id || "";
}

async function loadRoleCounts() {
  const payload = await ignoreAborted(api.getOwnedRoles({
    storageFilters: storageFilters.value,
  }));
  if (!payload) {
    return;
  }
  roleCounts.value = payload.roles || [];
  if (!activeRole.value) {
    activeRole.value = pickDefaultRole(roleCounts.value);
  }
}

function resetResults() {
  accumulatedCards.value = [];
  totalMatches.value = 0;
  loadedPages.value = 0;
}

function applySearchPayload(payload, { append = false } = {}) {
  const nextCards = payload.cards || [];
  accumulatedCards.value = append
    ? [...accumulatedCards.value, ...nextCards]
    : nextCards;
  totalMatches.value = Number(payload.totalMatches) || 0;
  loadedPages.value = Number(payload.page) || loadedPages.value;
}

async function fetchRolePage(pageNum) {
  if (!activeRole.value) {
    return null;
  }
  const token = ++searchRequestToken;
  const payload = await ignoreAborted(api.searchCards({
    q: searchQuery.value.trim() || undefined,
    setCode: "All",
    ownedFilter: "owned",
    foilFilter: foilFilter.value,
    typeFilter: typeFilter.value,
    colorFilters: colorFilters.value,
    colorMode: colorMode.value,
    rarityFilter: rarityFilter.value,
    roleFilters: [activeRole.value],
    storageFilters: storageFilters.value,
    cmcMin: parseOptionalNumber(cmcMin.value),
    cmcMax: parseOptionalNumber(cmcMax.value),
    priceMin: parseOptionalNumber(priceMin.value),
    priceMax: parseOptionalNumber(priceMax.value),
    powerMin: parseOptionalNumber(powerMin.value),
    toughnessMin: parseOptionalNumber(toughnessMin.value),
    sort: rolesSort.value,
    dir: rolesSortDir.value,
    page: pageNum,
    pageSize: PAGE_SIZE,
  }));
  if (!payload || token !== searchRequestToken) {
    return null;
  }
  return payload;
}

async function loadResults() {
  if (!activeRole.value) {
    resetResults();
    return;
  }
  await run(async (isCurrent) => {
    resetResults();
    const payload = await fetchRolePage(1);
    if (!isCurrent() || !payload) {
      return;
    }
    applySearchPayload(payload, { append: false });
  });
  await fillVisibleResults();
}

async function loadMoreResults() {
  if (loadingMore.value || loading.value || !hasMoreResults.value) {
    return;
  }
  loadingMore.value = true;
  try {
    const payload = await fetchRolePage(loadedPages.value + 1);
    if (payload) {
      applySearchPayload(payload, { append: true });
    }
  } finally {
    loadingMore.value = false;
  }
}

async function fillVisibleResults() {
  await nextTick();
  const root = virtualGridRef.value?.rootRef;
  if (!root || !hasMoreResults.value || loadingMore.value || loading.value) {
    return;
  }
  const scrollable = root.scrollHeight > root.clientHeight + 8;
  if (!scrollable) {
    await loadMoreResults();
    if (hasMoreResults.value) {
      await fillVisibleResults();
    }
  }
}

function syncRouteAndReload() {
  syncRoute();
  return reloadForFilters();
}

function selectRole(roleId) {
  const next = normalizeRolesRole(roleId);
  if (!next || next === activeRole.value) {
    return;
  }
  activeRole.value = next;
  return syncRouteAndReload();
}

function setFoilFilter(value) {
  foilFilter.value = value || "all";
  return syncRouteAndReload();
}

function onTypeFilterChange(event) {
  typeFilter.value = event.target.value || "all";
  return syncRouteAndReload();
}

function toggleColorFilter(color) {
  if (colorFilters.value.includes(color)) {
    colorFilters.value = colorFilters.value.filter((item) => item !== color);
  } else {
    colorFilters.value = [...colorFilters.value, color];
  }
  return syncRouteAndReload();
}

function clearColorFilters() {
  colorFilters.value = [];
  return syncRouteAndReload();
}

function setColorMode(mode) {
  const next = mode === "includes" ? "includes" : "exact";
  if (colorMode.value === next) {
    return;
  }
  colorMode.value = next;
  storeColorFilterMode(next);
  return syncRouteAndReload();
}

function toggleStorageFilter(slug) {
  if (storageFilters.value.includes(slug)) {
    storageFilters.value = storageFilters.value.filter((item) => item !== slug);
  } else {
    storageFilters.value = [...storageFilters.value, slug];
  }
  return syncRouteAndReload();
}

function clearStorageFilters() {
  storageFilters.value = [];
  return syncRouteAndReload();
}

function setStorageFilters(values) {
  storageFilters.value = Array.isArray(values) ? [...values] : [];
  return syncRouteAndReload();
}

function onRarityFilterChange(event) {
  rarityFilter.value = event.target.value || "all";
  return syncRouteAndReload();
}

function updateDetailFilter(field, value) {
  const next = value == null ? "" : String(value);
  if (field === "cmcMin") cmcMin.value = next;
  if (field === "cmcMax") cmcMax.value = next;
  if (field === "priceMin") priceMin.value = next;
  if (field === "priceMax") priceMax.value = next;
  if (field === "powerMin") powerMin.value = next;
  if (field === "toughnessMin") toughnessMin.value = next;
  return syncRouteAndReload();
}

function updateSearchQuery(value) {
  searchQuery.value = value || "";
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
  }
  searchDebounceTimer = setTimeout(() => {
    syncRouteAndReload();
  }, 250);
}

function updateRolesSort(event) {
  const next = normalizeRolesSort(event.target.value);
  if (next === rolesSort.value) {
    return;
  }
  rolesSort.value = next;
  rolesSortDir.value = defaultRolesSortDirForField(next);
  return syncRouteAndReload();
}

function toggleRolesSortDir() {
  rolesSortDir.value = rolesSortDir.value === "asc" ? "desc" : "asc";
  return syncRouteAndReload();
}

async function setCollectionCardScale(value) {
  await savePricingSettings({ collectionCardScale: value });
}

async function onGalleryOwnershipChanged() {
  mergeOwnershipPatchesIntoCards(accumulatedCards.value);
  reconcileOwnershipPatches(accumulatedCards.value);
  await loadRoleCounts();
}

async function reloadForFilters() {
  await loadRoleCounts();
  await loadResults();
}

watch(
  () => route.fullPath,
  async () => {
    if (!routeSyncReady.value || route.path !== "/collection/roles") {
      return;
    }
    const filters = rolesFiltersFromRoute(route);
    const nextPayload = rolesRouteQuery(filters);
    const currentPayload = rolesRouteQuery(currentFiltersPayload());
    if (JSON.stringify(nextPayload) === JSON.stringify(currentPayload)) {
      return;
    }
    applyRouteState();
    if (!activeRole.value) {
      activeRole.value = pickDefaultRole(roleCounts.value);
      syncRoute();
    }
    await reloadForFilters();
  },
);

onMounted(async () => {
  applyRouteState();
  await fetchPricingSettings();
  await loadRoleCounts();
  if (!activeRole.value) {
    activeRole.value = pickDefaultRole(roleCounts.value);
  }
  routeSyncReady.value = true;
  syncRoute();
  await reloadForFilters();
});
</script>

<template>
  <div class="reports-page collection-page collection-roles-page">
    <div class="page-with-sidebar">
      <FilterSidebar class="collection-desktop-filters">
        <div class="filter-sidebar-section">
          <p class="filter-sidebar-label">Role</p>
          <div class="collection-storage-filter-list collection-role-filter-list collection-roles-list">
            <button
              v-for="role in roleOptions"
              :key="role.id"
              type="button"
              class="collection-roles-list-item"
              :class="{
                active: activeRole === role.id,
                'is-empty': role.count === 0,
              }"
              @click="selectRole(role.id)"
            >
              <span class="collection-roles-list-label">{{ role.label }}</span>
              <span class="collection-roles-list-count">{{ role.count }}</span>
            </button>
          </div>
        </div>

        <CollectionAllFilters
          :is-all-view="true"
          :is-all-sets-view="true"
          :owned-filter="'owned'"
          :foil-filter="foilFilter"
          :type-filter="typeFilter"
          :color-filters="colorFilters"
          :color-mode="colorMode"
          :storage-filters="storageFilters"
          :rarity-filter="rarityFilter"
          :cmc-min="cmcMin"
          :cmc-max="cmcMax"
          :price-min="priceMin"
          :price-max="priceMax"
          :power-min="powerMin"
          :toughness-min="toughnessMin"
          :all-cards-sort="rolesSort"
          :all-cards-sort-dir="rolesSortDir"
          :show-sort="false"
          :show-ownership-filter="false"
          :show-unowned-filter="false"
          :show-role-filter="false"
          @set-foil-filter="setFoilFilter"
          @type-filter-change="onTypeFilterChange"
          @toggle-color-filter="toggleColorFilter"
          @clear-color-filters="clearColorFilters"
          @update:color-mode="setColorMode"
          @toggle-storage-filter="toggleStorageFilter"
          @clear-storage-filters="clearStorageFilters"
          @set-storage-filters="setStorageFilters"
          @rarity-filter-change="onRarityFilterChange"
          @update:cmc-min="updateDetailFilter('cmcMin', $event)"
          @update:cmc-max="updateDetailFilter('cmcMax', $event)"
          @update:price-min="updateDetailFilter('priceMin', $event)"
          @update:price-max="updateDetailFilter('priceMax', $event)"
          @update:power-min="updateDetailFilter('powerMin', $event)"
          @update:toughness-min="updateDetailFilter('toughnessMin', $event)"
        />
      </FilterSidebar>

      <CollectionMobileFilterSheet
        :open="mobileFiltersOpen"
        @close="mobileFiltersOpen = false"
      >
        <div class="filter-sidebar-section">
          <p class="filter-sidebar-label">Role</p>
          <div class="collection-storage-filter-list collection-role-filter-list collection-roles-list">
            <button
              v-for="role in roleOptions"
              :key="`mobile-${role.id}`"
              type="button"
              class="collection-roles-list-item"
              :class="{
                active: activeRole === role.id,
                'is-empty': role.count === 0,
              }"
              @click="selectRole(role.id)"
            >
              <span class="collection-roles-list-label">{{ role.label }}</span>
              <span class="collection-roles-list-count">{{ role.count }}</span>
            </button>
          </div>
        </div>
        <CollectionAllFilters
          :is-all-view="true"
          :is-all-sets-view="true"
          :owned-filter="'owned'"
          :foil-filter="foilFilter"
          :type-filter="typeFilter"
          :color-filters="colorFilters"
          :color-mode="colorMode"
          :storage-filters="storageFilters"
          :rarity-filter="rarityFilter"
          :cmc-min="cmcMin"
          :cmc-max="cmcMax"
          :price-min="priceMin"
          :price-max="priceMax"
          :power-min="powerMin"
          :toughness-min="toughnessMin"
          :all-cards-sort="rolesSort"
          :all-cards-sort-dir="rolesSortDir"
          :show-sort="false"
          :show-ownership-filter="false"
          :show-unowned-filter="false"
          :show-role-filter="false"
          @set-foil-filter="setFoilFilter"
          @type-filter-change="onTypeFilterChange"
          @toggle-color-filter="toggleColorFilter"
          @clear-color-filters="clearColorFilters"
          @update:color-mode="setColorMode"
          @toggle-storage-filter="toggleStorageFilter"
          @clear-storage-filters="clearStorageFilters"
          @set-storage-filters="setStorageFilters"
          @rarity-filter-change="onRarityFilterChange"
          @update:cmc-min="updateDetailFilter('cmcMin', $event)"
          @update:cmc-max="updateDetailFilter('cmcMax', $event)"
          @update:price-min="updateDetailFilter('priceMin', $event)"
          @update:price-max="updateDetailFilter('priceMax', $event)"
          @update:power-min="updateDetailFilter('powerMin', $event)"
          @update:toughness-min="updateDetailFilter('toughnessMin', $event)"
        />
      </CollectionMobileFilterSheet>

      <div class="page-with-sidebar-main">
        <div class="table-panel cards-panel reports-cards-panel collection-gallery-panel">
          <CollectionAllToolbar
            :search-query="searchQuery"
            :summary-text="toolbarSummary"
            :card-scale="collectionCardScale"
            :scale-options="pricingSettings?.collectionCardScaleOptions ?? [75, 100, 125, 150, 175, 200, 225, 250]"
            :mobile-filters-open="mobileFiltersOpen"
            view-mode="gallery"
            :table-mode-available="false"
            :show-lenses="false"
            :show-bulk="false"
            :show-view-mode="false"
            :show-sort="true"
            sort-mode="roles"
            :all-cards-sort="rolesSort"
            :all-cards-sort-dir="rolesSortDir"
            search-placeholder="Search owned cards…"
            @update:search-query="updateSearchQuery"
            @open-mobile-filters="mobileFiltersOpen = true"
            @update:card-scale="setCollectionCardScale"
            @update-sort="updateRolesSort"
            @toggle-sort-dir="toggleRolesSortDir"
          />

          <div v-if="!hasActiveRole" class="storage-empty collection-gallery-empty">
            <p>Select a role to browse owned cards.</p>
          </div>

          <div
            v-else-if="hasActiveRole && !loading && !totalMatches"
            class="storage-empty collection-gallery-empty"
          >
            <p>No owned cards match these filters for {{ activeRoleLabel }}.</p>
          </div>

          <div v-else-if="loading && !cards.length" class="storage-empty">
            <LoadingIndicator :label="`Loading ${activeRoleLabel.toLowerCase()}…`" />
          </div>

          <GalleryLoadingOverlay
            v-else-if="cards.length"
            :loading="loading && !loadingMore"
            :label="`Loading ${activeRoleLabel.toLowerCase()}…`"
          >
            <VirtualizedCollectionCardGrid
              ref="virtualGridRef"
              :cards="cards"
              :card-scale="collectionCardScale"
              :has-more="hasMoreResults"
              @ownership-changed="onGalleryOwnershipChanged"
              @load-more="loadMoreResults"
            />
            <p v-if="loadingMore" class="collection-search-load-more-status">
              <LoadingIndicator label="Loading more cards…" />
            </p>
          </GalleryLoadingOverlay>
        </div>
      </div>
    </div>
  </div>
</template>
