<script setup>
import { computed } from "vue";
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
  return [...grouped.values()].sort((a, b) => a.setCode.localeCompare(b.setCode));
}

const isAllSetsView = computed(() => String(props.setCode).toLowerCase() === "all");
const showSetBreakdown = computed(() => isAllSetsView.value || props.familyScope);

const setBreakdownRows = computed(() => {
  if (!showSetBreakdown.value || !props.stats) {
    return [];
  }
  const rows = props.stats.setBreakdown?.length
    ? props.stats.setBreakdown
    : aggregateArtStylesBySet(props.stats.artStyles || []);
  return [...rows].sort((a, b) => (b.current ?? 0) - (a.current ?? 0));
});

const maxSetValue = computed(() => {
  let max = 0;
  for (const row of setBreakdownRows.value) {
    const value = row.current;
    if (value != null && !Number.isNaN(value) && value > max) {
      max = value;
    }
  }
  return max;
});

function valueBarPercent(row) {
  const current = row.current;
  if (current == null || Number.isNaN(current) || maxSetValue.value <= 0) {
    return 0;
  }
  return Math.max(6, (current / maxSetValue.value) * 100);
}

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

const unknownCards = computed(() => props.stats?.unknownCards || []);
const hasUnknownCards = computed(() => (props.stats?.unknownCount ?? 0) > 0);

function hasInvestedValue(value) {
  return value != null && !Number.isNaN(Number(value)) && Number(value) !== 0;
}

const showInvestedTile = computed(() => hasInvestedValue(props.stats?.invested));
const showFinanceColumns = computed(() => {
  if (showInvestedTile.value) {
    return true;
  }
  if (showSetBreakdown.value) {
    return setBreakdownRows.value.some((row) => hasInvestedValue(row.invested));
  }
  return (props.stats?.artStyles || []).some((row) => hasInvestedValue(row.invested));
});
const showProfitTile = computed(() => {
  if (!showFinanceColumns.value) {
    return false;
  }
  const profit = props.stats?.profit;
  return profit != null && !Number.isNaN(profit);
});
const showRoiTile = computed(() => {
  const profit = props.stats?.profit;
  const invested = props.stats?.invested;
  return (
    showFinanceColumns.value
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
</script>

<template>
  <div class="collection-stats-panel">
    <div v-if="loading && !stats" class="storage-empty">
      <LoadingIndicator label="Loading stats…" />
    </div>

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
        <div v-else class="stats-card stats-card-unknown">
          <span>Unknown value</span>
          <strong>{{ formatEuro(stats.unknownInvested) }}</strong>
          <span class="stats-card-subtext">
            {{ stats.unknownCount }} {{ stats.unknownCount === 1 ? "card" : "cards" }}
          </span>
        </div>
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
          <strong>{{ formatCompletion(stats.ownedCount, stats.catalogCount) }}</strong>
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

      <details
        v-if="hasUnknownCards"
        class="table-panel stats-unknown-panel"
        aria-label="Unknown value"
      >
        <summary class="stats-unknown-summary">
          <h2>Unknown value ({{ stats.unknownCount }})</h2>
        </summary>
        <p class="stats-unknown-intro">
          These owned cards have no current market price.
          Total invested: {{ formatEuro(stats.unknownInvested) }}.
        </p>
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
                    @click="onSelectSet(unknownCardSetCode(card))"
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
      </details>

      <section v-if="showSetBreakdown && setBreakdownRows.length" class="table-panel">
        <h2>By set</h2>
        <table class="reports-table">
          <thead>
            <tr>
              <th>Set</th>
              <th>Cards</th>
              <th>Collected</th>
              <th>Value</th>
              <th v-if="showFinanceColumns">Invested</th>
              <th v-if="showFinanceColumns">Profit / loss</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in setBreakdownRows"
              :key="row.setCode"
              class="stats-set-row"
              :class="{ 'is-clickable': allowSetDrill }"
              @click="allowSetDrill && onSelectSet(row.setCode)"
            >
              <td>
                <div class="stats-set-drill">
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
                  />
                </div>
              </td>
              <td>{{ row.count }}</td>
              <td class="stats-completion-cell">
                <div
                  class="stats-completion-bar-wrap"
                  :title="collectedTitle(row)"
                  :aria-label="collectedTitle(row)"
                >
                  <div
                    class="stats-completion-bar"
                    :class="completionBarClass(row)"
                    :style="{ width: `${completionBarPercent(row)}%` }"
                  />
                  <span class="stats-completion-label">{{ formatCollectedPercent(row) }}</span>
                </div>
              </td>
              <td class="stats-value-cell">
                <div class="stats-value-bar-wrap">
                  <div
                    class="stats-value-bar"
                    :style="{ width: `${valueBarPercent(row)}%` }"
                    :title="`${((row.current ?? 0) / (stats.current || 1) * 100).toFixed(1)}% of portfolio`"
                  />
                  <span class="stats-value-label">{{ formatEuro(row.current) }}</span>
                </div>
              </td>
              <td v-if="showFinanceColumns">{{ formatEuro(row.invested) }}</td>
              <td
                v-if="showFinanceColumns"
                :class="profitClass(row.profit)"
              >
                {{ formatProfit(row.profit) }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="!isAllSetsView && !familyScope && stats.artStyles?.length" class="table-panel">
        <h2>By art style</h2>
        <table class="reports-table">
          <thead>
            <tr>
              <th>Art style</th>
              <th>Cards</th>
              <th>Collected</th>
              <th>Value</th>
              <th v-if="showFinanceColumns">Invested</th>
              <th v-if="showFinanceColumns">Profit / loss</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stats.artStyles" :key="`${row.setCode}-${row.artStyle}`">
              <td>
                <RouterLink
                  :to="collectionLinkForArtStyle(row)"
                  class="stats-art-drill"
                >
                  {{ row.artStyle }}
                </RouterLink>
              </td>
              <td>{{ row.count }}</td>
              <td class="stats-completion-cell">
                <div
                  class="stats-completion-bar-wrap"
                  :title="collectedTitle(row)"
                  :aria-label="collectedTitle(row)"
                >
                  <div
                    class="stats-completion-bar"
                    :class="completionBarClass(row)"
                    :style="{ width: `${completionBarPercent(row)}%` }"
                  />
                  <span class="stats-completion-label">{{ formatCollectedPercent(row) }}</span>
                </div>
              </td>
              <td>{{ formatEuro(row.current) }}</td>
              <td v-if="showFinanceColumns">{{ formatEuro(row.invested) }}</td>
              <td
                v-if="showFinanceColumns"
                :class="profitClass(row.profit)"
              >
                {{ formatProfit(row.profit) }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </GalleryLoadingOverlay>
  </div>
</template>
