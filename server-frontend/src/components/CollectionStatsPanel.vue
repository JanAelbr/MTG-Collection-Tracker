<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import GalleryLoadingOverlay from "./GalleryLoadingOverlay.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import StatsRarityChart from "./StatsRarityChart.vue";
import {
  completionPercent,
  completionRarityFromPercent,
  formatCompletion,
  formatEuro,
  formatProfit,
  formatRoi,
  setShortName,
} from "../utils/format";
import { finishLabel } from "../utils/finishes";
import { resolveSetIconUri } from "../utils/scryfall";
import { collectionScopeToQuery } from "../utils/setScope";

const props = defineProps({
  stats: { type: Object, default: null },
  sets: { type: Array, default: () => [] },
  setCode: { type: String, default: "All" },
  familyScope: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  /** When true, set rows / unknown-card set icons emit select-set. */
  allowSetDrill: { type: Boolean, default: true },
});

const emit = defineEmits(["select-set"]);

/** @type {import("vue").Ref<"value" | "completion">} */
const primaryMetric = ref("value");
const showFinances = ref(false);

function setRowLabel(code) {
  const set = props.sets.find((item) => item.setCode === code);
  if (!set) {
    return code;
  }
  const name = setShortName(set);
  return set.favorite ? `★ ${name}` : name;
}

function setIconForCode(code) {
  const set = props.sets.find((item) => item.setCode === code);
  return resolveSetIconUri(set || { setCode: code });
}

function profitClass(value) {
  if (value == null || Number.isNaN(value)) {
    return "";
  }
  return value >= 0 ? "reports-gain" : "reports-loss";
}

function sumNullable(left, right) {
  if (left == null && right == null) {
    return null;
  }
  return (left ?? 0) + (right ?? 0);
}

function aggregateArtStylesBySet(artStyles) {
  const grouped = new Map();
  for (const row of artStyles) {
    const key = row.setCode;
    if (!key) {
      continue;
    }
    const prev = grouped.get(key) || {
      setCode: key,
      count: 0,
      current: null,
      invested: null,
      profit: null,
    };
    prev.count += row.count || 0;
    prev.current = sumNullable(prev.current, row.current);
    prev.invested = sumNullable(prev.invested, row.invested);
    prev.profit = sumNullable(prev.profit, row.profit);
    grouped.set(key, prev);
  }
  return [...grouped.values()];
}

const isAllSetsView = computed(() => String(props.setCode).toLowerCase() === "all");
const showSetBreakdown = computed(() => isAllSetsView.value || props.familyScope);
const isValuePrimary = computed(() => primaryMetric.value === "value");

watch(
  showSetBreakdown,
  (bySet) => {
    primaryMetric.value = bySet ? "value" : "completion";
  },
  { immediate: true },
);

function rowCatalogCount(row) {
  if (row?.catalogCount != null && !Number.isNaN(Number(row.catalogCount))) {
    return Number(row.catalogCount);
  }
  const set = props.sets.find((item) => item.setCode === row?.setCode);
  return set?.catalogCount ?? 0;
}

function rowOwnedCount(row) {
  return row?.count ?? 0;
}

function rowCompletionPercent(row) {
  return completionPercent(rowOwnedCount(row), rowCatalogCount(row));
}

function completionBarPercent(row) {
  const percent = rowCompletionPercent(row);
  if (percent == null || percent <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(4, percent));
}

function completionBarClass(row) {
  const percent = rowCompletionPercent(row);
  if (percent == null) {
    return "";
  }
  if (percent >= 100) {
    return "is-complete";
  }
  const rarity = completionRarityFromPercent(percent);
  return rarity ? `is-${rarity}` : "";
}

function formatCollectedPercent(row) {
  const percent = rowCompletionPercent(row);
  if (percent == null) {
    return "—";
  }
  return `${percent.toFixed(percent >= 10 || percent === 0 ? 0 : 1)}%`;
}

function collectedTitle(row) {
  return formatCompletion(rowOwnedCount(row), rowCatalogCount(row));
}

function collectedCountsLabel(row) {
  const owned = rowOwnedCount(row);
  const catalog = rowCatalogCount(row);
  if (!catalog) {
    return `${owned} owned`;
  }
  return `${owned} / ${catalog}`;
}

function valueSharePercent(row) {
  const current = row?.current;
  const total = props.stats?.current;
  if (
    current == null
    || Number.isNaN(current)
    || total == null
    || Number.isNaN(total)
    || total <= 0
  ) {
    return null;
  }
  return (current / total) * 100;
}

