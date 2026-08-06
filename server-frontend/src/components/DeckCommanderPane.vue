<script setup>
import { computed, ref, watch } from "vue";
import DeckCardTile from "./DeckCardTile.vue";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

defineEmits(["deck-removed", "deck-changed", "deck-swap"]);

const commanderIndex = ref(0);

const hasCarousel = computed(() => props.cards.length > 1);
const activeCommander = computed(
  () => props.cards[commanderIndex.value] || props.cards[0] || null,
);
const canRemoveCommander = computed(() => props.cards.length > 1);

watch(
  () => props.cards,
  (cards) => {
    if (commanderIndex.value >= cards.length) {
      commanderIndex.value = Math.max(0, cards.length - 1);
    }
  },
);

function showPrevCommander() {
  const total = props.cards.length;
  if (total < 2) {
    return;
  }
  commanderIndex.value = (commanderIndex.value - 1 + total) % total;
}

function showNextCommander() {
  const total = props.cards.length;
  if (total < 2) {
    return;
  }
  commanderIndex.value = (commanderIndex.value + 1) % total;
}

function cardKey(card) {
  return `${card.setCode}-${card.collectorNumber}-${card.cardName}`;
}
</script>

<template>
  <aside v-if="activeCommander" class="deck-cards-commander-pane" aria-label="Commander">
    <header class="deck-cards-commander-head">
      <h3 class="deck-cards-commander-title">
        {{ hasCarousel ? "Commanders" : "Commander" }}
      </h3>
      <span v-if="hasCarousel" class="deck-cards-commander-meta">
        {{ commanderIndex + 1 }}/{{ cards.length }}
      </span>
    </header>

    <div class="deck-cards-commander-stage">
      <button
        v-if="hasCarousel"
        type="button"
        class="deck-cards-commander-nav"
        aria-label="Previous commander"
        @click="showPrevCommander"
      >
        ‹
      </button>

      <div class="deck-cards-commander-items">
        <DeckCardTile
          :key="cardKey(activeCommander)"
          :card="activeCommander"
          compact
          :default-deck-id="defaultDeckId"
          :show-deck-remove="showDeckRemove && canRemoveCommander"
          :show-deck-qty="false"
          :show-deck-swap="true"
          :deck-name="deckName"
          @deck-changed="$emit('deck-changed', $event)"
          @deck-swap="$emit('deck-swap', $event)"
          @deck-removed="$emit('deck-removed', $event)"
        />
      </div>

      <button
        v-if="hasCarousel"
        type="button"
        class="deck-cards-commander-nav"
        aria-label="Next commander"
        @click="showNextCommander"
      >
        ›
      </button>
    </div>
  </aside>
</template>
