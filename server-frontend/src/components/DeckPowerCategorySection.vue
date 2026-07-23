<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";
import CardFinishBadge from "./CardFinishBadge.vue";
import {
  componentScoreClass,
  formatComponentCount,
  powerCardRoute,
} from "../utils/deckPower";

const props = defineProps({
  component: { type: Object, required: true },
  score: { type: Number, default: 0 },
  counts: { type: Object, default: () => ({}) },
  cards: { type: Array, default: () => [] },
  deckId: { type: [String, Number], default: "" },
});

const hasCards = computed(() => props.cards.length > 0);
const countLabel = computed(() => formatComponentCount(props.component.id, props.counts));
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

    <div v-if="hasCards" class="deck-power-card-grid">
      <figure
        v-for="(card, index) in cards"
        :key="`${component.id}-${card.setCode}-${card.collectorNumber}-${card.finish}-${index}`"
        class="deck-power-card"
      >
        <div class="deck-power-card-image-wrap">
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
          <span class="deck-power-card-name-row">
            <RouterLink
              v-if="powerCardRoute(card, deckId)"
              :to="powerCardRoute(card, deckId)"
              class="deck-power-card-name"
            >
              {{ card.cardName }}
            </RouterLink>
            <span v-else class="deck-power-card-name is-plain">{{ card.cardName }}</span>
            <CardFinishBadge :card="card" compact />
            <span v-if="card.qty > 1" class="deck-power-card-meta">×{{ card.qty }}</span>
          </span>
        </figcaption>
      </figure>
    </div>

    <p v-else class="deck-power-category-empty">
      No tagged cards in this category yet.
    </p>
  </details>
</template>
