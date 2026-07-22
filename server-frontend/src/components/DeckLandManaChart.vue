<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import {
  filterManaSourcesByColor,
  MANA_SOURCE_CATEGORIES,
  MANA_SOURCE_CATEGORY_COLORS,
} from "../utils/manaPips";
import CardFinishBadge from "./CardFinishBadge.vue";
import { powerCardRoute } from "../utils/deckPower";

const props = defineProps({
  comparison: { type: Object, required: true },
  deckId: { type: [String, Number], default: "" },
  emptyMessage: {
    type: String,
    default: "No colored mana sources found in this deck yet.",
  },
});

const selectedId = ref(null);
const selectedCategoryId = ref(null);

const rows = computed(() => props.comparison?.rows || []);
const categories = computed(() => props.comparison?.categories || MANA_SOURCE_CATEGORIES);
const hasData = computed(() => Boolean(props.comparison?.hasData && rows.value.length));

const selectedCards = computed(() => (
  filterManaSourcesByColor(props.comparison, selectedId.value, selectedCategoryId.value)
));
const selectedRow = computed(() => rows.value.find((row) => row.id === selectedId.value) || null);
const selectedCategory = computed(() => (
  MANA_SOURCE_CATEGORIES.find((category) => category.id === selectedCategoryId.value) || null
));

const chartHeight = 168;
const chartWidth = 360;
const padding = { top: 12, right: 12, bottom: 34, left: 34 };
const plotWidth = chartWidth - padding.left - padding.right;
const plotHeight = chartHeight - padding.top - padding.bottom;
const groupWidth = computed(() => (rows.value.length ? plotWidth / rows.value.length : plotWidth));
const barWidth = computed(() => Math.min(36, Math.max(18, groupWidth.value * 0.55)));

function barHeight(value) {
  const max = Math.max(1, Number(props.comparison?.maxValue) || 1);
  return (Math.max(0, value) / max) * plotHeight;
}

function groupCenter(index) {
  return padding.left + groupWidth.value * index + groupWidth.value / 2;
}

function formatRatio(ratio) {
  if (ratio == null || Number.isNaN(ratio)) {
    return "—";
  }
  if (ratio >= 10) {
    return `${Math.round(ratio)}×`;
  }
  const rounded = Math.round(ratio * 10) / 10;
  return `${rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1)}×`;
}

function ratioTone(row) {
  if (row.ratio == null) {
    return "is-neutral";
  }
  if (row.ratio < 0.75) {
    return "is-low";
  }
  if (row.ratio > 1.35) {
    return "is-high";
  }
  return "is-balanced";
}

function stackSegments(row) {
  let offset = 0;
  return (row.stacks || []).map((stack) => {
    const height = barHeight(stack.count);
    const segment = {
      ...stack,
      y: padding.top + plotHeight - offset - height,
      height: Math.max(height, stack.count > 0 ? 2 : 0),
      fill: MANA_SOURCE_CATEGORY_COLORS[stack.id] || MANA_SOURCE_CATEGORY_COLORS.other,
    };
    offset += height;
    return segment;
  });
}

const yTicks = computed(() => {
  const max = Math.max(1, Number(props.comparison?.maxValue) || 1);
  const step = max <= 5 ? 1 : max <= 12 ? 2 : Math.ceil(max / 4);
  const ticks = [];
  for (let value = 0; value <= max; value += step) {
    ticks.push(value);
  }
  if (ticks[ticks.length - 1] !== max) {
    ticks.push(max);
  }
  return ticks;
});

function toggleRow(row, categoryId = null) {
  if (!row?.total && !row?.pips) {
    return;
  }
  if (selectedId.value === row.id && selectedCategoryId.value === categoryId) {
    selectedId.value = null;
    selectedCategoryId.value = null;
    return;
  }
  selectedId.value = row.id;
  selectedCategoryId.value = categoryId;
}

watch(
  () => props.comparison,
  () => {
    if (selectedId.value == null) {
      return;
    }
    const row = rows.value.find((item) => item.id === selectedId.value);
    if (!row) {
      selectedId.value = null;
      selectedCategoryId.value = null;
    }
  },
);
</script>

