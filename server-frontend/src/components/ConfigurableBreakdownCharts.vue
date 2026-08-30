<script setup>
import "../styles/stats.css";
import { computed, ref, watch } from "vue";
import BreakdownHistoryChart from "./BreakdownHistoryChart.vue";
import {
  DEDICATED_BREAKDOWN_CHARTS,
  loadBreakdownCharts,
  normalizeBreakdownChart,
  saveBreakdownCharts,
} from "../utils/breakdownCharts";
import {
  HISTORY_TOP_SERIES,
  buildHistoryChartView,
  historySourceOptions,
  seriesPickerOptions,
} from "../utils/breakdownHistory";

const props = defineProps({
  history: { type: Object, default: () => ({ points: [], hasArtStyles: false }) },
  storageKey: { type: String, default: "settingsBreakdownHistoryCharts" },
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

const charts = ref(loadBreakdownCharts(props.storageKey, options.value));

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
  return buildHistoryChartView(points.value, chart);
}

function chartTitle(chart) {
  return sources.value.find((item) => item.id === chart.source)?.label || chart.source;
}

function seriesChoices(chart) {
  return seriesPickerOptions(points.value, chart.source);
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
</script>

<template>
  <div class="breakdown-charts">
    <div class="breakdown-charts-grid">
      <section
        v-for="(chart, index) in charts"
        :key="chart.id"
        class="table-panel breakdown-chart-panel"
      >
        <div class="breakdown-chart-controls">
          <label class="breakdown-chart-field">
            <span class="visually-hidden">Series</span>
            <select
              :value="chart.series"
              @change="updateChart(index, { series: $event.target.value })"
            >
              <option
                v-for="item in seriesChoices(chart)"
                :key="item.id"
                :value="item.id"
              >
                {{ item.label }}
              </option>
            </select>
          </label>
        </div>

        <BreakdownHistoryChart
          :title="chartTitle(chart)"
          :dates="chartView(chart).dates"
          :series="chartView(chart).series"
          empty-label="Save daily breakdowns from Storage to chart change over time."
        />
      </section>
    </div>
  </div>
</template>
