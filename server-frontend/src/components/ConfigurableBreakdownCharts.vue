<script setup>
import "../styles/stats.css";
import { computed, ref, watch } from "vue";
import BreakdownHistoryChart from "./BreakdownHistoryChart.vue";
import CollectionTilesModal from "./CollectionTilesModal.vue";
import {
  DEDICATED_BREAKDOWN_CHARTS,
  loadBreakdownCharts,
  normalizeBreakdownChart,
  saveBreakdownCharts,
} from "../utils/breakdownCharts";
import { STATS_HISTORY_VIEW_KEY, useHistoryView } from "../composables/historyView";
import {
  HISTORY_METRIC_CHANGE,
  HISTORY_METRIC_VALUE,
  HISTORY_SCALE_ABSOLUTE,
  HISTORY_SCALE_RELATIVE,
  HISTORY_TOP_SERIES,
  buildHistoryChartView,
  formatHistoryPlotValue,
  historySourceOptions,
  seriesPickerOptions,
} from "../utils/breakdownHistory";

const props = defineProps({
  history: { type: Object, default: () => ({ points: [], hasArtStyles: false }) },
  storageKey: { type: String, default: STATS_HISTORY_VIEW_KEY },
});

const HISTORY_CHART_DEFAULTS = DEDICATED_BREAKDOWN_CHARTS.map((item) => ({
  ...item,
  series: HISTORY_TOP_SERIES,
}));

const sources = computed(() => historySourceOptions(props.history));
const points = computed(() => props.history?.points || []);
const options = computed(() => ({
  sources: sources.value,
  history: props.history,
  defaults: HISTORY_CHART_DEFAULTS,
}));

const { historyView, setHistoryView } = useHistoryView(props.storageKey);
const charts = ref(loadBreakdownCharts(props.storageKey, options.value));
const tilesModal = ref(null);

watch(
  () => [props.storageKey, sources.value.map((source) => source.id).join("|")],
  () => {
    charts.value = loadBreakdownCharts(props.storageKey, options.value);
  },
);

function persist() {
  saveBreakdownCharts(props.storageKey, charts.value, options.value);
}

function chartView(chart) {
  return buildHistoryChartView(points.value, { ...chart, ...historyView.value });
}

function chartTitle(chart) {
  return sources.value.find((item) => item.id === chart.source)?.label || chart.source;
}

function seriesChoices(chart) {
  return seriesPickerOptions(points.value, chart.source, historyView.value);
}

function seriesValueClass(value) {
  if (historyView.value.metric !== HISTORY_METRIC_CHANGE) {
    return "";
  }
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount === 0) {
    return "";
  }
  return amount > 0 ? "reports-gain" : "reports-loss";
}

function updateChart(index, patch) {
  const current = charts.value[index];
  const next = [...charts.value];
  next[index] = normalizeBreakdownChart(
    { ...current, ...patch, id: current.id, source: current.source },
    options.value,
  );
  charts.value = next;
  persist();
}

function openSeriesTiles(scope) {
  tilesModal.value = scope;
}

function closeSeriesTiles() {
  tilesModal.value = null;
}
</script>

<template>
  <div class="breakdown-charts">
    <div class="breakdown-charts-toolbar">
      <div class="button-group" role="group" aria-label="History metric">
        <button
          type="button"
          class="filter-button"
          :class="{ active: historyView.metric === HISTORY_METRIC_VALUE }"
          :aria-pressed="historyView.metric === HISTORY_METRIC_VALUE"
          @click="setHistoryView({ metric: HISTORY_METRIC_VALUE })"
        >
          Price
        </button>
        <button
          type="button"
          class="filter-button"
          :class="{ active: historyView.metric === HISTORY_METRIC_CHANGE }"
          :aria-pressed="historyView.metric === HISTORY_METRIC_CHANGE"
          @click="setHistoryView({ metric: HISTORY_METRIC_CHANGE })"
        >
          Change
        </button>
      </div>
      <div class="button-group" role="group" aria-label="History scale">
        <button
          type="button"
          class="filter-button"
          :class="{ active: historyView.scale === HISTORY_SCALE_ABSOLUTE }"
          :aria-pressed="historyView.scale === HISTORY_SCALE_ABSOLUTE"
          @click="setHistoryView({ scale: HISTORY_SCALE_ABSOLUTE })"
        >
          Absolute
        </button>
        <button
          type="button"
          class="filter-button"
          :class="{ active: historyView.scale === HISTORY_SCALE_RELATIVE }"
          :aria-pressed="historyView.scale === HISTORY_SCALE_RELATIVE"
          @click="setHistoryView({ scale: HISTORY_SCALE_RELATIVE })"
        >
          Relative
        </button>
      </div>
    </div>
    <div class="breakdown-charts-grid">
      <section
        v-for="(chart, index) in charts"
        :key="chart.id"
        class="table-panel breakdown-chart-panel"
        :class="{ 'has-series-list': chart.source !== 'all' }"
      >
        <h3 class="deck-breakdown-chart-title">{{ chartTitle(chart) }}</h3>
        <div class="breakdown-chart-body">
          <nav
            v-if="chart.source !== 'all'"
            class="breakdown-chart-series-list"
            :aria-label="`${chartTitle(chart)} series`"
          >
            <button
              v-for="item in seriesChoices(chart)"
              :key="item.id"
              type="button"
              class="breakdown-chart-series-option"
              :class="{ active: chart.series === item.id }"
              @click="updateChart(index, { series: item.id })"
            >
              <span class="breakdown-chart-series-label">{{ item.label }}</span>
              <span
                v-if="item.value != null"
                class="breakdown-chart-series-value"
                :class="seriesValueClass(item.value)"
              >
                {{ formatHistoryPlotValue(item.value, historyView) }}
              </span>
            </button>
          </nav>

          <BreakdownHistoryChart
            :title="chartTitle(chart)"
            :show-title="false"
            :dates="chartView(chart).dates"
            :series="chartView(chart).series"
            :source="chart.source"
            :metric="historyView.metric"
            :scale="historyView.scale"
            empty-label="Daily snapshots appear here after the first price sync of the day."
            @open-series="openSeriesTiles"
          />
        </div>
      </section>
    </div>
    <CollectionTilesModal
      :open="Boolean(tilesModal)"
      :title="tilesModal?.label || ''"
      :set-code="tilesModal?.setCode || ''"
      :art-style="tilesModal?.artStyle || ''"
      @close="closeSeriesTiles"
    />
  </div>
</template>
