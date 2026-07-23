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
});

const FINISH_COLORS = ["#607d8b", "#f9a825", "#8d6e63"];

const totals = computed(() => props.breakdown?.totals || null);
const byFinish = computed(() => props.breakdown?.byFinish || []);
const bySet = computed(() => props.breakdown?.bySet || []);
const topCards = computed(() => props.breakdown?.topCards || []);

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
</script>

<template>
  <div v-if="!totals || !totals.copies" class="storage-empty">
    No cards in this location.
  </div>

  <div v-else class="storage-breakdown">
    <div class="stats-hero-grid storage-breakdown-hero">
      <div class="stats-card">
        <span>Current value</span>
        <strong>{{ formatEuro(totals.current) }}</strong>
      </div>
      <div v-if="totals.invested" class="stats-card">
        <span>Invested</span>
        <strong>{{ formatEuro(totals.invested) }}</strong>
      </div>
      <div v-if="totals.profit != null" class="stats-card">
        <span>Profit / loss</span>
        <strong :class="profitClass(totals.profit)">{{ formatProfit(totals.profit) }}</strong>
      </div>
      <div class="stats-card">
        <span>Copies</span>
        <strong>{{ totals.copies }}</strong>
        <span class="stats-card-subtext">{{ totals.uniquePrints }} unique prints</span>
      </div>
      <div class="stats-card">
        <span>Sets</span>
        <strong>{{ bySet.length }}</strong>
        <span class="stats-card-subtext">in this location</span>
      </div>
      <div v-if="totals.unpricedCopies" class="stats-card stats-card-unknown">
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
          :total="totals.copies"
          :colors="FINISH_COLORS"
          unit-label="copies"
          empty-label="No finish mix yet."
        />
      </section>

      <section class="table-panel storage-breakdown-panel">
        <DeckBreakdownChart
          title="By set"
          :rows="setChartRows"
          :total="totals.copies"
          :colors="TYPE_CHART_COLORS"
          unit-label="copies"
          empty-label="No set mix yet."
        />
      </section>
    </div>

    <div class="storage-breakdown-grid">
      <section v-if="bySet.length" class="table-panel storage-breakdown-panel">
        <h2>Sets by value</h2>
        <table class="reports-table">
          <thead>
            <tr>
              <th>Set</th>
              <th>Copies</th>
              <th>Value</th>
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
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="topCards.length" class="table-panel storage-breakdown-panel">
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
                </strong>
                <span>
                  {{ setLabel(card.setCode) }} ({{ card.setCode }}) #{{ card.collectorNumber }}
                  · ×{{ card.copyCount }}
                </span>
              </div>
              <span class="storage-breakdown-list-value">{{ formatEuro(card.current) }}</span>
            </RouterLink>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
