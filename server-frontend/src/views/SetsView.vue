<script setup>
import "../styles/sets-page.css";
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { api, clearClientCache } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import {
  fetchAvailableManagerSets,
  removeAvailableSet,
  useAvailableManagerSets,
} from "../composables/availableSets";
import { formatSetCountLabel, setDisplayName, setShortName } from "../utils/format";
import {
  applySetGalleryIconFallback,
  resolveSetGalleryIconUri,
  resolveSetIconUri,
} from "../utils/scryfall";
import { collectionRouteForSet } from "../utils/setScope";
import {
  formatSubsetTypeLabel,
  isAutoLoadSubsetType,
  isSetsPageAlchemyType,
  isSetsPageDigitalOnlySet,
  isSetsPagePromoType,
} from "../utils/setBrowserSubsets";

const trackedSets = ref([]);
const loading = ref(true);
const loadError = ref("");
const filterQuery = ref("");
const statusFilter = ref("all");
const showPromoSets = ref(false);
const showAlchemySets = ref(false);
const showDigitalSets = ref(false);
const selectedCodes = ref(new Set());
const loadingCodes = ref(new Set());
const loadErrors = reactive({});
const reloadingSetCode = ref("");
const batchLoading = ref(false);
const batchSummary = ref("");

const { availableSets, loadingAvailableSets } = useAvailableManagerSets();

const trackedByCode = computed(() => {
  const map = new Map();
  for (const set of trackedSets.value) {
    if (set?.setCode) {
      map.set(set.setCode, set);
    }
  }
  return map;
});

function isBrowserRoot(set) {
  if (!set?.setCode || set.setCode === "All") {
    return false;
  }
  if (set.isFamilyRoot != null) {
    return Boolean(set.isFamilyRoot);
  }
  const root = set.familyRoot || set.setCode;
  return set.setCode === root;
}

const loadedRoots = computed(() =>
  trackedSets.value
    .filter((set) => isBrowserRoot(set))
    .map((set) => ({
      ...set,
      pendingImport: false,
      familyRoot: set.familyRoot || set.setCode,
      familyMembers: set.familyMembers || [set.setCode],
      releasedAt: set.releasedAt || "",
    })),
);

const pendingRoots = computed(() =>
  availableSets.value.map((set) => ({
    setCode: set.setCode,
    label: set.name || set.setCode,
    name: set.name || set.setCode,
    iconUri: set.iconUri || resolveSetIconUri(set),
    setType: set.setType,
    parentSetCode: set.parentSetCode,
    familyMembers: set.familyMembers || [set.setCode],
    autoLoadMembers: Array.isArray(set.autoLoadMembers) ? set.autoLoadMembers : null,
    familyRoot: set.setCode,
    isFamilyRoot: true,
    ownedCount: 0,
    catalogCount: 0,
    favorite: false,
    pendingImport: true,
    releasedAt: set.releasedAt || "",
    digital: Boolean(set.digital),
  })),
);

function compareByReleaseDate(a, b) {
  const byDate = String(b.releasedAt || "").localeCompare(String(a.releasedAt || ""));
  if (byDate) {
    return byDate;
  }
  return String(a.setCode).localeCompare(String(b.setCode));
}

function releaseYear(set) {
  const date = String(set?.releasedAt || "").trim();
  if (/^\d{4}/.test(date)) {
    return date.slice(0, 4);
  }
  return "";
}

const allTiles = computed(() =>
  [...loadedRoots.value, ...pendingRoots.value].sort(compareByReleaseDate),
);

function setMatchesQuery(set, query) {
  if (!query) {
    return true;
  }
  const members = set.familyMembers || [set.setCode];
  const haystack = [
    set.setCode,
    set.label,
    set.name,
    setDisplayName(set),
    setShortName(set),
    set.setType,
    ...members,
  ].filter(Boolean).join(" ").toLowerCase();
  return haystack.includes(query);
}

