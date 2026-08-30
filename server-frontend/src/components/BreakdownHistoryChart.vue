<script setup>
import { computed } from "vue";
import { formatEuro } from "../utils/format";
import { TYPE_CHART_COLORS } from "../utils/mtgTheme";

const props = defineProps({
  title: { type: String, default: "" },
  dates: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  emptyLabel: { type: String, default: "No snapshots yet." },
});

const width = 640;
const height = 220;
const padding = { top: 16, right: 16, bottom: 36, left: 64 };
const plotWidth = width - padding.left - padding.right;
const plotHeight = height - padding.top - padding.bottom;

const hasPoints = computed(() => props.dates.length > 0 && props.series.some((item) => item.values?.length));

const maxValue = computed(() => {
  let max = 0;
  for (const item of props.series) {
    for (const value of item.values || []) {
      max = Math.max(max, Number(value) || 0);
    }
  }
  return max;
});

const yTicks = computed(() => {
  const max = maxValue.value;
  if (max <= 0) {
    return [0];
  }
  const step = max <= 5 ? 1 : max <= 20 ? 5 : Math.ceil(max / 4);
  const ticks = [];
  for (let value = 0; value <= max; value += step) {
    ticks.push(value);
  }
  if (ticks[ticks.length - 1] < max) {
    ticks.push(max);
  }
  return ticks;
});

const scaleMax = computed(() => Math.max(maxValue.value, yTicks.value[yTicks.value.length - 1] || 1, 1));

function xFor(index) {
  const count = Math.max(props.dates.length - 1, 1);
  return padding.left + (index / count) * plotWidth;
}

function yFor(value) {
  const amount = Math.max(0, Number(value) || 0);
  return padding.top + plotHeight - (amount / scaleMax.value) * plotHeight;
}

function linePath(values) {
  return (values || [])
    .map((value, index) => `${index === 0 ? "M" : "L"} ${xFor(index)} ${yFor(value)}`)
    .join(" ");
}

function formatY(value) {
  return formatEuro(value);
}

function formatX(date, index) {
  if (!date) {
    return "";
  }
  const show = index === 0
    || index === props.dates.length - 1
    || (props.dates.length > 2 && index === Math.floor((props.dates.length - 1) / 2));
  return show ? date : "";
}

function seriesColor(index) {
  return TYPE_CHART_COLORS[index % TYPE_CHART_COLORS.length];
}

const dots = computed(() => {
  const items = [];
  props.series.forEach((item, seriesIndex) => {
    (item.values || []).forEach((value, index) => {
      items.push({
        key: `${item.id}-${index}`,
        x: xFor(index),
        y: yFor(value),
        color: seriesColor(seriesIndex),
      });
    });
  });
  return items;
});
</script>

<template>
  <section class="breakdown-history-chart">
    <h3 class="deck-breakdown-chart-title">{{ title }}</h3>
    <p v-if="!hasPoints" class="deck-breakdown-chart-empty">{{ emptyLabel }}</p>
    <template v-else>
      <svg
        class="breakdown-history-svg"
        :viewBox="`0 0 ${width} ${height}`"
        role="img"
        :aria-label="title"
      >
        <line
          v-for="tick in yTicks"
          :key="`y-${tick}`"
          class="breakdown-history-grid"
          :x1="padding.left"
          :x2="width - padding.right"
          :y1="yFor(tick)"
          :y2="yFor(tick)"
        />
        <text
          v-for="tick in yTicks"
          :key="`yl-${tick}`"
          class="breakdown-history-axis"
          :x="padding.left - 8"
          :y="yFor(tick) + 4"
          text-anchor="end"
        >
          {{ formatY(tick) }}
        </text>
        <text
          v-for="(date, index) in dates"
          :key="`x-${date}-${index}`"
          class="breakdown-history-axis"
          :x="xFor(index)"
          :y="height - 10"
          text-anchor="middle"
        >
          {{ formatX(date, index) }}
        </text>
        <path
          v-for="(item, index) in series"
          :key="item.id"
          class="breakdown-history-line"
          :d="linePath(item.values)"
          fill="none"
          :stroke="seriesColor(index)"
          stroke-width="2.5"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
        <circle
          v-for="dot in dots"
          :key="dot.key"
          :cx="dot.x"
          :cy="dot.y"
          r="3.5"
          :fill="dot.color"
        />
      </svg>
      <ul class="breakdown-history-legend">
        <li v-for="(item, index) in series" :key="item.id">
          <span class="breakdown-history-swatch" :style="{ background: seriesColor(index) }" />
          <span>{{ item.label }}</span>
          <strong>{{ formatY(item.values.at(-1)) }}</strong>
        </li>
      </ul>
    </template>
  </section>
</template>
