<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  deckCardImageUri,
  getGalleryCommanders,
  sortDecksForGallery,
} from "../utils/deckBrowse";
import { cardDisplayName } from "../utils/finishes";
import { formatDeckOwned, formatDeckValueRange, formatEuro } from "../utils/format";

const props = defineProps({
  decks: { type: Array, default: () => [] },
  pages: { type: Object, default: () => ({}) },
  activeDeckId: { type: String, default: "" },
  sortBy: { type: String, default: "year" },
});

const emit = defineEmits(["select"]);

const galleryRef = ref(null);

const sortedDecks = computed(() =>
  sortDecksForGallery(props.decks, props.pages, props.sortBy),
);

function deckStats(deck) {
  return props.pages[String(deck.id)] || {};
}

function deckCards(deck) {
  return deckStats(deck).cards || [];
}

function deckValueLabel(deck) {
  const stats = deckStats(deck);
  if (stats.ownedCurrent != null && stats.current != null) {
    return formatDeckValueRange(stats.ownedCurrent, stats.current);
  }
  return formatEuro(stats.current);
}

function deckOwnedLabel(deck) {
  const stats = deckStats(deck);
  return formatDeckOwned(stats.ownedQty, stats.deckSize);
}

function commandersFor(deck) {
  return getGalleryCommanders(deckCards(deck));
}

function selectDeck(deckId) {
  emit("select", String(deckId));
}

function onCardKeydown(event, deckId) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    selectDeck(deckId);
  }
}

function scrollActiveIntoView(behavior = "smooth") {
  nextTick(() => {
    const root = galleryRef.value;
    if (!root || !props.activeDeckId) {
      return;
    }
    const active = root.querySelector(".deck-gallery-card.active");
    active?.scrollIntoView({ block: "nearest", inline: "center", behavior });
  });
}

watch(() => props.activeDeckId, () => scrollActiveIntoView());
watch(
  () => [props.sortBy, sortedDecks.value.length],
  () => scrollActiveIntoView("auto"),
);

onMounted(() => scrollActiveIntoView("auto"));
</script>

<template>
  <div ref="galleryRef" class="deck-gallery" aria-label="All decks">
    <div
      v-for="deck in sortedDecks"
      :key="deck.id"
      class="deck-gallery-card"
      :class="{ active: String(deck.id) === String(activeDeckId) }"
      role="button"
      tabindex="0"
      @click="selectDeck(deck.id)"
      @keydown="onCardKeydown($event, deck.id)"
    >
      <div class="deck-gallery-visual">
        <div class="deck-gallery-commanders">
          <figure
            v-for="(card, index) in commandersFor(deck)"
            :key="`${deck.id}-commander-${index}`"
            class="deck-gallery-commander"
          >
            <img
              :src="deckCardImageUri(card)"
              :alt="cardDisplayName(card)"
              :title="cardDisplayName(card)"
              loading="lazy"
            />
          </figure>
          <div v-if="!commandersFor(deck).length" class="deck-gallery-placeholder">
            No commander image
          </div>
        </div>
      </div>

      <div class="deck-gallery-meta">
        <h3 class="deck-gallery-name">{{ deck.label }}</h3>
        <div class="deck-gallery-stats">
          <span v-if="deck.releaseYear" class="deck-gallery-year">{{ deck.releaseYear }}</span>
          <span class="deck-gallery-value">{{ deckValueLabel(deck) }}</span>
          <span v-if="deckOwnedLabel(deck)" class="deck-gallery-owned">{{ deckOwnedLabel(deck) }} owned</span>
        </div>
      </div>
    </div>
  </div>
</template>