function formatValueShare(row) {
  const share = valueSharePercent(row);
  if (share == null) {
    return null;
  }
  return `${share.toFixed(share >= 10 || share === 0 ? 0 : 1)}%`;
}

function formatValuePrimaryLabel(row) {
  const euro = formatEuro(row.current);
  const share = formatValueShare(row);
  return share ? `${euro} · ${share}` : euro;
}

function sortBreakdownRows(rows) {
  return [...rows].sort((a, b) => {
    if (isValuePrimary.value) {
      return (b.current ?? 0) - (a.current ?? 0);
    }
    const completionDiff = (rowCompletionPercent(b) ?? -1) - (rowCompletionPercent(a) ?? -1);
    if (completionDiff !== 0) {
      return completionDiff;
    }
    return (b.current ?? 0) - (a.current ?? 0);
  });
}

const SET_BREAKDOWN_PREVIEW_COUNT = 5;

const setBreakdownRows = computed(() => {
  if (!showSetBreakdown.value || !props.stats) {
    return [];
  }
  const rows = props.stats.setBreakdown?.length
    ? props.stats.setBreakdown
    : aggregateArtStylesBySet(props.stats.artStyles || []);
  return sortBreakdownRows(rows);
});

const setBreakdownExpanded = ref(false);

watch(
  () => props.setCode,
  () => {
    setBreakdownExpanded.value = false;
  },
);

const visibleSetBreakdownRows = computed(() => {
  if (setBreakdownExpanded.value) {
    return setBreakdownRows.value;
  }
  return setBreakdownRows.value.slice(0, SET_BREAKDOWN_PREVIEW_COUNT);
});

const hiddenSetBreakdownCount = computed(() => (
  Math.max(0, setBreakdownRows.value.length - SET_BREAKDOWN_PREVIEW_COUNT)
));

const artStyleRows = computed(() => {
  if (showSetBreakdown.value || !props.stats?.artStyles?.length) {
    return [];
  }
  return sortBreakdownRows(props.stats.artStyles);
});

const maxBreakdownValue = computed(() => {
  const rows = showSetBreakdown.value ? setBreakdownRows.value : artStyleRows.value;
  let max = 0;
  for (const row of rows) {
    const value = row.current;
    if (value != null && !Number.isNaN(value) && value > max) {
      max = value;
    }
  }
  return max;
});

function valueBarPercent(row) {
  const current = row.current;
  if (current == null || Number.isNaN(current) || maxBreakdownValue.value <= 0) {
    return 0;
  }
  return Math.max(6, (current / maxBreakdownValue.value) * 100);
}

function primaryBarPercent(row) {
  return isValuePrimary.value ? valueBarPercent(row) : completionBarPercent(row);
}

function primaryBarClass(row) {
  return isValuePrimary.value ? "is-value" : completionBarClass(row);
}

function primaryLabel(row) {
  return isValuePrimary.value ? formatValuePrimaryLabel(row) : formatCollectedPercent(row);
}

function primaryTitle(row) {
  if (isValuePrimary.value) {
    const share = formatValueShare(row);
    return share
      ? `${formatEuro(row.current)} (${share} of portfolio)`
      : formatEuro(row.current);
  }
  return collectedTitle(row);
}

function secondaryLine(row) {
  if (isValuePrimary.value) {
    const percent = formatCollectedPercent(row);
    return `${collectedCountsLabel(row)} · ${percent}`;
  }
  const share = formatValueShare(row);
  const euro = formatEuro(row.current);
  return share ? `${euro} · ${share}` : euro;
}

const unknownCards = computed(() => props.stats?.unknownCards || []);
const hasUnknownCards = computed(() => (props.stats?.unknownCount ?? 0) > 0);
const unknownModalOpen = ref(false);

function openUnknownModal() {
  unknownModalOpen.value = true;
}

function closeUnknownModal() {
  unknownModalOpen.value = false;
}

function onUnknownEscape(event) {
  if (event.key === "Escape") {
    closeUnknownModal();
  }
}

watch(unknownModalOpen, (open) => {
  if (open) {
    window.addEventListener("keydown", onUnknownEscape);
  } else {
    window.removeEventListener("keydown", onUnknownEscape);
  }
});

onUnmounted(() => {
  window.removeEventListener("keydown", onUnknownEscape);
});

function hasInvestedValue(value) {
  return value != null && !Number.isNaN(Number(value)) && Number(value) !== 0;
}

