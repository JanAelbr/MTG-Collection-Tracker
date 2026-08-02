<script setup>
import "../styles/separators.css";
import { computed, onMounted, ref, watch } from "vue";

import { api } from "../api";
import BinderSeparator from "../components/BinderSeparator.vue";
import BinderSeparatorStylePanel from "../components/BinderSeparatorStylePanel.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import StorageSeparator from "../components/StorageSeparator.vue";
import StorageSeparatorStylePanel from "../components/StorageSeparatorStylePanel.vue";
import {
  DEFAULT_BINDER_SEPARATOR_STYLE,
  loadBinderSeparatorStyle,
  saveBinderSeparatorStyle,
} from "../utils/binderSeparatorStyle";
import {
  DEFAULT_STORAGE_SEPARATOR_STYLE,
  loadStorageSeparatorStyle,
  saveStorageSeparatorStyle,
} from "../utils/storageSeparatorStyle";
import { setDisplayName, setShortName } from "../utils/format";
import {
  applySetGalleryIconFallback,
  resolveSetGalleryIconUri,
  resolveSetIconUri,
} from "../utils/scryfall";
import {
  buildBinderSeparators,
  buildStorageSeparators,
  releaseYear,
} from "../utils/separatorItems";
import {
  formatSubsetTypeLabel,
  isSetsPagePromoType,
  isTokenOrArtSetType,
} from "../utils/setBrowserSubsets";

const MODE_STORAGE = "storage";
const MODE_BINDER = "binder";
const SCOPE_LOADED = "loaded";
const SCOPE_ALL = "all";

const trackedSets = ref([]);
const availableSets = ref([]);
const storageLocations = ref([]);
const loading = ref(true);
const loadError = ref("");
const filterQuery = ref("");
const setScope = ref(SCOPE_LOADED);
const showTokenAndArtSets = ref(false);
const showPromoSets = ref(false);
const mode = ref(MODE_STORAGE);
const binderStyle = ref({ ...DEFAULT_BINDER_SEPARATOR_STYLE });
const storageStyle = ref({ ...DEFAULT_STORAGE_SEPARATOR_STYLE });
const selectedCodes = ref(new Set());
const previewIndex = ref(0);
const rulesBySetCode = ref(new Map());
const rulesLoading = ref(false);
const rulesError = ref("");
const storageSelectSlug = ref("");
const storageSelectLoading = ref(false);
const storageSelectError = ref("");

function isSelectableSet(set) {
  return Boolean(set?.setCode) && set.setCode !== "All";
}

function isFamilyRootSet(set) {
  if (!set?.setCode) {
    return false;
  }
  if (set.isFamilyRoot != null) {
    return Boolean(set.isFamilyRoot);
  }
  const root = set.familyRoot || set.setCode;
  return set.setCode === root;
}

function compareSelectableSets(a, b) {
  const rootA = String(a.familyRoot || a.setCode);
  const rootB = String(b.familyRoot || b.setCode);
  const byRoot = rootA.localeCompare(rootB);
  if (byRoot) {
    return byRoot;
  }
  const aIsRoot = isFamilyRootSet(a) ? 0 : 1;
  const bIsRoot = isFamilyRootSet(b) ? 0 : 1;
  if (aIsRoot !== bIsRoot) {
    return aIsRoot - bIsRoot;
  }
  return String(a.setCode).localeCompare(String(b.setCode));
}

const trackedByCode = computed(() => {
  const map = new Map();
  for (const set of trackedSets.value) {
    if (set?.setCode) {
      map.set(set.setCode, set);
    }
  }
  return map;
});

function enrichTrackedSet(set) {
  return {
    ...set,
    familyRoot: set.familyRoot || set.parentSetCode || set.setCode,
    parentSetCode: set.parentSetCode || "",
    iconUri: set.iconUri || "",
    familyMembers: set.familyMembers || [set.setCode],
    releasedAt: set.releasedAt || "",
    isFamilyRoot: isFamilyRootSet(set),
    pendingImport: false,
  };
}

function enrichAvailableSet(set) {
  const setCode = String(set.setCode || "").trim();
  const name = String(set.name || "").trim();
  const label = name ? `${name} (${setCode})` : setCode;
  return {
    setCode,
    label,
    name: name || setCode,
    iconUri: set.iconUri || "",
    setType: set.setType,
    parentSetCode: set.parentSetCode || "",
    familyMembers: set.familyMembers || [setCode],
    familyRoot: setCode,
    isFamilyRoot: true,
    ownedCount: 0,
    catalogCount: 0,
    favorite: false,
    pendingImport: true,
    releasedAt: set.releasedAt || "",
    digital: Boolean(set.digital),
  };
}

