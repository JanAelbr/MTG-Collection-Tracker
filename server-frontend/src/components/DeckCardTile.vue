<script setup>
import { computed } from "vue";
import ManaCost from "./ManaCost.vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import DeckCardQtyControl from "./DeckCardQtyControl.vue";
import DeckOwnedToggle from "./DeckOwnedToggle.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import {
  effectiveDeckOwnedQty,
  isDeckCardFullyOwned,
  ownershipRevision,
} from "../composables/cardContextMenu";
import { cardFinish, cardRouteQuery } from "../utils/finishes";

const props = defineProps({
  card: { type: Object, required: true },
  compact: { type: Boolean, default: false },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

defineEmits(["deck-removed", "deck-changed"]);

const ownershipTick = computed(() => ownershipRevision.value);

function cardRoute(card) {
  if (!card.setCode || !card.collectorNumber) {
    return null;
  }
  const query = cardRouteQuery(cardFinish(card));
  if (props.defaultDeckId) {
    query.deck = props.defaultDeckId;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query,
  };
}

function ownershipState(card) {
  ownershipTick.value;
  const qty = Number(card?.qty) || 0;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (isDeckCardFullyOwned(card)) {
    return "owned";
  }
  if (ownedQty > 0 && ownedQty < qty) {
    return "partial";
  }
  return "missing";
}
</script>

<template>
  <figure
    class="deck-card-grid-item"
    :class="[`is-${ownershipState(card)}`, { 'deck-card-grid-item-compact': compact }]"
  >
    <span v-if="card.qty > 1 && !showDeckRemove" class="deck-card-grid-qty">×{{ card.qty }}</span>

    <div class="deck-card-grid-image-wrap">
      <RouterLink
        v-if="card.imageUri && cardRoute(card)"
        :to="cardRoute(card)"
        class="deck-card-grid-link"
      >
        <img
          :src="card.imageUri"
          :alt="card.cardName"
          class="card-interactive-image deck-card-grid-image"
          loading="lazy"
        >
      </RouterLink>
      <CardInteractiveImage
        v-else-if="card.imageUri"
        :src="card.imageUri"
        :alt="card.cardName"
        :card="card"
        :show-details="false"
      />
      <div v-else class="deck-card-grid-placeholder">{{ card.cardName }}</div>
    </div>

    <div
      v-if="showDeckRemove && defaultDeckId"
      class="deck-card-grid-manage"
    >
      <DeckCardQtyControl
        :card="card"
        :deck-id="defaultDeckId"
        :deck-name="deckName"
        compact
        @changed="$emit('deck-changed', $event)"
        @removed="$emit('deck-removed', $event)"
      />
      <DeckOwnedToggle
        :card="card"
        :deck-id="defaultDeckId"
        compact
        @changed="$emit('deck-changed', $event)"
      />
    </div>

    <figcaption class="deck-card-grid-caption">
      <span class="deck-card-grid-name-row">
        <ManaCost :mana-cost="card.manaCost || ''" :size="16" />
        <RouterLink
          v-if="cardRoute(card)"
          :to="cardRoute(card)"
          class="deck-card-grid-name deck-card-grid-name-link"
        >
          {{ card.cardName }}
        </RouterLink>
        <span v-else class="deck-card-grid-name">{{ card.cardName }}</span>
        <CardFinishBadge :card="card" compact />
      </span>
      <span class="deck-card-grid-meta">
        <PriceStrategyValue v-if="card.currentValue != null" :card="card" />
      </span>
    </figcaption>
  </figure>
</template>
