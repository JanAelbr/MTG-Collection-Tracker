<script setup>
import DeckCardTile from "./DeckCardTile.vue";

defineProps({
  cards: { type: Array, default: () => [] },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

defineEmits(["deck-removed", "deck-changed"]);
</script>

<template>
  <aside v-if="cards.length" class="deck-cards-commander-pane" aria-label="Commander">
    <h3 class="deck-cards-commander-title">
      {{ cards.length > 1 ? "Commanders" : "Commander" }}
    </h3>
    <div class="deck-cards-commander-items">
      <DeckCardTile
        v-for="card in cards"
        :key="`${card.setCode}-${card.collectorNumber}-${card.cardName}`"
        :card="card"
        compact
        :default-deck-id="defaultDeckId"
        :show-deck-remove="showDeckRemove"
        :deck-name="deckName"
        @deck-changed="$emit('deck-changed', $event)"
      />
    </div>
  </aside>
</template>