const showInvestedTile = computed(() => hasInvestedValue(props.stats?.invested));
const hasFinanceData = computed(() => {
  if (showInvestedTile.value) {
    return true;
  }
  if (showSetBreakdown.value) {
    return setBreakdownRows.value.some((row) => hasInvestedValue(row.invested));
  }
  return artStyleRows.value.some((row) => hasInvestedValue(row.invested));
});
const showFinanceColumns = computed(() => showFinances.value && hasFinanceData.value);
const showProfitTile = computed(() => {
  if (!showInvestedTile.value) {
    return false;
  }
  const profit = props.stats?.profit;
  return profit != null && !Number.isNaN(profit);
});
const showRoiTile = computed(() => {
  const profit = props.stats?.profit;
  const invested = props.stats?.invested;
  return (
    showInvestedTile.value
    && profit != null
    && invested != null
    && !Number.isNaN(profit)
    && !Number.isNaN(invested)
    && Number(invested) !== 0
  );
});
const rarityBreakdown = computed(() => (
  !isAllSetsView.value && !props.familyScope ? (props.stats?.rarityBreakdown || []) : []
));
const hasRarityBreakdown = computed(() => rarityBreakdown.value.length > 0);
const hasBreakdown = computed(() => (
  (showSetBreakdown.value && setBreakdownRows.value.length > 0)
  || (!showSetBreakdown.value && artStyleRows.value.length > 0)
));

const raritySetMeta = computed(() => {
  const code = String(props.setCode || "").trim().toUpperCase();
  if (!code || code === "ALL") {
    return { setCode: "", familyRoot: "", iconUri: "" };
  }
  const set = props.sets.find((item) => String(item.setCode || "").toUpperCase() === code);
  return {
    setCode: code,
    familyRoot: set?.familyRoot || "",
    iconUri: set?.iconUri || "",
  };
});

function unknownCardSetCode(card) {
  return card.setCode || card.set_code || "";
}

function unknownCardNumber(card) {
  return String(card.collectorNumber ?? card.collector_number ?? "");
}

function unknownCardFinish(card) {
  return card.finish ?? card.foil ?? 0;
}

function cardDetailLink(card) {
  return {
    name: "card",
    params: {
      setCode: unknownCardSetCode(card),
      collectorNumber: unknownCardNumber(card),
    },
  };
}

function collectionLinkForArtStyle(row) {
  return {
    path: "/collection/all",
    query: collectionScopeToQuery(props.setCode, row.artStyle, false),
  };
}

function onSelectSet(code) {
  if (!props.allowSetDrill || !code || String(code).toLowerCase() === "all") {
    return;
  }
  emit("select-set", code);
}

function setPrimaryMetric(metric) {
  primaryMetric.value = metric;
}
</script>