/** Full catalog used for selection resolution (tracked + available). */
const catalogSets = computed(() => {
  const tracked = trackedSets.value
    .filter((set) => isSelectableSet(set))
    .map(enrichTrackedSet);
  const trackedCodes = new Set(tracked.map((set) => set.setCode));
  const available = availableSets.value
    .filter((set) => isSelectableSet(set) && !trackedCodes.has(set.setCode))
    .map(enrichAvailableSet);
  return [...tracked, ...available].sort(compareSelectableSets);
});

const selectableSets = computed(() => {
  if (setScope.value === SCOPE_ALL) {
    return catalogSets.value;
  }
  // Loaded = every imported/tracked set, including subsets (HOC, tokens, …).
  return catalogSets.value.filter((set) => !set.pendingImport);
});

function setMatchesQuery(set, query) {
  if (!query) {
    return true;
  }
  const typeLabel = formatSubsetTypeLabel(set.setType);
  const haystack = [
    set.setCode,
    set.label,
    setDisplayName(set),
    setShortName(set),
    set.setType,
    typeLabel,
    set.familyRoot,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

function setPickerLabel(set) {
  return setDisplayName(set) || set.setCode;
}

function setGroupYear(set) {
  const rootCode = set.familyRoot || set.setCode;
  const root = trackedByCode.value.get(rootCode);
  return releaseYear(root) || releaseYear(set) || "unknown";
}

const visibleSets = computed(() => {
  const query = filterQuery.value.trim().toLowerCase();
  return selectableSets.value.filter((set) => {
    if (!query) {
      if (!showTokenAndArtSets.value && isTokenOrArtSetType(set.setType)) {
        return false;
      }
      if (!showPromoSets.value && isSetsPagePromoType(set.setType)) {
        return false;
      }
    }
    return setMatchesQuery(set, query);
  });
});

const visibleGroups = computed(() => {
  const favorites = [];
  const byYear = new Map();

  for (const set of visibleSets.value) {
    if (set.favorite && isFamilyRootSet(set)) {
      favorites.push(set);
      continue;
    }
    const year = setGroupYear(set);
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
      sets: [...favorites].sort(compareSelectableSets),
    });
  }
  for (const year of years) {
    groups.push({
      key: year,
      label: year === "unknown" ? "Unknown year" : year,
      sets: [...byYear.get(year)].sort(compareSelectableSets),
    });
  }
  return groups;
});

const selectedSets = computed(() => {
  const selected = [];
  for (const set of catalogSets.value) {
    if (selectedCodes.value.has(set.setCode)) {
      selected.push(set);
    }
  }
  return selected;
});

const selectedCount = computed(() => selectedCodes.value.size);

const separators = computed(() => {
  if (mode.value === MODE_BINDER) {
    return buildBinderSeparators(selectedSets.value, rulesBySetCode.value);
  }
  return buildStorageSeparators(selectedSets.value);
});

const activeSeparator = computed(() => {
  if (!separators.value.length) {
    return null;
  }
  const index = Math.min(Math.max(previewIndex.value, 0), separators.value.length - 1);
  return separators.value[index];
});

const showInitialLoading = computed(() =>
  loading.value && !visibleGroups.value.length,
);

function isSelected(set) {
  return selectedCodes.value.has(set.setCode);
}

function toggleSelect(set) {
  if (!set?.setCode) {
    return;
  }
  const next = new Set(selectedCodes.value);
  if (next.has(set.setCode)) {
    next.delete(set.setCode);
  } else {
    next.add(set.setCode);
  }
  selectedCodes.value = next;
}

function clearSelection() {
  selectedCodes.value = new Set();
}

function allSelectedInGroup(group) {
  const sets = group?.sets || [];
  if (!sets.length) {
    return false;
  }
  return sets.every((set) => selectedCodes.value.has(set.setCode));
}

function toggleSelectYear(group) {
  const sets = group?.sets || [];
  if (!sets.length) {
    return;
  }
  const next = new Set(selectedCodes.value);
  if (allSelectedInGroup(group)) {
    for (const set of sets) {
      next.delete(set.setCode);
    }
  } else {
    for (const set of sets) {
      next.add(set.setCode);
    }
  }
  selectedCodes.value = next;
}

