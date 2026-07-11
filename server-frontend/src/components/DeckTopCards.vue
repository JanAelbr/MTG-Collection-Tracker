<script setup>
import { computed } from "vue";
import ManaSymbols from "./ManaSymbols.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import { getTopValueCards } from "../utils/deckBrowse";
import { cardDisplayName, cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";

const TOP_CARD_LIMIT = 10;

const props = defineProps({
  cards: { type: Array, default: () => [] },
  deckId: { type: String, default: "" },
});

const topCards = computed(() => getTopValueCards(props.cards, TOP_CARD_LIMIT));

function cardRoute(card) {
  if (!card?.setCode || !card?.collectorNumber) {
    return null;
  }
  const query = cardRouteQuery(cardFinish(card));
  if (props.deckId) {
    query.deck = props.deckId;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query,
  };
}
</script>

<template>
  <div class="deck-top-cards-view">
    <p v-if="!topCards.length" class="storage-empty deck-top-cards-empty">
      No priced cards match the current filters.
    </p>

    <div v-else class="deck-top-cards-grid">
      <figure
        v-for="(card, index) in topCards"
        :key="`${card.setCode}-${card.collectorNumber}-${cardFinish(card)}-${index}`"
        class="deck-top-card"
      >
        <RouterLink v-if="cardRoute(card)" :to="cardRoute(card)" class="deck-top-card-image-link">
          <img :src="card.imageUri" :alt="card.cardName" loading="lazy">
        </RouterLink>
        <img v-else :src="card.imageUri" :alt="card.cardName" loading="lazy">

        <figcaption class="deck-top-card-caption">
          <span class="top-card-rank">#{{ index + 1 }}</span>

          <span class="deck-top-card-name-row">
            <ManaSymbols class="deck-top-card-mana" :colors="card.colors" :size="12" />
            <RouterLink
              v-if="cardRoute(card)"
              :to="cardRoute(card)"
              class="deck-top-card-name"
            >
              {{ cardDisplayName(card) }}
            </RouterLink>
            <span v-else class="deck-top-card-name is-plain">{{ cardDisplayName(card) }}</span>
          </span>

          <div v-if="card.qty > 1" class="deck-top-card-meta">
            <span class="deck-top-card-qty">×{{ card.qty }}</span>
          </div>

          <p v-if="card.typeLine" class="deck-top-card-type-line">{{ card.typeLine }}</p>

          <div class="deck-top-card-values">
            <PriceStrategyValue :card="card" class="top-card-value" />
          </div>

          <p v-if="card.setCode" class="deck-top-card-print">
            <CollectionSetLink :set-code="card.setCode" />
            #{{ card.collectorNumber }}
            <span v-if="card.finish != null"> · {{ finishLabel(card.finish ?? card.foil ?? 0) }}</span>
          </p>
        </figcaption>
      </figure>
    </div>
  </div>
</template>
