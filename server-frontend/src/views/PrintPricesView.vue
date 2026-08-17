<script setup>
import "../styles/print-prices.css";
import "../styles/separators.css";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import { api, isApiAbortError } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import PrintPricesListHeader from "../components/PrintPricesListHeader.vue";
import PrintPricesOptionsPanel from "../components/PrintPricesOptionsPanel.vue";
import SeparatorSetPicker from "../components/SeparatorSetPicker.vue";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
import {
  SCOPE_ALL,
  SCOPE_LOADED,
  useSeparatorSetPicker,
} from "../composables/useSeparatorSetPicker";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { FINISH_ETCHED, FINISH_FOIL } from "../utils/finishes";
import { formatEuro } from "../utils/format";
import {
  allArtStyleKeys,
  artStyleSelectionKey,
  buildArtStyleGroups,
  buildPrintPriceRows,
  groupPrintPriceRows,
  mapWithConcurrency,
  PRINT_PRICE_FETCH_CONCURRENCY,
  previewSetStartIndexes,
  slimPrintPriceCard,
  stepPreviewSetIndex,
} from "../utils/printPrices";
import {
  loadPrintPricesState,
  savePrintPricesState,
} from "../utils/printPricesState";

const PAGE_SIZE = 500;
const LOAD_DEBOUNCE_MS = 250;