<template>
  <div class="deck-land-mana-chart">
    <div v-if="!hasData" class="deck-land-mana-empty">
      {{ emptyMessage }}
    </div>

    <template v-else>
      <div class="deck-land-mana-body">
        <svg
          class="deck-land-mana-svg"
          :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
          role="img"
          aria-label="Colored mana sources by card type"
        >
          <title>Mana sources by color and card type</title>

          <g class="deck-land-mana-grid">
            <line
              :x1="padding.left"
              :y1="padding.top + plotHeight"
              :x2="padding.left + plotWidth"
              :y2="padding.top + plotHeight"
            />
            <g v-for="tick in yTicks" :key="`tick-${tick}`">
              <line
                :x1="padding.left"
                :y1="padding.top + plotHeight - barHeight(tick)"
                :x2="padding.left + plotWidth"
                :y2="padding.top + plotHeight - barHeight(tick)"
                class="deck-land-mana-grid-line"
              />
              <text
                :x="padding.left - 8"
                :y="padding.top + plotHeight - barHeight(tick) + 4"
                text-anchor="end"
                class="deck-land-mana-axis-label"
              >
                {{ tick }}
              </text>
            </g>
          </g>

          <g class="deck-land-mana-bars">
            <g v-for="(row, index) in rows" :key="row.id">
              <rect
                v-for="segment in stackSegments(row)"
                :key="`${row.id}-${segment.id}`"
                class="deck-land-mana-bar deck-land-mana-bar--stack"
                :class="{
                  'is-clickable': segment.count > 0,
                  'is-selected': selectedId === row.id && selectedCategoryId === segment.id,
                  'is-dimmed': selectedId === row.id && selectedCategoryId && selectedCategoryId !== segment.id,
                }"
                :x="groupCenter(index) - barWidth / 2"
                :y="segment.y"
                :width="barWidth"
                :height="segment.height"
                :fill="segment.fill"
                :tabindex="segment.count > 0 ? 0 : undefined"
                :role="segment.count > 0 ? 'button' : undefined"
                :aria-pressed="segment.count > 0
                  ? selectedId === row.id && selectedCategoryId === segment.id
                  : undefined"
                :aria-label="segment.count > 0
                  ? `View ${segment.count} ${segment.label} for ${row.label}`
                  : undefined"
                @click="toggleRow(row, segment.id)"
                @keydown.enter.prevent="toggleRow(row, segment.id)"
                @keydown.space.prevent="toggleRow(row, segment.id)"
              >
                <title>{{ row.label }} · {{ segment.label }}: {{ segment.count }}</title>
              </rect>
              <text
                :x="groupCenter(index)"
                :y="padding.top + plotHeight + 18"
                text-anchor="middle"
                class="deck-land-mana-axis-label deck-land-mana-axis-label--x"
                :class="{ 'is-clickable': row.total > 0 || row.pips > 0, 'is-selected': selectedId === row.id }"
                :tabindex="(row.total > 0 || row.pips > 0) ? 0 : undefined"
                :role="(row.total > 0 || row.pips > 0) ? 'button' : undefined"
                @click="toggleRow(row, null)"
                @keydown.enter.prevent="toggleRow(row, null)"
                @keydown.space.prevent="toggleRow(row, null)"
              >
                {{ row.label }}
              </text>
            </g>
          </g>
        </svg>

        <aside class="deck-land-mana-ratios" aria-label="Expected versus actual color ratios">
          <header class="deck-land-mana-ratios-head">
            <span>Color</span>
            <span>Expected</span>
            <span>Actual</span>
            <span>Ratio</span>
          </header>
          <ul class="deck-land-mana-ratios-list">
            <li
              v-for="row in rows"
              :key="`ratio-${row.id}`"
              class="deck-land-mana-ratios-row"
              :class="[ratioTone(row), { 'is-selected': selectedId === row.id }]"
            >
              <button
                type="button"
                class="deck-land-mana-ratios-color"
                @click="toggleRow(row, null)"
              >
                {{ row.label }}
              </button>
              <span class="deck-land-mana-ratios-expected">{{ row.pipPercent }}%</span>
              <span class="deck-land-mana-ratios-actual">{{ row.sourcePercent }}%</span>
              <span class="deck-land-mana-ratios-mult">{{ formatRatio(row.ratio) }}</span>
            </li>
          </ul>
        </aside>
      </div>

      <div class="deck-land-mana-legend">
        <span
          v-for="category in categories"
          :key="category.id"
          class="deck-land-mana-legend-item"
        >
          <span
            class="deck-land-mana-swatch"
            :style="{ background: MANA_SOURCE_CATEGORY_COLORS[category.id] }"
          />
          {{ category.label }}
        </span>
        <span v-if="comparison.anyColorCount" class="deck-land-mana-legend-note">
          {{ comparison.anyColorCount }} any-color
          {{ comparison.anyColorCount === 1 ? "source" : "sources" }}
          counted for each color
        </span>
      </div>

      <section v-if="selectedRow" class="deck-land-mana-selection">
        <header class="deck-land-mana-selection-header">
          <h4 class="deck-land-mana-selection-title">
            {{ selectedRow.label }}
            <template v-if="selectedCategory"> · {{ selectedCategory.label }}</template>
          </h4>
          <span class="deck-land-mana-selection-count">
            {{ selectedCards.length || selectedRow.total }}
            {{ (selectedCards.length || selectedRow.total) === 1 ? "card" : "cards" }}
          </span>
        </header>

        <div v-if="selectedCards.length" class="deck-power-card-grid">
          <figure
            v-for="(card, index) in selectedCards"
            :key="`${selectedId}-${selectedCategoryId}-${card.setCode}-${card.collectorNumber}-${card.finish}-${index}`"
            class="deck-power-card"
          >
            <div class="deck-power-card-image-wrap">
              <CardFinishBadge :card="card" variant="overlay" compact />
              <RouterLink
                v-if="powerCardRoute(card, deckId)"
                :to="powerCardRoute(card, deckId)"
                class="deck-power-card-image-link"
              >
                <img
                  v-if="card.imageUri"
                  :src="card.imageUri"
                  :alt="card.cardName"
                  class="deck-power-card-image"
                  loading="lazy"
                >
                <div v-else class="deck-power-card-placeholder">{{ card.cardName }}</div>
              </RouterLink>
              <template v-else>
                <img
                  v-if="card.imageUri"
                  :src="card.imageUri"
                  :alt="card.cardName"
                  class="deck-power-card-image"
                  loading="lazy"
                >
                <div v-else class="deck-power-card-placeholder">{{ card.cardName }}</div>
              </template>
            </div>

            <figcaption class="deck-power-card-caption">
              <RouterLink
                v-if="powerCardRoute(card, deckId)"
                :to="powerCardRoute(card, deckId)"
                class="deck-power-card-name"
              >
                {{ card.cardName }}
              </RouterLink>
              <span v-else class="deck-power-card-name is-plain">{{ card.cardName }}</span>
              <span v-if="card.qty > 1" class="deck-power-card-meta">×{{ card.qty }}</span>
            </figcaption>
          </figure>
        </div>

        <p v-else class="deck-land-mana-selection-empty">
          No sources for this color.
        </p>
      </section>
    </template>
  </div>
</template>