function selectAllVisible() {
  const next = new Set(selectedCodes.value);
  for (const set of visibleSets.value) {
    next.add(set.setCode);
  }
  selectedCodes.value = next;
}

async function selectAllInStorage(slug) {
  const locationSlug = String(slug || "").trim();
  storageSelectSlug.value = locationSlug;
  storageSelectError.value = "";
  if (!locationSlug) {
    return;
  }
  storageSelectLoading.value = true;
  try {
    const payload = await api.getStorageLocationCards(locationSlug);
    const codesInLocation = new Set();
    for (const card of payload?.cards || []) {
      const code = String(card.setCode || "").trim().toUpperCase();
      if (code) {
        codesInLocation.add(code);
      }
    }
    const selectableByCode = new Map(
      catalogSets.value
        .filter((set) => !set.pendingImport)
        .map((set) => [String(set.setCode || "").trim().toUpperCase(), set.setCode]),
    );
    const next = new Set();
    for (const code of codesInLocation) {
      const selectableCode = selectableByCode.get(code);
      if (selectableCode) {
        next.add(selectableCode);
      }
    }
    selectedCodes.value = next;
    if (!next.size) {
      storageSelectError.value = "No tracked sets found in that storage location.";
    }
  } catch (error) {
    storageSelectError.value = error.message || "Could not load storage location.";
  } finally {
    storageSelectLoading.value = false;
    storageSelectSlug.value = "";
  }
}

function setIconUri(set) {
  // Prefer API iconUri — for subsets the backend already resolves the family-root SVG.
  return resolveSetIconUri(set) || resolveSetGalleryIconUri(set);
}

function onSetIconError(event, set) {
  applySetGalleryIconFallback(event.target, set);
}

function selectPreview(index) {
  previewIndex.value = index;
}

function printSeparators() {
  if (!separators.value.length) {
    return;
  }
  window.print();
}

async function loadTrackedSets() {
  loadError.value = "";
  try {
    const payload = await api.listManagerSets();
    trackedSets.value = payload?.sets || [];
  } catch (error) {
    loadError.value = error.message || "Could not load sets.";
    trackedSets.value = [];
  }
}

async function loadAvailableSets() {
  try {
    const payload = await api.listAvailableManagerSets();
    availableSets.value = payload?.sets || [];
  } catch {
    availableSets.value = [];
  }
}

async function loadStorageLocations() {
  try {
    const payload = await api.listStorageLocations();
    storageLocations.value = payload?.locations || [];
  } catch {
    storageLocations.value = [];
  }
}

async function loadArtStyleRules(codes) {
  const needed = codes.filter((code) => !rulesBySetCode.value.has(code));
  if (!needed.length) {
    return;
  }
  rulesLoading.value = true;
  rulesError.value = "";
  try {
    const results = await Promise.all(
      needed.map(async (setCode) => {
        try {
          const payload = await api.getManagerArtStyleRules(setCode);
          return { setCode, rules: payload?.rules || [], error: "" };
        } catch (error) {
          return {
            setCode,
            rules: [],
            error: error.message || `Could not load art styles for ${setCode}.`,
          };
        }
      }),
    );
    const next = new Map(rulesBySetCode.value);
    const errors = [];
    for (const result of results) {
      next.set(result.setCode, result.rules);
      if (result.error) {
        errors.push(result.error);
      }
    }
    rulesBySetCode.value = next;
    if (errors.length) {
      rulesError.value = errors[0];
    }
  } finally {
    rulesLoading.value = false;
  }
}

watch(
  separators,
  (items) => {
    if (!items.length) {
      previewIndex.value = 0;
      return;
    }
    if (previewIndex.value >= items.length) {
      previewIndex.value = 0;
    }
  },
);

watch(
  binderStyle,
  (next) => {
    saveBinderSeparatorStyle(next);
  },
  { deep: true },
);

watch(
  storageStyle,
  (next) => {
    saveStorageSeparatorStyle(next);
  },
  { deep: true },
);

watch(
  [mode, selectedSets],
  async ([nextMode, sets]) => {
    if (nextMode !== MODE_BINDER) {
      return;
    }
    const codes = sets.filter((set) => !set.pendingImport).map((set) => set.setCode);
    await loadArtStyleRules(codes);
  },
);