const picker = useSeparatorSetPicker();
const {
  loading: pickerLoading,
  loadError: pickerLoadError,
  filterQuery,
  setScope,
  showTokenAndArtSets,
  showPromoSets,
  loadedSelectedSets,
  selectedCount,
  visibleSets,
  visibleGroups,
  storageLocations,
  storageSelectSlug,
  storageSelectLoading,
  storageSelectError,
  selectedCodes,
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

const cards = ref([]);
const loadError = ref("");
const strategy = ref("trend");
const minimumPrice = ref("");
const sort = ref("collector");
const ownedOnly = ref(true);
const includeTimestamp = ref(false);
const showSetIcon = ref(true);
const showFullSetName = ref(true);
const fontScale = ref(100);
const columnCount = ref(1);
const generatedAt = ref(null);
const selectedArtStyles = ref(new Set());
const previewIndex = ref(0);
const { settings: pricingSettings } = usePricingSettings();
const { loading: cardsLoading, run } = useAsyncLoad();

let loadTimer = 0;
let persistReady = false;

const priceStrategies = computed(() => pricingSettings.value?.priceStrategies || []);
const artStyleGroups = computed(() => buildArtStyleGroups(cards.value));
const artStyleKeys = computed(() => allArtStyleKeys(artStyleGroups.value));
const rows = computed(() =>
  buildPrintPriceRows(cards.value, {
    strategy: strategy.value,
    minimumPrice: minimumPrice.value,
    ownedOnly: ownedOnly.value,
  }),
);
const groups = computed(() =>
  groupPrintPriceRows(
    rows.value.filter((row) =>
      selectedArtStyles.value.has(artStyleSelectionKey(row.setCode, row.artStyle)),
    ),
    sort.value,
  ),
);
const activeGroup = computed(() => groups.value[previewIndex.value] || null);
const previewSetCount = computed(() => previewSetStartIndexes(groups.value).length);
const showInitialLoading = computed(() => pickerLoading.value && !visibleGroups.value.length);
const listStyle = computed(() => ({
  "--print-prices-font-scale": fontScale.value / 100,
  "--print-prices-columns": columnCount.value,
}));
const strategyLabel = computed(
  () => priceStrategies.value.find((item) => item.id === strategy.value)?.label || strategy.value,
);

function toggleArtStyle(key) {
  const next = new Set(selectedArtStyles.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  selectedArtStyles.value = next;
}

function selectAllArtStyles() {
  selectedArtStyles.value = new Set(artStyleKeys.value);
}

function selectSetArtStyles(group) {
  const next = new Set(selectedArtStyles.value);
  for (const style of group.styles || []) {
    next.add(style.key);
  }
  selectedArtStyles.value = next;
}

function finishIcon(finish) {
  if (finish === FINISH_FOIL) return "✦";
  if (finish === FINISH_ETCHED) return "◆";
  return "";
}

function finishLabel(finish) {
  if (finish === FINISH_FOIL) return "Foil";
  if (finish === FINISH_ETCHED) return "Etched";
  return "Non-foil";
}

function printPrices() {
  if (!groups.value.length) return;
  if (includeTimestamp.value) generatedAt.value = new Date();
  window.print();
}

function handleGroupIconError(event, group) {
  onSetIconError(event, {
    setCode: group.setCode,
    iconUri: group.setIconUri,
  });
}

function stepPreview(delta) {
  const count = groups.value.length;
  if (count < 2) {
    return;
  }
  previewIndex.value = (previewIndex.value + delta + count) % count;
}

function stepPreviewSet(delta) {
  previewIndex.value = stepPreviewSetIndex(groups.value, previewIndex.value, delta);
}

async function fetchSetCards(set, isCurrent) {
  const ownedCards = [];
  let page = 1;
  let fetched = 0;
  let total = Infinity;
  while (fetched < total) {
    if (isCurrent && !isCurrent()) {
      return ownedCards;
    }
    const payload = await api.getManagerSetCards(set.setCode, { page, pageSize: PAGE_SIZE });
    const pageCards = payload?.cards || [];
    fetched += pageCards.length;
    for (const card of pageCards) {
      const slim = slimPrintPriceCard(card, {
        ...set,
        iconUri: setIconUri(set),
      }, { ownedOnly: ownedOnly.value });
      if (slim) {
        ownedCards.push(slim);
      }
    }
    const reportedTotal = Number(payload?.total);
    total = Number.isFinite(reportedTotal) ? reportedTotal : fetched;
    if (!pageCards.length) {
      break;
    }
    page += 1;
  }
  return ownedCards;
}

async function loadCards() {
  const sets = loadedSelectedSets.value;
  loadError.value = "";
  if (!sets.length) {
    cards.value = [];
    selectedArtStyles.value = new Set();
    return;
  }
  try {
    const nextCards = await run(async (isCurrent) => {
      const pages = await mapWithConcurrency(
        sets,
        PRINT_PRICE_FETCH_CONCURRENCY,
        async (set) => {
          if (!isCurrent()) {
            return [];
          }
          try {
            return await fetchSetCards(set, isCurrent);
          } catch (error) {
            if (isApiAbortError(error) || !isCurrent()) {
              return [];
            }
            throw error;
          }
        },
      );
      return isCurrent() ? pages.flat() : undefined;
    });
    if (nextCards) {
      cards.value = nextCards;
    }
  } catch (error) {
    if (isApiAbortError(error)) {
      return;
    }
    loadError.value = error.message || "Could not load cards for the selected sets.";
    cards.value = [];
  }
}

function scheduleLoadCards() {
  window.clearTimeout(loadTimer);
  loadTimer = window.setTimeout(() => {
    loadCards();
  }, LOAD_DEBOUNCE_MS);
}

function persistState() {
  if (!persistReady) {
    return;
  }
  savePrintPricesState({
    filterQuery: filterQuery.value,
    setScope: setScope.value,
    showTokenAndArtSets: showTokenAndArtSets.value,
    showPromoSets: showPromoSets.value,
    selectedCodes: [...selectedCodes.value],
    strategy: strategy.value,
    minimumPrice: minimumPrice.value,
    sort: sort.value,
    ownedOnly: ownedOnly.value,
    includeTimestamp: includeTimestamp.value,
    showSetIcon: showSetIcon.value,
    showFullSetName: showFullSetName.value,
    fontScale: fontScale.value,
    columnCount: columnCount.value,
    selectedArtStyles: [...selectedArtStyles.value],
    previewIndex: previewIndex.value,
  });
}

function applyPrintPricesState(state) {
  filterQuery.value = state.filterQuery;
  setScope.value = state.setScope;
  showTokenAndArtSets.value = state.showTokenAndArtSets;
  showPromoSets.value = state.showPromoSets;
  selectedCodes.value = new Set(state.selectedCodes);
  strategy.value = state.strategy || pricingSettings.value?.priceStrategy || "trend";
  minimumPrice.value = state.minimumPrice;
  sort.value = state.sort;
  ownedOnly.value = state.ownedOnly;
  includeTimestamp.value = state.includeTimestamp;
  showSetIcon.value = state.showSetIcon;
  showFullSetName.value = state.showFullSetName;
  fontScale.value = state.fontScale;
  columnCount.value = state.columnCount;
  selectedArtStyles.value = new Set(state.selectedArtStyles);
  previewIndex.value = state.previewIndex;
}

watch([selectedCodes, ownedOnly], scheduleLoadCards);
watch(groups, (next) => {
  if (previewIndex.value >= next.length) previewIndex.value = 0;
});
watch(includeTimestamp, (enabled) => {
  generatedAt.value = enabled ? new Date() : null;
});
watch(artStyleGroups, (groups) => {
  const available = allArtStyleKeys(groups);
  if (!available.length) {
    return;
  }
  const availableSet = new Set(available);
  const kept = [];
  for (const key of selectedArtStyles.value) {
    if (availableSet.has(key)) {
      kept.push(key);
      continue;
    }
    if (!String(key).includes(":")) {
      for (const full of available) {
        if (full.endsWith(`:${key}`)) {
          kept.push(full);
        }
      }
    }
  }
  selectedArtStyles.value = new Set(kept.length ? kept : available);
});
watch(
  [
    filterQuery,
    setScope,
    showTokenAndArtSets,
    showPromoSets,
    selectedCodes,
    strategy,
    minimumPrice,
    sort,
    ownedOnly,
    includeTimestamp,
    showSetIcon,
    showFullSetName,
    fontScale,
    columnCount,
    selectedArtStyles,
    previewIndex,
  ],
  persistState,
);

onMounted(async () => {
  const saved = loadPrintPricesState();
  await Promise.all([loadPicker(), fetchPricingSettings()]);
  applyPrintPricesState(saved);
  persistReady = true;
});

onUnmounted(() => {
  window.clearTimeout(loadTimer);
});
</script>

<template>
  <div class="print-prices-page separators-page collection-page">
    <div class="print-prices-no-print separators-no-print">
      <header class="separators-page-header">
        <h1>Print prices</h1>
        <p class="separators-page-intro">
          Printable owned-card price lists for selected sets, grouped by art style.
        </p>
      </header>

      <div class="separators-page-toolbar">
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
            <template v-if="groups.length">
              · {{ groups.length }} list{{ groups.length === 1 ? "" : "s" }}
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
            :disabled="!groups.length"
            @click="printPrices"
          >
            Print / Save PDF
          </button>
        </div>
      </div>

      <p v-if="pickerLoadError" class="separators-page-error">{{ pickerLoadError }}</p>
      <p v-else-if="storageSelectError" class="separators-page-error">{{ storageSelectError }}</p>
      <p v-else-if="loadError" class="separators-page-error">{{ loadError }}</p>
      <p v-else-if="cardsLoading" class="separators-page-muted">
        Loading prices for selected sets…
      </p>
      <p v-else class="separators-page-muted">
        One list per art style — collector number, name, and selected strategy price.
      </p>
    </div>

    <div v-if="showInitialLoading" class="separators-page-empty print-prices-no-print">
      <LoadingIndicator label="Loading sets…" />
    </div>

    <div
      v-else
      class="separators-layout separators-layout--with-style print-prices-layout print-prices-no-print"
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

      <PrintPricesOptionsPanel
        v-model:strategy="strategy"
        v-model:minimum-price="minimumPrice"
        v-model:sort="sort"
        v-model:owned-only="ownedOnly"
        v-model:include-timestamp="includeTimestamp"
        v-model:show-set-icon="showSetIcon"
        v-model:show-full-set-name="showFullSetName"
        v-model:font-scale="fontScale"
        v-model:column-count="columnCount"
        :price-strategies="priceStrategies"
        :art-style-groups="artStyleGroups"
        :selected-art-styles="selectedArtStyles"
        @toggle-art-style="toggleArtStyle"
        @select-all-art-styles="selectAllArtStyles"
        @select-set-art-styles="selectSetArtStyles"
      />

      <aside class="separators-preview-panel" aria-label="Price list preview">
        <div class="print-prices-preview-nav">
          <button
            type="button"
            class="print-prices-preview-arrow print-prices-preview-arrow-set"
            :disabled="previewSetCount < 2"
            aria-label="Previous set"
            @click="stepPreviewSet(-1)"
          >
            &lt;&lt;
          </button>
          <button
            type="button"
            class="print-prices-preview-arrow"
            :disabled="groups.length < 2"
            aria-label="Previous art style"
            @click="stepPreview(-1)"
          >
            ‹
          </button>
          <h2 class="separators-preview-heading">Preview</h2>
          <button
            type="button"
            class="print-prices-preview-arrow"
            :disabled="groups.length < 2"
            aria-label="Next art style"
            @click="stepPreview(1)"
          >
            ›
          </button>
          <button
            type="button"
            class="print-prices-preview-arrow print-prices-preview-arrow-set"
            :disabled="previewSetCount < 2"
            aria-label="Next set"
            @click="stepPreviewSet(1)"
          >
            &gt;&gt;
          </button>
        </div>
        <div class="separators-preview-stage print-prices-preview-stage">
          <p v-if="!activeGroup" class="separators-preview-empty">
            Select one or more loaded sets to preview prices.
          </p>
          <div
            v-else
            class="print-prices-preview"
            :style="listStyle"
          >
            <PrintPricesListHeader
              :group="activeGroup"
              :show-set-icon="showSetIcon"
              :show-full-set-name="showFullSetName"
              :include-timestamp="includeTimestamp"
              :generated-at="generatedAt"
              :strategy-label="strategyLabel"
              :minimum-price="minimumPrice"
              :on-icon-error="handleGroupIconError"
            />
            <div class="print-prices-list-rows">
              <div v-for="row in activeGroup.rows" :key="row.id" class="print-prices-list-row">
                <span>{{ row.collectorNumber }}</span>
                <span class="print-prices-list-name" :title="row.name">{{ row.name }}</span>
                <span :title="finishLabel(row.finish)">
                  <span v-if="finishIcon(row.finish)" class="print-prices-finish-icon">
                    {{ finishIcon(row.finish) }}
                  </span>
                  {{ formatEuro(row.price) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <div
      class="print-prices-sheet"
      :style="listStyle"
      aria-hidden="true"
    >
      <section v-for="group in groups" :key="group.id" class="print-prices-print-group">
        <PrintPricesListHeader
          :group="group"
          :show-set-icon="showSetIcon"
          :show-full-set-name="showFullSetName"
          :include-timestamp="includeTimestamp"
          :generated-at="generatedAt"
          :strategy-label="strategyLabel"
          :minimum-price="minimumPrice"
          :on-icon-error="handleGroupIconError"
        />
        <div class="print-prices-list-rows">
          <div v-for="row in group.rows" :key="row.id" class="print-prices-list-row">
            <span>{{ row.collectorNumber }}</span>
            <span class="print-prices-list-name" :title="row.name">{{ row.name }}</span>
            <span>
              <span v-if="finishIcon(row.finish)" class="print-prices-finish-icon">
                {{ finishIcon(row.finish) }}
              </span>
              {{ formatEuro(row.price) }}
            </span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
