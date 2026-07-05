<script setup>
import { computed } from "vue";
import { getCommanderCards, getTopValueCards, HERO_TOP_CARD_COUNT } from "../utils/deckBrowse";
import { formatDeckOwned, formatDeckValueRange, formatEuro } from "../utils/format";

const props = defineProps({
  deck: { type: Object, default: null },
  stats: { type: Object, default: null },
});

const commanders = computed(() => getCommanderCards(props.stats?.cards || []));
const topCards = computed(() => getTopValueCards(props.stats?.cards || [], HERO_TOP_CARD_COUNT));
const commanderTitle = computed(() => (commanders.value.length > 1 ? "Commanders" : "Commander"));

const deckSize = computed(() => props.stats?.deckSize || 0);
const ownedQty = computed(() => props.stats?.ownedQty || 0);
const missingQty = computed(() => props.stats?.missingQty || 0);

const completionPercent = computed(() => {
  if (props.stats?.ownedCoverage != null) {
    return Math.min(100, Math.max(0, props.stats.ownedCoverage));
  }
  if (!deckSize.value) {
    return 0;
  }
  return Math.min(100, (ownedQty.value / deckSize.value) * 100);
});

const completionLabel = computed(() => {
  const ownedText = formatDeckOwned(ownedQty.value, deckSize.value) || String(ownedQty.value);
  if (missingQty.value > 0) {
    return `${ownedText} owned · ${missingQty.value} missing`;
  }
  return `${ownedText} owned · complete`;
});
</script>

<template>
  <section v-if="deck && stats" class="deck-hero">
    <div class="deck-hero-header">
      <p class="deck-hero-deck-value">
        {{ formatDeckValueRange(stats.ownedCurrent, stats.current) }}
      </p>

      <div class="deck-hero-completion">
        <div
          class="deck-hero-completion-bar"
          role="progressbar"
          :aria-valuenow="Math.round(completionPercent)"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`${Math.round(completionPercent)}% owned`"
        >
          <span
            class="deck-hero-completion-fill"
            :class="{ 'is-complete': completionPercent >= 100 }"
            :style="{ width: `${completionPercent}%` }"
          />
        </div>
        <p class="deck-hero-completion-meta">
          <strong>{{ Math.round(completionPercent) }}%</strong>
          <span>{{ completionLabel }}</span>
        </p>
      </div>
    </div>

    <div class="deck-hero-panels">
      <div class="deck-hero-commanders">
        <h3 class="deck-hero-panel-title">{{ commanderTitle }}</h3>
        <div v-if="commanders.length" class="deck-hero-images">
          <figure v-for="card in commanders" :key="`${card.cardName}-commander`" class="top-card-image deck-hero-image">
            <img :src="card.imageUri" :alt="card.cardName" loading="lazy">
            <figcaption>
              <span class="top-card-name">{{ card.cardName }}</span>
              <span class="top-card-value">{{ formatEuro(card.currentValue) }}</span>
            </figcaption>
          </figure>
        </div>
        <p v-else class="deck-hero-empty">No commander images available.</p>
      </div>

      <div class="deck-hero-top">
        <h3 class="deck-hero-panel-title">Top cards</h3>
        <div v-if="topCards.length" class="deck-hero-images top-card-images">
          <figure
            v-for="(card, index) in topCards"
            :key="`${card.cardName}-top-${index}`"
            class="top-card-image deck-hero-image"
          >
            <img :src="card.imageUri" :alt="card.cardName" loading="lazy">
            <figcaption>
              <span class="top-card-rank">#{{ index + 1 }}</span>
              <span class="top-card-name">{{ card.cardName }}</span>
              <span class="top-card-value">{{ formatEuro(card.currentValue) }}</span>
            </figcaption>
          </figure>
        </div>
        <p v-else class="deck-hero-empty">No priced cards available.</p>
      </div>
    </div>
  </section>
</template>
