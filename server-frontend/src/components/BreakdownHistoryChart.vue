<script setup>
import { computed, ref, watch } from "vue";
import { formatPercentChange } from "../utils/format";
import {
  formatHistoryAxisValue,
  formatHistoryPlotValue,
  historyPlotFromZero,
  normalizeHistoryView,
} from "../utils/breakdownHistory";
import { TYPE_CHART_COLORS } from "../utils/mtgTheme";

const props = defineProps({
  title: { type: String, default: "" },
  showTitle: { type: Boolean, default: true },
  dates: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  metric: { type: String, default: "value" },
  scale: { type: String, default: "absolute" },
  emptyLabel: { type: String, default: "No snapshots yet." },
});

const width = 640;
const height = 220;
const view = computed(() => normalizeHistoryView({ metric: props.metric, scale: props.scale }));
const padding = computed(() => ({
  top: 16,
  right: 16,
  bottom: 36,
  left: view.value.metric === "change" && view.value.scale === "absolute" ? 76 : 64,
}));
const plotWidth = computed(() => width - padding.value.left - padding.value.right);
const plotHeight = computed(() => height - padding.value.top - padding.value.bottom);
const hovered = ref(null);
const svgRef = ref(null);
const baselineIndex = ref(0);

watch(
  () => props.dates.join("|"),
  () => {
    baselineIndex.value = 0;
  },
);

const hasPoints = computed(() => props.dates.length > 0 && props.series.some((item) => item.values?.length));
const baselineDate = computed(() => props.dates[baselineIndex.value] || props.dates[0] || "");

function plotValues() {
  const values = [];
  for (const item of props.series) {
    for (const value of item.values || []) {
      values.push(Number(value) || 0);
    }
  }
  return values;
}

function niceStep(span) {
  if (!Number.isFinite(span) || span <= 0) {
    return 1;
  }
  const raw = span / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  if (!Number.isFinite(mag) || mag <= 0) {
    return span;
  }
  const norm = raw / mag;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
}

const yDomain = computed(() => {
  const values = plotValues().filter((value) => Number.isFinite(value));
  let min = values.length ? Math.min(...values) : 0;
  let max = values.length ? Math.max(...values) : 1;
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: 0, max: 1 };
  }
  if (historyPlotFromZero(view.value)) {
    min = Math.min(0, min);
    max = Math.max(0, max, 1);
    return { min, max };
  }
  if (view.value.metric === "change") {
    if (min > 0) {
      min = 0;
    }
    if (max < 0) {
      max = 0;
    }
  }
  if (min === max) {
    const bump = view.value.scale === "relative" ? 5 : Math.max(1, Math.abs(min) * 0.05);
    min -= bump;
    max += bump;
  }
  const pad = (max - min) * 0.08;
  return { min: min - pad, max: max + pad };
});

const yTicks = computed(() => {
  const { min, max } = yDomain.value;
  const span = max - min;
  const step = niceStep(span);
  const start = Math.floor(min / step) * step;
  const ticks = [];
  const limit = 8;
  for (let index = 0; index <= limit; index += 1) {
    const value = Number((start + index * step).toFixed(8));
    if (value > max + step / 2) {
      break;
    }
    ticks.push(value);
  }
  if (min <= 0 && max >= 0 && !ticks.some((tick) => Math.abs(tick) < step / 4)) {
    ticks.push(0);
    ticks.sort((left, right) => left - right);
  }
  return ticks.length ? ticks : [0];
});

const scaleMin = computed(() => Math.min(yDomain.value.min, yTicks.value[0]));
const scaleMax = computed(() => Math.max(
  yDomain.value.max,
  yTicks.value[yTicks.value.length - 1],
  scaleMin.value + 1,
));

function xFor(index) {
  const count = Math.max(props.dates.length - 1, 1);
  return padding.value.left + (index / count) * plotWidth.value;
}

function yFor(value) {
  const amount = Number(value) || 0;
  const range = scaleMax.value - scaleMin.value;
  if (!(range > 0) || !Number.isFinite(range)) {
    return padding.value.top + plotHeight.value;
  }
  return padding.value.top + plotHeight.value - ((amount - scaleMin.value) / range) * plotHeight.value;
}

function linePath(values) {
  return (values || [])
    .map((value, index) => `${index === 0 ? "M" : "L"} ${xFor(index)} ${yFor(value)}`)
    .join(" ");
}

function formatY(value) {
  return formatHistoryAxisValue(value, view.value);
}