<template>
  <div class="collection-stats-panel">
    <div v-if="loading && !stats" class="storage-empty">
      <LoadingIndicator label="Loading stats…" />
    </div>
    <p v-else-if="!stats" class="storage-empty">Could not load collection stats.</p>

    <GalleryLoadingOverlay
      v-else-if="stats"
      class="stats-content-loading"
      :loading="loading"
      label="Updating stats…"
    >
      <div class="stats-hero-grid">
        <div
          v-if="!hasUnknownCards"
          class="stats-card stats-card-healthy"
          aria-label="Every owned card has a current market price"
          title="Every owned card has a current market price"
        >
          <span>Pricing</span>
          <strong class="stats-healthy-tile-value">
            <span class="stats-health-check" aria-hidden="true">✓</span>
          </strong>
        </div>
        <button
          v-else
          type="button"
          class="stats-card stats-card-unknown stats-card-action"
          title="Show cards with no current market price"
          @click="openUnknownModal"
        >
          <span>Unknown value</span>
          <strong>{{ formatEuro(stats.unknownInvested) }}</strong>
          <span class="stats-card-subtext">
            {{ stats.unknownCount }} {{ stats.unknownCount === 1 ? "card" : "cards" }}
          </span>
        </button>
        <div class="stats-card">
          <span>Current value</span>
          <strong>{{ formatEuro(stats.current) }}</strong>
        </div>
        <div v-if="showInvestedTile" class="stats-card">
          <span>Invested</span>
          <strong>{{ formatEuro(stats.invested) }}</strong>
        </div>
        <div v-if="showProfitTile" class="stats-card">
          <span>Profit / loss</span>
          <strong :class="profitClass(stats.profit)">{{ formatProfit(stats.profit) }}</strong>
        </div>
        <div v-if="showRoiTile" class="stats-card">
          <span>ROI</span>
          <strong>{{ formatRoi(stats.profit, stats.invested) }}</strong>
        </div>
        <div class="stats-card">
          <span>Owned</span>
          <strong>{{ stats.ownedCount ?? 0 }}</strong>
        </div>
      </div>

      <section
        v-if="!isAllSetsView && hasRarityBreakdown"
        class="table-panel stats-rarity-panel"
        aria-label="Owned by rarity"
      >
        <h2>Owned by rarity</h2>
        <p class="stats-rarity-intro">
          Completion slots you own versus the full set catalog, by rarity.
        </p>
        <StatsRarityChart
          :rows="rarityBreakdown"
          :set-code="raritySetMeta.setCode"
          :family-root="raritySetMeta.familyRoot"
          :icon-uri="raritySetMeta.iconUri"
        />
      </section>

      <Teleport to="body">
        <div
          v-if="unknownModalOpen"
          class="modal-backdrop stats-unknown-modal-backdrop"
          role="presentation"
          @click.self="closeUnknownModal"
        >
          <div
            class="modal-card stats-unknown-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="stats-unknown-modal-title"
          >
            <div class="stats-unknown-modal-head">
              <div>
                <h3 id="stats-unknown-modal-title">Unknown value</h3>
                <p class="stats-unknown-intro">
                  These owned cards have no current market price.
                  Total invested: {{ formatEuro(stats.unknownInvested) }}.
                </p>
              </div>
              <button
                type="button"
                class="btn btn-secondary btn-small"
                @click="closeUnknownModal"
              >
                Close
              </button>
            </div>
            <div class="stats-unknown-modal-body">
              <table class="reports-table">
                <thead>
                  <tr>
                    <th>Set</th>
                    <th>#</th>
                    <th>Name</th>
                    <th>Art style</th>
                    <th>Finish</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(card, index) in unknownCards"
                    :key="`${unknownCardSetCode(card)}-${unknownCardNumber(card)}-${unknownCardFinish(card)}-${index}`"
                  >
                    <td>
                      <div class="stats-set-drill">
                        <button
                          v-if="allowSetDrill"
                          type="button"
                          class="stats-set-drill-icon"
                          :aria-label="`Filter stats to ${setRowLabel(unknownCardSetCode(card))}`"
                          @click="onSelectSet(unknownCardSetCode(card)); closeUnknownModal()"
                        >
                          <img
                            v-if="setIconForCode(unknownCardSetCode(card))"
                            :src="setIconForCode(unknownCardSetCode(card))"
                            alt=""
                            class="stats-set-icon"
                          >
                        </button>
                        <span v-else class="stats-set-drill-icon" aria-hidden="true">
                          <img
                            v-if="setIconForCode(unknownCardSetCode(card))"
                            :src="setIconForCode(unknownCardSetCode(card))"
                            alt=""
                            class="stats-set-icon"
                          >
                        </span>
                        <CollectionSetLink
                          :set-code="unknownCardSetCode(card)"
                          :label="setRowLabel(unknownCardSetCode(card))"
                        />
                      </div>
                    </td>
                    <td>{{ unknownCardNumber(card) }}</td>
                    <td>
                      <RouterLink :to="cardDetailLink(card)" class="stats-art-drill">
                        {{ card.name || "Unknown" }}
                      </RouterLink>
                    </td>
                    <td>{{ card.artStyle || card.art_style || "—" }}</td>
                    <td>{{ finishLabel(unknownCardFinish(card)) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </Teleport>

      <section
        v-if="hasBreakdown"
        class="table-panel stats-breakdown-panel"
        :aria-label="showSetBreakdown ? 'By set' : 'By art style'"
      >
        <div class="stats-breakdown-header">
          <h2>{{ showSetBreakdown ? "By set" : "By art style" }}</h2>
          <div class="stats-breakdown-controls">
            <div class="button-group stats-metric-toggle" role="group" aria-label="Primary metric">
              <button
                type="button"
                class="filter-button"
                :class="{ active: isValuePrimary }"
                :aria-pressed="isValuePrimary"
                @click="setPrimaryMetric('value')"
              >
                Value
              </button>
              <button
                type="button"
                class="filter-button"
                :class="{ active: !isValuePrimary }"
                :aria-pressed="!isValuePrimary"
                @click="setPrimaryMetric('completion')"
              >
                Collected
              </button>
            </div>
            <button
              v-if="hasFinanceData"
              type="button"
              class="btn btn-secondary btn-small"
              :aria-pressed="showFinances"
              @click="showFinances = !showFinances"
            >
              {{ showFinances ? "Hide finances" : "Show finances" }}
            </button>
          </div>
        </div>
        <p class="stats-breakdown-intro">
          <template v-if="isValuePrimary">
            Sorted by market value. Share is percent of this scope’s total.
          </template>
          <template v-else>
            Sorted by completion. Bar shows owned slots versus the catalog.
          </template>
        </p>

        <template v-if="showSetBreakdown">
        <ul
          class="stats-breakdown-list"
          :class="{ 'is-scrollable': setBreakdownExpanded }"
        >
          <li
            v-for="row in visibleSetBreakdownRows"
            :key="row.setCode"
            class="stats-breakdown-row"
            :class="{ 'is-clickable': allowSetDrill }"
            @click="allowSetDrill && onSelectSet(row.setCode)"
          >
            <div class="stats-breakdown-identity">
              <button
                v-if="allowSetDrill"
                type="button"
                class="stats-set-drill-icon"
                :aria-label="`Open stats for ${setRowLabel(row.setCode)}`"
                @click.stop="onSelectSet(row.setCode)"
              >
                <img
                  v-if="setIconForCode(row.setCode)"
                  :src="setIconForCode(row.setCode)"
                  alt=""
                  class="stats-set-icon"
                >
              </button>
              <span v-else class="stats-set-drill-icon" aria-hidden="true">
                <img
                  v-if="setIconForCode(row.setCode)"
                  :src="setIconForCode(row.setCode)"
                  alt=""
                  class="stats-set-icon"
                >
              </span>
              <CollectionSetLink
                :set-code="row.setCode"
                :label="setRowLabel(row.setCode)"
                @click.stop
              />
            </div>
            <div
              class="stats-completion-bar-wrap stats-breakdown-bar"
              :title="primaryTitle(row)"
              :aria-label="primaryTitle(row)"
            >
              <div
                class="stats-completion-bar"
                :class="primaryBarClass(row)"
                :style="{ width: `${primaryBarPercent(row)}%` }"
              />
              <span class="stats-completion-label">{{ primaryLabel(row) }}</span>
            </div>
            <div class="stats-breakdown-meta">
              <span class="stats-breakdown-secondary">{{ secondaryLine(row) }}</span>
              <template v-if="showFinanceColumns">
                <span class="stats-breakdown-finance">
                  Inv {{ formatEuro(row.invested) }}
                </span>
                <span
                  class="stats-breakdown-finance"
                  :class="profitClass(row.profit)"
                >
                  {{ formatProfit(row.profit) }}
                </span>
              </template>
            </div>
          </li>
        </ul>
        <button
          v-if="hiddenSetBreakdownCount"
          type="button"
          class="btn btn-secondary btn-small stats-breakdown-more"
          :aria-expanded="setBreakdownExpanded"
          @click="setBreakdownExpanded = !setBreakdownExpanded"
        >
          {{ setBreakdownExpanded
            ? "Show top 5"
            : `Show all ${setBreakdownRows.length} sets` }}
        </button>
        </template>

        <ul v-else class="stats-breakdown-list">
          <li
            v-for="row in artStyleRows"
            :key="`${row.setCode}-${row.artStyle}`"
            class="stats-breakdown-row"
          >
            <div class="stats-breakdown-identity">
              <RouterLink
                :to="collectionLinkForArtStyle(row)"
                class="stats-art-drill"
              >
                {{ row.artStyle }}
              </RouterLink>
            </div>
            <div
              class="stats-completion-bar-wrap stats-breakdown-bar"
              :title="primaryTitle(row)"
              :aria-label="primaryTitle(row)"
            >
              <div
                class="stats-completion-bar"
                :class="primaryBarClass(row)"
                :style="{ width: `${primaryBarPercent(row)}%` }"
              />
              <span class="stats-completion-label">{{ primaryLabel(row) }}</span>
            </div>
            <div class="stats-breakdown-meta">
              <span class="stats-breakdown-secondary">{{ secondaryLine(row) }}</span>
              <template v-if="showFinanceColumns">
                <span class="stats-breakdown-finance">
                  Inv {{ formatEuro(row.invested) }}
                </span>
                <span
                  class="stats-breakdown-finance"
                  :class="profitClass(row.profit)"
                >
                  {{ formatProfit(row.profit) }}
                </span>
              </template>
            </div>
          </li>
        </ul>
      </section>
    </GalleryLoadingOverlay>
  </div>
</template>
