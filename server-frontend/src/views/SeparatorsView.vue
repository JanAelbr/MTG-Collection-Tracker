<script setup>
import "../styles/separators.css";
import { computed, onMounted, ref, watch } from "vue";

import { api } from "../api";
import BinderSeparator from "../components/BinderSeparator.vue";
import BinderSeparatorStylePanel from "../components/BinderSeparatorStylePanel.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import SeparatorSetPicker from "../components/SeparatorSetPicker.vue";
import StorageSeparator from "../components/StorageSeparator.vue";
import StorageSeparatorStylePanel from "../components/StorageSeparatorStylePanel.vue";
import {
  SCOPE_ALL,
  SCOPE_LOADED,
  useSeparatorSetPicker,
} from "../composables/useSeparatorSetPicker";
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
import {
  buildBinderSeparators,
  buildStorageSeparators,
} from "../utils/separatorItems";

const MODE_STORAGE = "storage";
const MODE_BINDER = "binder";

const picker = useSeparatorSetPicker();
const {
  loading,
  loadError,
  filterQuery,
  setScope,
  showTokenAndArtSets,
  showPromoSets,
  selectedSets,
  selectedCount,
  visibleSets,
  visibleGroups,
  storageLocations,
  storageSelectSlug,
  storageSelectLoading,
  storageSelectError,
  isSelected,
  toggleSelect,
  clearSelection,
  allSelectedInGroup,
  toggleSelectYear,
  selectAllVisible,
  selectAllInStorage,
  setPickerLabel,
  setIconUri,
  onSetIconError,
  loadPicker,
} = picker;

const mode = ref(MODE_STORAGE);
const binderStyle = ref({ ...DEFAULT_BINDER_SEPARATOR_STYLE });
const storageStyle = ref({ ...DEFAULT_STORAGE_SEPARATOR_STYLE });
const previewIndex = ref(0);
const rulesBySetCode = ref(new Map());
const rulesLoading = ref(false);
const rulesError = ref("");

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

function selectPreview(index) {
  previewIndex.value = index;
}

function printSeparators() {
  if (!separators.value.length) {
    return;
  }
  window.print();
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
  await loadPicker();
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
      <SeparatorSetPicker
        :visible-groups="visibleGroups"
        :set-scope="setScope"
        :is-selected="isSelected"
        :all-selected-in-group="allSelectedInGroup"
        :set-picker-label="setPickerLabel"
        :set-icon-uri="setIconUri"
        @toggle-select="toggleSelect"
        @toggle-year="toggleSelectYear"
        @icon-error="onSetIconError"
      />

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