function formatPlot(value) {
  return formatHistoryPlotValue(value, view.value);
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

function seriesChange(item) {
  const values = item?.rawValues || item?.values || [];
  if (!values.length) {
    return "";
  }
  const last = values.at(-1);
  const from = Math.min(Math.max(baselineIndex.value, 0), values.length - 1);
  const first = values.slice(from).find((value) => value != null && Number(value) !== 0)
    ?? values[from];
  return formatPercentChange(
    last == null || first == null ? null : Number(last) - Number(first),
    first,
  ).trim();
}

function selectBaseline(dot) {
  baselineIndex.value = baselineIndex.value === dot.index ? 0 : dot.index;
}

const dots = computed(() => {
  const items = [];
  props.series.forEach((item, seriesIndex) => {
    (item.values || []).forEach((value, index) => {
      const raw = item.rawValues || item.values || [];
      const previousRaw = index > 0 ? raw[index - 1] : null;
      const currentRaw = raw[index];
      items.push({
        key: `${item.id}-${index}`,
        index,
        x: xFor(index),
        y: yFor(value),
        color: seriesColor(seriesIndex),
        date: props.dates[index] || "",
        label: item.label,
        value: Number(value) || 0,
        copies: Number(item.copies?.[index]) || 0,
        isBaseline: index === baselineIndex.value,
        change: historyPlotFromZero(view.value)
          ? formatPercentChange(
            previousRaw == null ? null : Number(currentRaw) - Number(previousRaw),
            previousRaw,
          ).trim()
          : "",
      });
    });
  });
  return items;
});

function tooltipPlacement(dot) {
  const svg = svgRef.value;
  if (!svg || !dot) {
    return null;
  }
  const rect = svg.getBoundingClientRect();
  const x = rect.left + (dot.x / width) * rect.width;
  const y = rect.top + (dot.y / height) * rect.height;
  const margin = 12;
  const estimatedWidth = 200;
  const estimatedHeight = 92;
  const preferAbove = y - estimatedHeight - margin > margin;
  let translateX = "-50%";
  if (x - estimatedWidth / 2 < margin) {
    translateX = "0";
  } else if (x + estimatedWidth / 2 > window.innerWidth - margin) {
    translateX = "-100%";
  }
  const translateY = preferAbove ? "calc(-100% - 10px)" : "12px";
  return {
    left: `${Math.round(x)}px`,
    top: `${Math.round(y)}px`,
    transform: `translate(${translateX}, ${translateY})`,
  };
}

const tooltipStyle = computed(() => {
  if (!hovered.value || !hasPoints.value) {
    return { display: "none" };
  }
  return tooltipPlacement(hovered.value) || { display: "none" };
});
</script>

<template>
  <section class="breakdown-history-chart">
    <h3 v-if="showTitle" class="deck-breakdown-chart-title">{{ title }}</h3>
    <p v-if="!hasPoints" class="deck-breakdown-chart-empty">{{ emptyLabel }}</p>
    <template v-else>
      <div class="breakdown-history-plot" @mouseleave="hovered = null">
        <svg
          ref="svgRef"
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
          <line
            v-if="scaleMin < 0 && scaleMax > 0"
            class="breakdown-history-zero"
            :x1="padding.left"
            :x2="width - padding.right"
            :y1="yFor(0)"
            :y2="yFor(0)"
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
          <g v-for="dot in dots" :key="dot.key">
            <circle
              class="breakdown-history-hit"
              :cx="dot.x"
              :cy="dot.y"
              r="10"
              fill="transparent"
              @mouseenter="hovered = dot"
              @click="selectBaseline(dot)"
            />
            <circle
              v-if="dot.isBaseline"
              :cx="dot.x"
              :cy="dot.y"
              r="6"
              fill="none"
              :stroke="dot.color"
              stroke-width="1.75"
              pointer-events="none"
            />
            <circle
              :cx="dot.x"
              :cy="dot.y"
              r="3.5"
              :fill="dot.color"
              pointer-events="none"
            />
          </g>
        </svg>
      </div>
      <Teleport to="body">
        <div
          v-if="hovered"
          class="breakdown-history-tooltip"
          :style="tooltipStyle"
        >
          <strong>{{ hovered.label }}</strong>
          <span>{{ hovered.date }}</span>
          <span>
            {{ formatPlot(hovered.value) }}
            <template v-if="hovered.change"> {{ hovered.change }}</template>
          </span>
          <span v-if="hovered.copies">{{ hovered.copies }} {{ hovered.copies === 1 ? "copy" : "copies" }}</span>
          <span class="breakdown-history-tooltip-hint">Click to measure % from here</span>
        </div>
      </Teleport>
      <p v-if="baselineIndex > 0 && baselineDate" class="breakdown-history-baseline">
        % from {{ baselineDate }}
      </p>
      <ul class="breakdown-history-legend">
        <li v-for="(item, index) in series" :key="item.id">
          <span class="breakdown-history-swatch" :style="{ background: seriesColor(index) }" />
          <span>{{ item.label }}</span>
          <strong>
            {{ formatPlot(item.values.at(-1)) }}
            <span v-if="seriesChange(item)" class="breakdown-history-change">{{ seriesChange(item) }}</span>
          </strong>
        </li>
      </ul>
    </template>
  </section>
</template>