const visibleTiles = computed(() => {
  const query = filterQuery.value.trim().toLowerCase();
  return allTiles.value.filter((set) => {
    if (statusFilter.value === "loaded" && set.pendingImport) {
      return false;
    }
    if (statusFilter.value === "pending" && !set.pendingImport) {
      return false;
    }
    // Promo / Alchemy / other digital-only roots stay off the default browse list
    // unless their toggle is on or the user is searching.
    if (!query && !set.favorite) {
      if (!showPromoSets.value && isSetsPagePromoType(set.setType)) {
        return false;
      }
      if (!showAlchemySets.value && isSetsPageAlchemyType(set.setType)) {
        return false;
      }
      if (!showDigitalSets.value && isSetsPageDigitalOnlySet(set)) {
        return false;
      }
    }
    return setMatchesQuery(set, query);
  });
});

const visibleGroups = computed(() => {
  const favorites = [];
  const byYear = new Map();

  for (const set of visibleTiles.value) {
    if (set.favorite) {
      favorites.push(set);
      continue;
    }
    const year = releaseYear(set) || "unknown";
    const bucket = byYear.get(year);
    if (bucket) {
      bucket.push(set);
    } else {
      byYear.set(year, [set]);
    }
  }

  const years = [...byYear.keys()].sort((a, b) => {
    if (a === "unknown") {
      return 1;
    }
    if (b === "unknown") {
      return -1;
    }
    return b.localeCompare(a);
  });

  const groups = [];
  if (favorites.length) {
    groups.push({
      key: "favorites",
      label: "Favourites",
      sets: [...favorites].sort(compareByReleaseDate),
    });
  }
  for (const year of years) {
    groups.push({
      key: year,
      label: year === "unknown" ? "Unknown year" : year,
      sets: [...byYear.get(year)].sort(compareByReleaseDate),
    });
  }
  return groups;
});

const selectedPendingCount = computed(() => {
  let count = 0;
  for (const code of selectedCodes.value) {
    if (pendingRoots.value.some((set) => set.setCode === code)) {
      count += 1;
    }
  }
  return count;
});

const canLoadSelected = computed(() =>
  selectedPendingCount.value > 0 && !batchLoading.value,
);

const showInitialLoading = computed(() =>
  (loading.value || loadingAvailableSets.value) && !visibleGroups.value.length,
);

async function refreshLists({ forceAvailable = false } = {}) {
  loadError.value = "";
  try {
    const [managerPayload] = await Promise.all([
      api.listManagerSets(),
      fetchAvailableManagerSets({ force: forceAvailable }),
    ]);
    trackedSets.value = managerPayload?.sets || [];
  } catch (error) {
    loadError.value = error.message || "Could not load sets.";
    trackedSets.value = [];
  }
}

function setIconUri(set) {
  if (set.pendingImport) {
    return resolveSetIconUri(set);
  }
  return resolveSetGalleryIconUri(set) || resolveSetIconUri(set);
}

function onSetIconError(event, set) {
  applySetGalleryIconFallback(event.target, set);
}

function countLabel(set) {
  if (set.pendingImport) {
    return "";
  }
  if (set.familyOwnedCount != null && set.familyCatalogCount != null) {
    return `${set.familyOwnedCount}/${set.familyCatalogCount}`;
  }
  return formatSetCountLabel(set).replace(/[()]/g, "") || "";
}

function subsetMembers(set) {
  if (Array.isArray(set.autoLoadMembers) && set.autoLoadMembers.length) {
    return set.autoLoadMembers
      .filter((member) => member?.setCode && member.setCode !== set.setCode)
      .map((member) => ({
        setCode: member.setCode,
        setType: member.setType || "",
      }));
  }
  if (set.pendingImport) {
    return (set.familyMembers || [])
      .filter((code) => code && code !== set.setCode)
      .map((code) => ({ setCode: code, setType: "" }));
  }
  return (set.familyMembers || [])
    .filter((code) => code && code !== set.setCode)
    .map((code) => {
      const meta = trackedByCode.value.get(code);
      return { setCode: code, setType: meta?.setType || "" };
    })
    .filter((member) => isAutoLoadSubsetType(member.setType));
}

function subsetLabel(member) {
  const type = formatSubsetTypeLabel(member.setType);
  return type && member.setType ? `${member.setCode} · ${type}` : member.setCode;
}

function collectionLink(set) {
  return collectionRouteForSet(set.setCode, "", (set.familyMembers || []).length > 1);
}

function isSelected(set) {
  return selectedCodes.value.has(set.setCode);
}

function isTileLoading(set) {
  return loadingCodes.value.has(set.setCode);
}

