<script setup>
import { computed } from "vue";
import { getCommanderCards, getTopValueCards, HERO_TOP_CARD_COUNT } from "../utils/deckBrowse";
import { formatDeckValueRange, formatEuro } from "../utils/format";

const props = defineProps({
  deck: { type: Object, default: null },
  stats: { type: Object, default: null },
});

const commanders = computed(() => getCommanderCards(props.stats?.cards || []));
const topCards = computed(() => getTopValueCards(props.stats?.cards || [], HERO_TOP_CARD_COUNT));
const commanderTitle = computed(() => (commanders.value.length > 1 ? "Commanders" : "Commander"));
</script>

<template>
  <section v-if="deck && stats" class="deck-hero">
    <div class="deck-hero-header">
      <h2 class="deck-hero-deck-name">{{ deck.label }}</h2>
      <p class="deck-hero-deck-value">
        {{ formatDeckValueRange(stats.ownedCurrent, stats.current) }}
      </p>
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
