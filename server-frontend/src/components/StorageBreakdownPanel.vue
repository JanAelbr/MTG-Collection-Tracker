<script setup>
import "../styles/stats.css";
import { computed } from "vue";
import { RouterLink } from "vue-router";
import DeckBreakdownChart from "./DeckBreakdownChart.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import { formatEuro, formatProfit } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import { TYPE_CHART_COLORS } from "../utils/mtgTheme";

const props = defineProps({
  breakdown: { type: Object, default: null },
  setIcons: { type: Object, default: () => ({}) },
  setLabels: { type: Object, default: () => ({}) },
  diff: { type: Object, default: null },
});

const FINISH_COLORS = ["#607d8b", "#f9a825", "#8d6e63"];

const totals = computed(() => props.breakdown?.totals || null);
const byFinish = computed(() => props.breakdown?.byFinish || []);
const bySet = computed(() => props.breakdown?.bySet || []);
const topCards = computed(() => props.breakdown?.topCards || []);
const comparing = computed(() => Boolean(props.diff));
const showEmpty = computed(() => {
  if (comparing.value) {
    return false;
  }
  return !totals.value || !totals.value.copies;
});
const setDiffByCode = computed(() => {
  const map = new Map();
  for (const row of props.diff?.bySet || []) {
    map.set(String(row.setCode || "").toUpperCase(), row);
  }
  return map;
});
const savedOnlySets = computed(() => (
  (props.diff?.bySet || []).filter((row) => row.presence === "saved-only")
));
const leftTopCards = computed(() => props.diff?.topCards?.left || []);
const enteredKeys = computed(() => new Set(
  (props.diff?.topCards?.entered || []).map((row) => row.key),
));

const maxSetValue = computed(() => {
  let max = 0;
  for (const row of bySet.value) {
    max = Math.max(max, Number(row.current) || 0);
  }
  return max;
});

const finishChartRows = computed(() =>
  byFinish.value.map((row, index) => ({
    id: String(row.id),
    label: row.label,
    count: row.copies,
    share: row.share,
    colorIndex: index,
  })),
);

const setChartRows = computed(() =>
  bySet.value.map((row, index) => ({
    id: row.setCode,
    label: setLabel(row.setCode),
    count: row.copies,
    share: row.share,
    colorIndex: index % TYPE_CHART_COLORS.length,
  })),
);

function setBarPercent(row) {
  const current = Number(row.current) || 0;
  if (!maxSetValue.value || current <= 0) {
    return 0;
  }
  return Math.max(6, (current / maxSetValue.value) * 100);
}

function setLabel(setCode) {
  const code = String(setCode || "").trim().toUpperCase();
  return props.setLabels?.[code] || props.setLabels?.[setCode] || code;
}

function setIcon(setCode) {
  return props.setIcons?.[setCode] || resolveSetIconUri({ setCode });
}

function cardDetailTo(card) {
  return {
    name: "card",
    params: {
      setCode: card.setCode,
      collectorNumber: card.collectorNumber,
    },
  };
}

function profitClass(value) {
  if (value == null || Number.isNaN(value)) {
    return "";
  }
  return value >= 0 ? "reports-gain" : "reports-loss";
}

function deltaClass(value) {
  if (value == null || Number(value) === 0) {
    return "";
  }
  return Number(value) > 0 ? "reports-gain" : "reports-loss";
}

function formatCountDelta(value) {
  if (value == null || Number.isNaN(value)) {
    return "";
  }
  const number = Number(value);
  if (number === 0) {
    return "0";
  }
  return number > 0 ? `+${number}` : String(number);
}

function totalsDelta(field) {
  return props.diff?.totals?.[field] || null;
}

function setDelta(row) {
  return setDiffByCode.value.get(String(row.setCode || "").toUpperCase()) || null;
}

function topCardKey(card) {
  return [
    String(card.setCode || "").toUpperCase(),
    String(card.collectorNumber || ""),
    String(card.finish ?? 0),
  ].join("|");
}

function topCardDelta(card) {
  return (props.diff?.topCards?.rows || []).find((row) => row.key === topCardKey(card)) || null;
}
</script>