function toggleSelect(set) {
  if (!set?.pendingImport || batchLoading.value) {
    return;
  }
  const code = set.setCode;
  const next = new Set(selectedCodes.value);
  if (next.has(code)) {
    next.delete(code);
  } else {
    next.add(code);
  }
  selectedCodes.value = next;
}

function clearSelection() {
  selectedCodes.value = new Set();
}

function pendingSetsInGroup(group) {
  return (group?.sets || []).filter((set) => set.pendingImport);
}

function allPendingSelectedInGroup(group) {
  const pending = pendingSetsInGroup(group);
  if (!pending.length) {
    return false;
  }
  return pending.every((set) => selectedCodes.value.has(set.setCode));
}

function toggleSelectYear(group) {
  if (batchLoading.value) {
    return;
  }
  const pending = pendingSetsInGroup(group);
  if (!pending.length) {
    return;
  }
  const next = new Set(selectedCodes.value);
  if (allPendingSelectedInGroup(group)) {
    for (const set of pending) {
      next.delete(set.setCode);
    }
  } else {
    for (const set of pending) {
      next.add(set.setCode);
    }
  }
  selectedCodes.value = next;
}

function onPendingKeydown(event, set) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    toggleSelect(set);
  }
}

async function toggleFavorite(event, set) {
  event.preventDefault();
  event.stopPropagation();
  if (!set?.setCode || set.pendingImport) {
    return;
  }
  try {
    const result = await api.toggleManagerSetFavorite(set.setCode);
    clearClientCache();
    if (result?.sets) {
      trackedSets.value = result.sets;
    } else {
      await refreshLists();
    }
  } catch (error) {
    window.alert(error.message || "Could not update favourite set.");
  }
}

async function reloadCatalog(event, set) {
  event.preventDefault();
  event.stopPropagation();
  if (!set?.setCode || set.pendingImport || reloadingSetCode.value) {
    return;
  }
  reloadingSetCode.value = set.setCode;
  try {
    await api.reloadManagerSetCatalog(set.setCode);
    clearClientCache();
    await refreshLists({ forceAvailable: true });
  } catch (error) {
    window.alert(error.message || "Could not reload catalog.");
  } finally {
    reloadingSetCode.value = "";
  }
}

async function loadSelected() {
  const queue = [...selectedCodes.value].filter((code) =>
    pendingRoots.value.some((set) => set.setCode === code),
  );
  if (!queue.length || batchLoading.value) {
    return;
  }

  batchLoading.value = true;
  batchSummary.value = "";
  const errors = [];
  let loadedCount = 0;

  for (const code of queue) {
    loadingCodes.value = new Set([...loadingCodes.value, code]);
    delete loadErrors[code];
    try {
      const result = await api.createManagerSet({ setCode: code });
      for (const member of result.addedSetCodes || result.familyMembers || [code]) {
        removeAvailableSet(member);
      }
      const nextSelected = new Set(selectedCodes.value);
      nextSelected.delete(code);
      selectedCodes.value = nextSelected;
      loadedCount += 1;
      clearClientCache();
      const managerPayload = await api.listManagerSets();
      trackedSets.value = managerPayload?.sets || [];
    } catch (error) {
      const message = error.message || "Could not load set.";
      loadErrors[code] = message;
      errors.push(`${code}: ${message}`);
    } finally {
      const nextLoading = new Set(loadingCodes.value);
      nextLoading.delete(code);
      loadingCodes.value = nextLoading;
    }
  }

  await fetchAvailableManagerSets({ force: true });
  batchLoading.value = false;

  if (errors.length) {
    batchSummary.value = `Loaded ${loadedCount} of ${queue.length}. ${errors.length} failed.`;
  } else if (loadedCount) {
    batchSummary.value = `Loaded ${loadedCount} set${loadedCount === 1 ? "" : "s"}.`;
  }
}

onMounted(async () => {
  loading.value = true;
  await refreshLists({ forceAvailable: true });
  loading.value = false;
});
</script>

