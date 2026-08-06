<script setup>
import { computed } from "vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import CardSetSymbol from "./CardSetSymbol.vue";
import DeckCardQtyControl from "./DeckCardQtyControl.vue";
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
  /** Deck qty −/+ on the tile. Defaults on when showDeckRemove is on. */
  showDeckQty: { type: Boolean, default: undefined },
  showDeckSwap: { type: Boolean, default: true },
  deckName: { type: String, default: "" },
});

const emit = defineEmits(["deck-removed", "deck-changed", "deck-swap"]);

const ownershipTick = computed(() => ownershipRevision.value);
const showQtyStepper = computed(() =>
  props.showDeckQty !== undefined ? Boolean(props.showDeckQty) : Boolean(props.showDeckRemove),
);
const showManageRow = computed(() =>
  Boolean(props.defaultDeckId)
  && (showQtyStepper.value || props.showDeckSwap || props.showDeckRemove),
);

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
      <CardInteractiveImage
        v-if="card.imageUri"
        :src="card.imageUri"
        :alt="card.cardName"
        :card="card"
        img-class="deck-card-grid-image"
        :show-details="false"
        :show-copy-controls="false"
        :deck-id="defaultDeckId"
        :show-deck-swap="Boolean(defaultDeckId && showDeckSwap)"
        :show-deck-remove="Boolean(defaultDeckId && showDeckRemove)"
        @deck-changed="emit('deck-changed', $event)"
        @deck-swap="emit('deck-swap', $event)"
        @deck-removed="emit('deck-removed', $event)"
        @ownership-changed="emit('deck-changed', $event)"
      />
      <div v-else class="deck-card-grid-placeholder">{{ card.cardName }}</div>
    </div>

    <div
      v-if="showManageRow"
      class="deck-card-grid-manage"
    >
      <DeckCardQtyControl
        :card="card"
        :deck-id="defaultDeckId"
        :deck-name="deckName"
        compact
        :show-swap="showDeckSwap"
        :show-remove="showDeckRemove"
        :hide-stepper="!showQtyStepper"
        @changed="emit('deck-changed', $event)"
        @removed="emit('deck-removed', $event)"
        @swap="emit('deck-swap', $event)"
      />
    </div>

    <figcaption class="deck-card-grid-caption">
      <span class="deck-card-grid-name-row">
        <CardSetSymbol
          v-if="card.setCode"
          :set-code="card.setCode"
          :family-root="card.familyRoot || ''"
          :rarity="card.rarity || ''"
        />
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
        <PriceStrategyValue :card="card" />
      </span>
    </figcaption>
  </figure>
</template>