onMounted(async () => {
  binderStyle.value = loadBinderSeparatorStyle();
  storageStyle.value = loadStorageSeparatorStyle();
  loading.value = true;
  await Promise.all([loadTrackedSets(), loadAvailableSets(), loadStorageLocations()]);
  loading.value = false;
});
</script>

<template>
  <div class="separators-page collection-page">
    <div class="separators-no-print">
      <header class="separators-page-header">
        <h1>Separators</h1>
        <p class="separators-page-intro">
          Printable storage dividers or binder inserts for selected sets.
        </p>
      </header>

      <div class="separators-page-toolbar">
        <div class="separators-mode" role="group" aria-label="Separator type">
          <button
            type="button"
            class="separators-mode-btn"
            :class="{ 'is-active': mode === MODE_STORAGE }"
            @click="mode = MODE_STORAGE"
          >
            Storage
          </button>
          <button
            type="button"
            class="separators-mode-btn"
            :class="{ 'is-active': mode === MODE_BINDER }"
            @click="mode = MODE_BINDER"
          >
            Binder
          </button>
        </div>

        <label class="separators-page-search">
          <span class="sr-only">Filter sets</span>
          <input
            v-model="filterQuery"
            type="search"
            placeholder="Filter sets"
            autocomplete="off"
            spellcheck="false"
          />
        </label>

        <div class="separators-scope" role="group" aria-label="Set scope">
          <button
            type="button"
            class="separators-mode-btn"
            :class="{ 'is-active': setScope === SCOPE_LOADED }"
            @click="setScope = SCOPE_LOADED"
          >
            Loaded
          </button>
          <button
            type="button"
            class="separators-mode-btn"
            :class="{ 'is-active': setScope === SCOPE_ALL }"
            @click="setScope = SCOPE_ALL"
          >
            All
          </button>
          <button
            type="button"
            class="separators-mode-btn"
            :class="{ 'is-active': showTokenAndArtSets }"
            :aria-pressed="showTokenAndArtSets ? 'true' : 'false'"
            title="Show token and art sets in the list"
            @click="showTokenAndArtSets = !showTokenAndArtSets"
          >
            Tokens &amp; art
          </button>
          <button
            type="button"
            class="separators-mode-btn"
            :class="{ 'is-active': showPromoSets }"
            :aria-pressed="showPromoSets ? 'true' : 'false'"
            title="Show promo sets in the list"
            @click="showPromoSets = !showPromoSets"
          >
            Promos
          </button>
        </div>

        <div class="separators-page-actions">
          <span v-if="selectedCount" class="separators-page-selection-count">
            {{ selectedCount }} selected
            <template v-if="separators.length">
              · {{ separators.length }} separator{{ separators.length === 1 ? "" : "s" }}
            </template>
          </span>
          <button
            v-if="selectedCount"
            type="button"
            class="btn btn-secondary btn-small"
            @click="clearSelection"
          >
            Clear
          </button>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!visibleSets.length"
            @click="selectAllVisible"
          >
            Select all
          </button>
          <label class="separators-storage-select">
            <span class="sr-only">Select all sets in a storage location</span>
            <select
              :value="storageSelectSlug"
              :disabled="storageSelectLoading || !storageLocations.length"
              @change="selectAllInStorage($event.target.value)"
            >
              <option value="">
                {{ storageSelectLoading ? "Loading storage…" : "All in storage…" }}
              </option>
              <option
                v-for="location in storageLocations"
                :key="location.slug"
                :value="location.slug"
              >
                All in {{ location.label || location.slug }}
              </option>
            </select>
          </label>
          <button
            type="button"
            class="btn btn-primary btn-small"
            :disabled="!separators.length"
            @click="printSeparators"
          >
            Print / Save PDF
          </button>
        </div>
      </div>

      <p v-if="loadError" class="separators-page-error">{{ loadError }}</p>
      <p v-else-if="storageSelectError" class="separators-page-error">{{ storageSelectError }}</p>
      <p v-else-if="rulesError" class="separators-page-error">{{ rulesError }}</p>
      <p v-else-if="mode === MODE_BINDER && rulesLoading" class="separators-page-muted">
        Loading art styles…
      </p>
      <p v-else-if="mode === MODE_STORAGE" class="separators-page-muted">
        One taller divider per set — sleeve width, set label on the top tab.
      </p>
      <p v-else class="separators-page-muted">
        Card-sized inserts — one per set art style, with collector number range.
      </p>
    </div>

    <div v-if="showInitialLoading" class="separators-page-empty separators-no-print">
      <LoadingIndicator label="Loading sets…" />
    </div>

    <div
      v-else
      class="separators-layout separators-no-print"
      :class="{ 'separators-layout--with-style': true }"
    >
      <div class="separators-picker">
        <p v-if="!visibleGroups.length" class="separators-page-empty">
          {{
            setScope === SCOPE_LOADED
              ? "No loaded sets match this filter."
              : "No sets match this filter."
          }}
        </p>

        <section
          v-for="group in visibleGroups"
          :key="group.key"
          class="separators-year-group"
        >
          <div class="separators-year-heading-row">
            <h2 class="separators-year-heading">{{ group.label }}</h2>
            <button
              type="button"
              class="separators-year-select"
              @click="toggleSelectYear(group)"
            >
              {{ allSelectedInGroup(group) ? "Clear year" : "Select year" }}
            </button>
          </div>
          <div class="separators-set-grid">
            <button
              v-for="set in group.sets"
              :key="set.setCode"
              type="button"
              class="separators-set-tile"
              :class="{
                'is-selected': isSelected(set),
                'is-pending': set.pendingImport,
              }"
              :aria-pressed="isSelected(set) ? 'true' : 'false'"
              @click="toggleSelect(set)"
            >
              <input
                class="separators-set-tile-check"
                type="checkbox"
                tabindex="-1"
                :checked="isSelected(set)"
                @click.stop="toggleSelect(set)"
              />
              <img
                v-if="setIconUri(set)"
                class="separators-set-tile-icon"
                :src="setIconUri(set)"
                alt=""
                loading="lazy"
                @error="onSetIconError($event, set)"
              />
              <span class="separators-set-tile-label">
                {{ setPickerLabel(set) }}
              </span>
              <span v-if="set.pendingImport" class="separators-set-tile-badge">
                Not loaded
              </span>
            </button>
          </div>
        </section>
      </div>

      <BinderSeparatorStylePanel
        v-if="mode === MODE_BINDER"
        v-model="binderStyle"
        class="separators-no-print"
      />
      <StorageSeparatorStylePanel
        v-else
        v-model="storageStyle"
        class="separators-no-print"
      />

      <aside class="separators-preview-panel" aria-label="Separator preview">
        <h2 class="separators-preview-heading">Preview</h2>
        <div class="separators-preview-stage">
          <p v-if="!activeSeparator" class="separators-preview-empty">
            Select one or more sets to preview separators.
          </p>
          <BinderSeparator
            v-else-if="activeSeparator.mode === MODE_BINDER"
            :set-code="activeSeparator.setCode"
            :family-root="activeSeparator.familyRoot"
            :icon-uri="activeSeparator.iconUri"
            :set-name="activeSeparator.setName"
            :art-style="activeSeparator.artStyle"
            :number-range="activeSeparator.numberRange"
            :seed="activeSeparator.id"
            :style-settings="binderStyle"
          />
          <StorageSeparator
            v-else
            :set-code="activeSeparator.setCode"
            :family-root="activeSeparator.familyRoot"
            :icon-uri="activeSeparator.iconUri"
            :set-name="activeSeparator.setName"
            :year="activeSeparator.year"
            :style-settings="storageStyle"
          />
        </div>

        <div v-if="separators.length > 1" class="separators-thumb-strip" role="list">
          <button
            v-for="(item, index) in separators"
            :key="item.id"
            type="button"
            class="separators-thumb"
            :class="{ 'is-active': index === previewIndex }"
            role="listitem"
            @click="selectPreview(index)"
          >
            {{ item.previewLabel }}
          </button>
        </div>
      </aside>
    </div>

    <div class="separators-print-sheet" aria-hidden="true">
      <template v-for="item in separators" :key="`print-${item.id}`">
        <BinderSeparator
          v-if="item.mode === MODE_BINDER"
          :set-code="item.setCode"
          :family-root="item.familyRoot"
          :icon-uri="item.iconUri"
          :set-name="item.setName"
          :art-style="item.artStyle"
          :number-range="item.numberRange"
          :seed="item.id"
          :style-settings="binderStyle"
        />
        <StorageSeparator
          v-else
          :set-code="item.setCode"
          :family-root="item.familyRoot"
          :icon-uri="item.iconUri"
          :set-name="item.setName"
          :year="item.year"
          :style-settings="storageStyle"
        />
      </template>
    </div>
  </div>
</template>
