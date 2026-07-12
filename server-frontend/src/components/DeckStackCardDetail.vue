<script setup>
import { computed } from "vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import DeckCardQtyControl from "./DeckCardQtyControl.vue";
import DeckTypeIcon from "./DeckTypeIcon.vue";
import ManaSymbols from "./ManaSymbols.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import {
  effectiveDeckOwnedQty,
  isDeckCardFullyOwned,
  ownershipRevision,
} from "../composables/cardContextMenu";
import { cardDisplayName, cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import { cardTypeGroup, deckTypeLabel } from "../utils/deckCards";

const props = defineProps({
  card: { type: Object, default: null },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

defineEmits(["deck-removed", "deck-changed"]);

const ownershipTick = computed(() => ownershipRevision.value);

function cardRoute(card) {
  if (!card?.setCode || !card?.collectorNumber) {
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

function ownershipClass(card) {
  ownershipTick.value;
  const qty = Number(card?.qty) || 0;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (isDeckCardFullyOwned(card)) {
    return "is-owned";
  }
  if (ownedQty > 0 && ownedQty < qty) {
    return "is-partial";
  }
  return "is-missing";
}

function ownedLabel(card) {
  ownershipTick.value;
  const qty = Number(card?.qty) || 0;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (isDeckCardFullyOwned(card)) {
    return qty > 1 ? `${qty} owned` : "Owned";
  }
  if (ownedQty > 0 && ownedQty < qty) {
    return `${ownedQty} / ${qty} owned`;
  }
  return "Missing";
}
</script>

<template>
  <aside class="deck-stacks-detail-pane" aria-label="Selected card details">
    <p v-if="!card" class="deck-stacks-detail-empty storage-empty">
      Select a card to preview its details.
    </p>

    <div v-else class="deck-stacks-detail-panel">
      <div class="deck-stacks-detail-image-wrap">
        <RouterLink
          v-if="card.imageUri && cardRoute(card)"
          :to="cardRoute(card)"
          class="deck-stacks-detail-image-link"
        >
          <img
            :src="card.imageUri"
            :alt="card.cardName"
            class="deck-stacks-detail-image"
          >
        </RouterLink>
        <img
          v-else-if="card.imageUri"
          :src="card.imageUri"
          :alt="card.cardName"
          class="deck-stacks-detail-image"
        >
        <div v-else class="deck-stacks-detail-image-empty">No image</div>
      </div>

      <div class="deck-stacks-detail-meta">
        <div class="deck-stacks-expanded-name-row">
          <ManaSymbols :colors="card.colors" :size="16" />
          <RouterLink
            v-if="cardRoute(card)"
            :to="cardRoute(card)"
            class="deck-stacks-expanded-name"
          >
            {{ cardDisplayName(card) }}
          </RouterLink>
          <span v-else class="deck-stacks-expanded-name is-plain">
            {{ cardDisplayName(card) }}
          </span>
        </div>

        <p v-if="card.typeLine" class="deck-stacks-expanded-type">{{ card.typeLine }}</p>

        <dl class="deck-stacks-expanded-details">
          <div v-if="cardTypeGroup(card)" class="deck-stacks-detail-row">
            <dt>Type</dt>
            <dd class="deck-type-label">
              <DeckTypeIcon :type="cardTypeGroup(card)" />
              <span>{{ deckTypeLabel(cardTypeGroup(card)) }}</span>
            </dd>
          </div>
          <div v-if="card.qty > 1" class="deck-stacks-detail-row">
            <dt>Qty</dt>
            <dd>{{ card.qty }}</dd>
          </div>
          <div v-if="card.setCode" class="deck-stacks-detail-row">
            <dt>Print</dt>
            <dd>
              <CollectionSetLink :set-code="card.setCode" />
              #{{ card.collectorNumber }}
            </dd>
          </div>
          <div v-if="card.finish != null" class="deck-stacks-detail-row">
            <dt>Finish</dt>
            <dd>{{ finishLabel(card.finish ?? card.foil ?? 0) }}</dd>
          </div>
          <div v-if="card.currentValue != null" class="deck-stacks-detail-row">
            <dt>Value</dt>
            <dd><PriceStrategyValue :card="card" /></dd>
          </div>
          <div class="deck-stacks-detail-row">
            <dt>Owned</dt>
            <dd :class="`is-${ownershipClass(card)}`">{{ ownedLabel(card) }}</dd>
          </div>
        </dl>

        <DeckCardQtyControl
          v-if="showDeckRemove && defaultDeckId"
          :card="card"
          :deck-id="defaultDeckId"
          :deck-name="deckName"
          compact
          @changed="$emit('deck-changed', $event)"
          @removed="$emit('deck-removed', $event)"
        />
      </div>
    </div>
  </aside>
</template>
