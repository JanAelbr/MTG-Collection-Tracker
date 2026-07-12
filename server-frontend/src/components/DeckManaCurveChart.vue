<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { buildManaCurveChartData, filterCardsByManaBucket, manaBucketLabel } from "../utils/manaCurve";
import { powerCardRoute } from "../utils/deckPower";
import { cardDisplayName } from "../utils/finishes";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  deckId: { type: [String, Number], default: "" },
});

const selectedBucket = ref(null);

const chart = computed(() => buildManaCurveChartData(props.cards));

const selectedCards = computed(() => {
  if (selectedBucket.value == null) {
    return [];
  }
  return filterCardsByManaBucket(props.cards, selectedBucket.value);
});

const selectedBucketMeta = computed(() => (
  chart.value.buckets.find((bucket) => bucket.id === selectedBucket.value) || null
));

const chartHeight = 160;
const chartWidth = 360;
const padding = { top: 12, right: 12, bottom: 34, left: 34 };
const plotWidth = chartWidth - padding.left - padding.right;
const plotHeight = chartHeight - padding.top - padding.bottom;
const groupWidth = plotWidth / chart.value.buckets.length;
const barWidth = Math.min(14, groupWidth * 0.28);
const barGap = 4;

function barHeight(value) {
  return (Math.max(0, value) / chart.value.maxCount) * plotHeight;
}

function groupCenter(index) {
  return padding.left + groupWidth * index + groupWidth / 2;
}