<template>
  <div v-if="showEmpty" class="storage-empty">
    No cards in this location.
  </div>

  <div v-else class="storage-breakdown">
    <div class="stats-hero-grid storage-breakdown-hero">
      <div class="stats-card">
        <span>Current value</span>
        <strong>{{ formatEuro(totals?.current) }}</strong>
        <span
          v-if="totalsDelta('current')"
          class="stats-card-subtext"
          :class="deltaClass(totalsDelta('current').delta)"
        >
          {{ formatProfit(totalsDelta('current').delta) }} vs saved
        </span>
      </div>
      <div v-if="totals?.invested || totalsDelta('invested')?.saved" class="stats-card">
        <span>Invested</span>
        <strong>{{ formatEuro(totals?.invested) }}</strong>
        <span
          v-if="totalsDelta('invested')"
          class="stats-card-subtext"
          :class="deltaClass(totalsDelta('invested').delta)"
        >
          {{ formatProfit(totalsDelta('invested').delta) }} vs saved
        </span>
      </div>
      <div v-if="totals?.profit != null || totalsDelta('profit')?.saved != null" class="stats-card">
        <span>Profit / loss</span>
        <strong :class="profitClass(totals?.profit)">{{ formatProfit(totals?.profit) }}</strong>
        <span
          v-if="totalsDelta('profit')"
          class="stats-card-subtext"
          :class="deltaClass(totalsDelta('profit').delta)"
        >
          {{ formatProfit(totalsDelta('profit').delta) }} vs saved
        </span>
      </div>
      <div class="stats-card">
        <span>Copies</span>
        <strong>{{ totals?.copies || 0 }}</strong>
        <span class="stats-card-subtext">
          {{ totals?.uniquePrints || 0 }} unique prints
          <template v-if="totalsDelta('copies')">
            ·
            <span :class="deltaClass(totalsDelta('copies').delta)">
              {{ formatCountDelta(totalsDelta('copies').delta) }} copies
            </span>
          </template>
        </span>
      </div>
      <div class="stats-card">
        <span>Sets</span>
        <strong>{{ bySet.length }}</strong>
        <span class="stats-card-subtext">in this location</span>
      </div>
      <div v-if="totals?.unpricedCopies" class="stats-card stats-card-unknown">
        <span>Unpriced</span>
        <strong>{{ totals.unpricedCopies }}</strong>
        <span class="stats-card-subtext">
          {{ totals.unpricedCopies === 1 ? "copy" : "copies" }} without market price
        </span>
      </div>
    </div>

    <div class="storage-breakdown-grid">
      <section class="table-panel storage-breakdown-panel">
        <DeckBreakdownChart
          title="By finish"
          :rows="finishChartRows"
          :total="totals?.copies || 0"
          :colors="FINISH_COLORS"
          unit-label="copies"
          empty-label="No finish mix yet."
        />
        <ul v-if="comparing && (props.diff?.byFinish || []).length" class="storage-breakdown-delta-list">
          <li v-for="row in props.diff.byFinish" :key="row.id">
            <span>{{ row.label }}</span>
            <span :class="deltaClass(row.copiesDelta)">{{ formatCountDelta(row.copiesDelta) }} copies</span>
            <span :class="deltaClass(row.valueDelta)">{{ formatProfit(row.valueDelta) }}</span>
          </li>
        </ul>
      </section>

      <section class="table-panel storage-breakdown-panel">
        <DeckBreakdownChart
          title="By set"
          :rows="setChartRows"
          :total="totals?.copies || 0"
          :colors="TYPE_CHART_COLORS"
          unit-label="copies"
          empty-label="No set mix yet."
        />
      </section>
    </div>

    <div class="storage-breakdown-grid">
      <section v-if="bySet.length || savedOnlySets.length" class="table-panel storage-breakdown-panel">
        <h2>Sets by value</h2>
        <table class="reports-table">
          <thead>
            <tr>
              <th>Set</th>
              <th>Copies</th>
              <th>Value</th>
              <th v-if="comparing">vs saved</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in bySet" :key="row.setCode">
              <td>
                <div class="storage-breakdown-location-cell">
                  <img
                    v-if="setIcon(row.setCode)"
                    :src="setIcon(row.setCode)"
                    alt=""
                    class="storage-breakdown-set-icon"
                  >
                  <div class="storage-breakdown-list-meta">
                    <strong>{{ setLabel(row.setCode) }}</strong>
                    <span>{{ row.setCode }} · {{ row.copies }} copies · {{ row.uniquePrints }} prints</span>
                  </div>
                </div>
              </td>
              <td>{{ row.copies }}</td>
              <td class="stats-value-cell">
                <div class="stats-value-bar-wrap">
                  <span
                    class="stats-value-bar"
                    :style="{ width: `${setBarPercent(row)}%` }"
                    :title="`${((row.valueShare || 0) * 100).toFixed(1)}% of location`"
                  />
                  <span class="stats-value-label">{{ formatEuro(row.current) }}</span>
                </div>
              </td>
              <td v-if="comparing">
                <span :class="deltaClass(setDelta(row)?.copiesDelta)">
                  {{ formatCountDelta(setDelta(row)?.copiesDelta) }}
                </span>
                <span :class="deltaClass(setDelta(row)?.valueDelta)">
                  {{ formatProfit(setDelta(row)?.valueDelta) }}
                </span>
              </td>
            </tr>
            <tr v-for="row in savedOnlySets" :key="`saved-${row.setCode}`">
              <td>
                <div class="storage-breakdown-list-meta">
                  <strong>{{ setLabel(row.setCode) }}</strong>
                  <span>{{ row.setCode }} · only in saved</span>
                </div>
              </td>
              <td>0</td>
              <td>{{ formatEuro(0) }}</td>
              <td>
                <span :class="deltaClass(row.copiesDelta)">{{ formatCountDelta(row.copiesDelta) }}</span>
                <span :class="deltaClass(row.valueDelta)">{{ formatProfit(row.valueDelta) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="topCards.length || leftTopCards.length" class="table-panel storage-breakdown-panel">
        <h2>Most valuable prints</h2>
        <ul class="storage-breakdown-card-list">
          <li v-for="card in topCards" :key="`${card.setCode}-${card.collectorNumber}-${card.finish}`">
            <RouterLink :to="cardDetailTo(card)" class="storage-breakdown-card-link">
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                alt=""
                class="storage-breakdown-card-thumb"
                loading="lazy"
              >
              <div class="storage-breakdown-list-meta">
                <strong>
                  {{ card.name }}
                  <CardFinishBadge :finish="card.finish" />
                  <span
                    v-if="enteredKeys.has(topCardKey(card))"
                    class="storage-breakdown-presence"
                  >entered</span>
                </strong>
                <span>
                  {{ setLabel(card.setCode) }} ({{ card.setCode }}) #{{ card.collectorNumber }}
                  · ×{{ card.copyCount }}
                </span>
              </div>
              <span class="storage-breakdown-list-value">
                {{ formatEuro(card.current) }}
                <span
                  v-if="topCardDelta(card)"
                  class="storage-breakdown-delta"
                  :class="deltaClass(topCardDelta(card).valueDelta)"
                >
                  {{ formatProfit(topCardDelta(card).valueDelta) }}
                </span>
              </span>
            </RouterLink>
          </li>
        </ul>
        <p v-if="leftTopCards.length" class="storage-breakdown-left-label">Left the top list</p>
        <ul v-if="leftTopCards.length" class="storage-breakdown-card-list">
          <li v-for="card in leftTopCards" :key="`left-${card.key}`">
            <RouterLink :to="cardDetailTo(card)" class="storage-breakdown-card-link">
              <div class="storage-breakdown-list-meta">
                <strong>
                  {{ card.name }}
                  <CardFinishBadge :finish="card.finish" />
                  <span class="storage-breakdown-presence">left</span>
                </strong>
                <span>
                  {{ setLabel(card.setCode) }} ({{ card.setCode }}) #{{ card.collectorNumber }}
                </span>
              </div>
              <span
                class="storage-breakdown-list-value"
                :class="deltaClass(card.valueDelta)"
              >
                {{ formatProfit(card.valueDelta) }}
              </span>
            </RouterLink>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