<template>
  <div class="sets-page collection-page">
    <header class="sets-page-header">
      <h1>Sets</h1>
      <p class="sets-page-intro">
        Browse every set family, load catalogs into your library, and manage favourites.
      </p>
    </header>

    <div class="sets-page-toolbar">
      <label class="sets-page-search">
        <span class="sr-only">Filter sets</span>
        <input
          v-model="filterQuery"
          type="search"
          placeholder="Filter sets"
          autocomplete="off"
          spellcheck="false"
        />
      </label>

      <div class="sets-page-filter-chips" role="group" aria-label="Loaded filter">
        <button
          type="button"
          class="sets-page-chip"
          :class="{ 'is-active': statusFilter === 'all' }"
          @click="statusFilter = 'all'"
        >
          All
        </button>
        <button
          type="button"
          class="sets-page-chip"
          :class="{ 'is-active': statusFilter === 'loaded' }"
          @click="statusFilter = 'loaded'"
        >
          Loaded
        </button>
        <button
          type="button"
          class="sets-page-chip"
          :class="{ 'is-active': statusFilter === 'pending' }"
          @click="statusFilter = 'pending'"
        >
          Not loaded
        </button>
        <button
          type="button"
          class="sets-page-chip"
          :class="{ 'is-active': showPromoSets }"
          :aria-pressed="showPromoSets ? 'true' : 'false'"
          title="Show promo set families in the browse list"
          @click="showPromoSets = !showPromoSets"
        >
          Promos
        </button>
        <button
          type="button"
          class="sets-page-chip"
          :class="{ 'is-active': showAlchemySets }"
          :aria-pressed="showAlchemySets ? 'true' : 'false'"
          title="Show Arena / Alchemy set families in the browse list"
          @click="showAlchemySets = !showAlchemySets"
        >
          Alchemy
        </button>
        <button
          type="button"
          class="sets-page-chip"
          :class="{ 'is-active': showDigitalSets }"
          :aria-pressed="showDigitalSets ? 'true' : 'false'"
          title="Show other digital-only set families in the browse list"
          @click="showDigitalSets = !showDigitalSets"
        >
          Digital
        </button>
      </div>

      <div class="sets-page-actions">
        <span v-if="selectedPendingCount" class="sets-page-selection-count">
          {{ selectedPendingCount }} selected
        </span>
        <button
          v-if="selectedPendingCount"
          type="button"
          class="btn btn-secondary btn-small"
          :disabled="batchLoading"
          @click="clearSelection"
        >
          Clear
        </button>
        <button
          type="button"
          class="btn btn-primary btn-small"
          :disabled="!canLoadSelected"
          :aria-busy="batchLoading ? 'true' : 'false'"
          @click="loadSelected"
        >
          {{ batchLoading ? "Loading…" : "Load selected" }}
        </button>
      </div>
    </div>

    <p v-if="batchSummary" class="sets-page-muted">{{ batchSummary }}</p>
    <p v-if="loadError" class="sets-page-error">{{ loadError }}</p>

    <div v-if="showInitialLoading" class="sets-page-empty">
      <LoadingIndicator label="Loading sets…" />
    </div>

    <p v-else-if="!visibleGroups.length" class="sets-page-empty">
      No sets match this filter.
    </p>

    <div v-else class="sets-page-groups">
      <section
        v-for="group in visibleGroups"
        :key="group.key"
        class="sets-page-year-group"
      >
        <div class="sets-page-year-heading-row">
          <h2 class="sets-page-year-heading">{{ group.label }}</h2>
          <button
            v-if="pendingSetsInGroup(group).length"
            type="button"
            class="sets-page-year-select"
            :disabled="batchLoading"
            @click="toggleSelectYear(group)"
          >
            {{ allPendingSelectedInGroup(group) ? "Clear year" : "Select all" }}
            <span class="sets-page-year-select-count">
              ({{ pendingSetsInGroup(group).length }})
            </span>
          </button>
        </div>
        <div class="sets-page-grid">
          <template v-for="set in group.sets" :key="set.setCode">
            <RouterLink
              v-if="!set.pendingImport"
              :to="collectionLink(set)"
              class="sets-tile sets-tile--loaded"
              :class="{ 'is-loading': reloadingSetCode === set.setCode }"
              :title="setDisplayName(set) || set.setCode"
            >
              <button
                type="button"
                class="sets-tile-favorite"
                :class="{ 'is-favorite': set.favorite }"
                :aria-pressed="set.favorite ? 'true' : 'false'"
                :aria-label="set.favorite ? `Unfavourite ${setDisplayName(set) || set.setCode}` : `Favourite ${setDisplayName(set) || set.setCode}`"
                :title="set.favorite ? 'Unfavourite set' : 'Favourite set'"
                @click="toggleFavorite($event, set)"
              >
                {{ set.favorite ? "★" : "☆" }}
              </button>
              <button
                type="button"
                class="sets-tile-reload"
                :class="{ 'is-loading': reloadingSetCode === set.setCode }"
                :aria-label="`Reload ${set.setCode} family catalog from Scryfall`"
                :aria-busy="reloadingSetCode === set.setCode ? 'true' : 'false'"
                title="Reload family catalog from Scryfall"
                @click="reloadCatalog($event, set)"
              >
                <span
                  v-if="reloadingSetCode === set.setCode"
                  class="loading-spinner"
                  aria-hidden="true"
                />
                <span v-else aria-hidden="true">↻</span>
              </button>

              <div class="sets-tile-icon-wrap">
                <img
                  v-if="setIconUri(set)"
                  :src="setIconUri(set)"
                  :alt="`${set.setCode} set icon`"
                  class="sets-tile-icon"
                  loading="lazy"
                  @error="onSetIconError($event, set)"
                >
                <div v-else class="sets-tile-icon-placeholder" aria-hidden="true">
                  {{ set.setCode.slice(0, 3) }}
                </div>
              </div>
              <div class="sets-tile-meta">
                <span class="sets-tile-code">{{ set.setCode }}</span>
                <span class="sets-tile-name">{{ setShortName(set) }}</span>
                <span v-if="countLabel(set)" class="sets-tile-count">{{ countLabel(set) }}</span>
                <span
                  v-if="subsetMembers(set).length"
                  class="sets-tile-subsets"
                  :title="`Also loaded: ${subsetMembers(set).map((m) => m.setCode).join(', ')}`"
                >
                  +{{ subsetMembers(set).map((m) => m.setCode).join(", ") }}
                </span>
              </div>
            </RouterLink>

            <div
              v-else
              class="sets-tile sets-tile--pending"
              :class="{
                'is-selected': isSelected(set),
                'is-loading': isTileLoading(set),
                'is-load-error': Boolean(loadErrors[set.setCode]),
              }"
              role="button"
              tabindex="0"
              :aria-pressed="isSelected(set) ? 'true' : 'false'"
              :aria-label="`Select ${setDisplayName(set) || set.setCode} for loading`"
              :aria-busy="isTileLoading(set) ? 'true' : 'false'"
              :title="setDisplayName(set) || set.setCode"
              @click="toggleSelect(set)"
              @keydown="onPendingKeydown($event, set)"
            >
              <div v-if="isTileLoading(set)" class="sets-tile-loading">
                <LoadingIndicator compact :label="`Loading ${set.setCode}…`" />
              </div>
              <template v-else>
                <span class="sets-tile-check" aria-hidden="true">
                  {{ isSelected(set) ? "✓" : "" }}
                </span>
                <div class="sets-tile-icon-wrap">
                  <img
                    v-if="setIconUri(set)"
                    :src="setIconUri(set)"
                    :alt="`${set.setCode} set icon`"
                    class="sets-tile-icon"
                    loading="lazy"
                    @error="onSetIconError($event, set)"
                  >
                  <div v-else class="sets-tile-icon-placeholder" aria-hidden="true">
                    {{ set.setCode.slice(0, 3) }}
                  </div>
                </div>
                <div class="sets-tile-meta">
                  <span class="sets-tile-code">{{ set.setCode }}</span>
                  <span class="sets-tile-name">{{ setShortName(set) }}</span>
                  <span class="sets-tile-badge sets-tile-badge--pending">Not loaded</span>
                  <span
                    v-if="subsetMembers(set).length"
                    class="sets-tile-subsets"
                    :title="`Will also load: ${subsetMembers(set).map((m) => subsetLabel(m)).join(', ')}`"
                  >
                    +{{ subsetMembers(set).map((m) => m.setCode).join(", ") }}
                  </span>
                  <p v-if="loadErrors[set.setCode]" class="sets-tile-error">
                    {{ loadErrors[set.setCode] }}
                  </p>
                </div>
              </template>
            </div>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>
