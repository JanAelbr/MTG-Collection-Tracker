<script setup>
import CollectionSetLink from "./CollectionSetLink.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import DeckCardQtyControl from "./DeckCardQtyControl.vue";
import DeckOwnedToggle from "./DeckOwnedToggle.vue";
import DeckTypeIcon from "./DeckTypeIcon.vue";
import ManaCost from "./ManaCost.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import { cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import { cardTypeGroup, deckTypeLabel } from "../utils/deckCards";

const props = defineProps({
  card: { type: Object, default: null },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

defineEmits(["deck-removed", "deck-changed"]);

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
</script>

<template>
  <aside class="deck-stacks-detail-pane" aria-label="Selected card details">
    <p v-if="!card" class="deck-stacks-detail-empty storage-empty">
      Select a card to preview its details.
    </p>

    <div v-else class="deck-stacks-detail-panel">
      <div class="deck-stacks-detail-image-wrap">
        <CardFinishBadge :card="card" variant="overlay" compact />
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
          <ManaCost :mana-cost="card.manaCost || ''" :size="16" />
          <RouterLink
            v-if="cardRoute(card)"
            :to="cardRoute(card)"
            class="deck-stacks-expanded-name"
          >
            {{ card.cardName }}
          </RouterLink>
          <span v-else class="deck-stacks-expanded-name is-plain">
            {{ card.cardName }}
          </span>
          <CardFinishBadge :card="card" compact />
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
          <div class="deck-stacks-detail-row deck-stacks-detail-owned-row">
            <dt>Owned</dt>
            <dd>
              <DeckOwnedToggle
                v-if="defaultDeckId"
                :card="card"
                :deck-id="defaultDeckId"
                @changed="$emit('deck-changed', $event)"
              />
              <span v-else>—</span>
            </dd>
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