const yTicks = computed(() => {
  const max = chart.value.maxCount;
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

function toggleBucket(bucket) {
  if (!bucket.actual) {
    return;
  }
  selectedBucket.value = selectedBucket.value === bucket.id ? null : bucket.id;
}

watch(
  () => props.cards,
  () => {
    if (selectedBucket.value == null) {
      return;
    }
    const bucket = chart.value.buckets.find((item) => item.id === selectedBucket.value);
    if (!bucket?.actual) {
      selectedBucket.value = null;
    }
  },
);
</script>

<template>
  <div class="deck-mana-curve-chart">
    <div v-if="!chart.hasData" class="deck-mana-curve-empty">
      No mana-cost data for nonland spells yet. Open the Power tab again after a moment —
      missing CMC is fetched from Scryfall automatically on first load.
    </div>

    <template v-else>
      <div class="deck-mana-curve-meta">
        <span>{{ chart.total }} nonland spells charted</span>
        <span v-if="chart.averageCmc != null">Avg CMC {{ chart.averageCmc }}</span>
      </div>

      <svg
        class="deck-mana-curve-svg"
        :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
        role="img"
        aria-label="Deck mana curve compared to an ideal Commander curve"
      >
        <title>Deck mana curve vs ideal Commander curve</title>

        <g class="deck-mana-curve-grid">
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
              class="deck-mana-curve-grid-line"
            />
            <text
              :x="padding.left - 8"
              :y="padding.top + plotHeight - barHeight(tick) + 4"
              text-anchor="end"
              class="deck-mana-curve-axis-label"
            >
              {{ tick }}
            </text>
          </g>
        </g>

        <g class="deck-mana-curve-bars">
          <g
            v-for="(bucket, index) in chart.buckets"
            :key="bucket.id"
          >
            <rect
              class="deck-mana-curve-bar deck-mana-curve-bar--ideal"
              :x="groupCenter(index) - barWidth - barGap / 2"
              :y="padding.top + plotHeight - barHeight(bucket.ideal)"
              :width="barWidth"
              :height="barHeight(bucket.ideal)"
              :rx="3"
            >
              <title>Ideal {{ bucket.label }}: {{ bucket.ideal }} ({{ bucket.idealPercent }}%)</title>
            </rect>
            <rect
              class="deck-mana-curve-bar deck-mana-curve-bar--actual"
              :class="{
                'is-clickable': bucket.actual > 0,
                'is-selected': selectedBucket === bucket.id,
              }"
              :x="groupCenter(index) + barGap / 2"
              :y="padding.top + plotHeight - barHeight(bucket.actual)"
              :width="barWidth"
              :height="Math.max(barHeight(bucket.actual), bucket.actual > 0 ? 4 : 0)"
              :rx="3"
              :tabindex="bucket.actual > 0 ? 0 : undefined"
              :role="bucket.actual > 0 ? 'button' : undefined"
              :aria-pressed="bucket.actual > 0 ? selectedBucket === bucket.id : undefined"
              :aria-label="bucket.actual > 0 ? `View ${bucket.actual} cards at CMC ${bucket.label}` : undefined"
              @click="toggleBucket(bucket)"
              @keydown.enter.prevent="toggleBucket(bucket)"
              @keydown.space.prevent="toggleBucket(bucket)"
            >
              <title>Your deck {{ bucket.label }}: {{ bucket.actual }} ({{ bucket.actualPercent }}%)</title>
            </rect>
            <text
              :x="groupCenter(index)"
              :y="padding.top + plotHeight + 18"
              text-anchor="middle"
              class="deck-mana-curve-axis-label deck-mana-curve-axis-label--x"
              :class="{ 'is-clickable': bucket.actual > 0, 'is-selected': selectedBucket === bucket.id }"
              :tabindex="bucket.actual > 0 ? 0 : undefined"
              :role="bucket.actual > 0 ? 'button' : undefined"
              @click="toggleBucket(bucket)"
              @keydown.enter.prevent="toggleBucket(bucket)"
              @keydown.space.prevent="toggleBucket(bucket)"
            >
              {{ bucket.label }}
            </text>
          </g>
        </g>
      </svg>

      <div class="deck-mana-curve-legend">
        <span class="deck-mana-curve-legend-item">
          <span class="deck-mana-curve-swatch deck-mana-curve-swatch--ideal" />
          Ideal Commander curve
        </span>
        <span class="deck-mana-curve-legend-item">
          <span class="deck-mana-curve-swatch deck-mana-curve-swatch--actual" />
          Your deck (click a bar)
        </span>
      </div>

      <section v-if="selectedBucket != null" class="deck-mana-curve-selection">
        <header class="deck-mana-curve-selection-header">
          <h4 class="deck-mana-curve-selection-title">
            {{ manaBucketLabel(selectedBucket) }}
          </h4>
          <span class="deck-mana-curve-selection-count">
            {{ selectedBucketMeta?.actual || 0 }}
            {{ (selectedBucketMeta?.actual || 0) === 1 ? "card" : "cards" }}
          </span>
        </header>

        <div v-if="selectedCards.length" class="deck-power-card-grid">
          <figure
            v-for="(card, index) in selectedCards"
            :key="`${selectedBucket}-${card.setCode}-${card.collectorNumber}-${card.finish}-${index}`"
            class="deck-power-card"
          >
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
            <div v-else class="deck-power-card-image-wrap">
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.cardName"
                class="deck-power-card-image"
                loading="lazy"
              >
              <div v-else class="deck-power-card-placeholder">{{ card.cardName }}</div>
            </div>

            <figcaption class="deck-power-card-caption">
              <RouterLink
                v-if="powerCardRoute(card, deckId)"
                :to="powerCardRoute(card, deckId)"
                class="deck-power-card-name"
              >
                {{ cardDisplayName(card) }}
              </RouterLink>
              <span v-else class="deck-power-card-name is-plain">{{ cardDisplayName(card) }}</span>
              <span class="deck-power-card-meta">CMC {{ card.cmc }}</span>
              <span v-if="card.qty > 1" class="deck-power-card-meta">×{{ card.qty }}</span>
            </figcaption>
          </figure>
        </div>

        <p v-else class="deck-mana-curve-selection-empty">
          No cards at this mana value.
        </p>
      </section>
    </template>
  </div>
</template>
