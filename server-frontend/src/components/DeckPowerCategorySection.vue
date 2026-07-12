<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";
import DeckManaCurveChart from "./DeckManaCurveChart.vue";
import {
  componentScoreClass,
  formatComponentCount,
  powerCardRoute,
} from "../utils/deckPower";
import { buildManaCurveChartData } from "../utils/manaCurve";
import { cardDisplayName } from "../utils/finishes";

const props = defineProps({
  component: { type: Object, required: true },
  score: { type: Number, default: 0 },
  counts: { type: Object, default: () => ({}) },
  cards: { type: Array, default: () => [] },
  deckId: { type: [String, Number], default: "" },
});

const isCurve = computed(() => props.component.id === "curve");
const curveChart = computed(() => (
  isCurve.value ? buildManaCurveChartData(props.cards) : null
));
const hasCards = computed(() => {
  if (isCurve.value) {
    return curveChart.value?.hasData || props.cards.length > 0;
  }
  return props.cards.length > 0;
});
const countLabel = computed(() => {
  if (isCurve.value) {
    const total = curveChart.value?.total || 0;
    if (!total) {
      return "No CMC data";
    }
    return total === 1 ? "1 spell" : `${total} spells`;
  }
  return formatComponentCount(props.component.id, props.counts);
});
</script>

<template>
  <details class="deck-power-category" :open="hasCards">
    <summary class="deck-power-category-summary">
      <div class="deck-power-category-heading">
        <span class="deck-power-category-title">{{ component.label }}</span>
        <span v-if="component.showCount !== false" class="deck-power-count">{{ countLabel }}</span>
      </div>
      <div class="deck-power-bar deck-power-bar--compact">
        <span
          class="deck-power-bar-fill"
          :class="componentScoreClass(score)"
          :style="{ width: `${Math.max(0, Math.min(100, score || 0))}%` }"
        />
      </div>
    </summary>

    <DeckManaCurveChart
      v-if="isCurve"
      :cards="cards"
      :deck-id="deckId"
    />

    <div v-else-if="hasCards" class="deck-power-card-grid">
      <figure
        v-for="(card, index) in cards"
        :key="`${component.id}-${card.setCode}-${card.collectorNumber}-${card.finish}-${index}`"
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
          <span v-if="component.id === 'curve' && card.cmc != null" class="deck-power-card-meta">
            CMC {{ card.cmc }}
          </span>
          <span v-else-if="card.qty > 1" class="deck-power-card-meta">×{{ card.qty }}</span>
        </figcaption>
      </figure>
    </div>

    <p v-else-if="!isCurve" class="deck-power-category-empty">
      No tagged cards in this category yet.
    </p>
  </details>
</template>
