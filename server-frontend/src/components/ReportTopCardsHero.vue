<script setup>
import { computed } from "vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import { formatEuro } from "../utils/format";
import { cardDisplayName, cardFinish, cardRouteQuery } from "../utils/finishes";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  limit: { type: Number, default: 5 },
});

const heroCards = computed(() =>
  props.cards.filter((card) => card.imageUri).slice(0, props.limit),
);

function cardRoute(card) {
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function heroValue(card) {
  if (card.currentValue != null) {
    return card.currentValue;
  }
  return card.priceChange != null ? Math.abs(card.priceChange) : null;
}
</script>

<template>
  <div v-if="heroCards.length" class="top-card-images">
    <figure
      v-for="(card, index) in heroCards"
      :key="`${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`"
      class="top-card-image"
    >
      <RouterLink :to="cardRoute(card)">
        <CardInteractiveImage
          :src="card.imageUri"
          :alt="card.name"
          :card="card"
        />
      </RouterLink>
      <figcaption>
        <span class="top-card-rank">#{{ index + 1 }}</span>
        <span class="top-card-name">{{ cardDisplayName(card) }}</span>
        <span class="top-card-value">{{ formatEuro(heroValue(card)) }}</span>
      </figcaption>
    </figure>
  </div>
</template>
