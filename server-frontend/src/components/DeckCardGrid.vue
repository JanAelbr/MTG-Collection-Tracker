<script setup>
import { computed } from "vue";
import ManaSymbols from "./ManaSymbols.vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import {
  effectiveDeckOwnedQty,
  isDeckCardFullyOwned,
  ownershipRevision,
} from "../composables/cardContextMenu";
import { formatEuro, formatSection } from "../utils/format";
import { cardDisplayName, cardFinish, cardRouteQuery } from "../utils/finishes";

defineProps({
  groups: { type: Array, default: () => [] },
});

const ownershipTick = computed(() => ownershipRevision.value);

function cardRoute(card) {
  if (!card.setCode || !card.collectorNumber) {
    return null;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function cardKey(card) {
  ownershipTick.value;
  return `${card.section}-${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`;
}

function isFullyOwned(card) {
  ownershipTick.value;
  return isDeckCardFullyOwned(card);
}

function ownedLabel(card) {
  ownershipTick.value;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (ownedQty > 0) {
    return `${ownedQty}/${card.qty} owned`;
  }
  return "Not owned";
}

function sectionHeading(group) {
  if (group.kind === "section" && group.cards?.length) {
    return formatSection(group.section);
  }
  return group.label;
}
</script>

<template>
  <div class="deck-card-grid">
    <template v-for="group in groups" :key="group.key">
      <section
        v-if="group.kind === 'section' && !group.cards?.length"
        class="deck-card-grid-section deck-card-grid-section-title"
      >
        <h3 class="deck-card-grid-heading deck-card-grid-heading-section">{{ group.label }}</h3>
      </section>

      <section
        v-else-if="group.cards?.length"
        class="deck-card-grid-section"
        :class="{ 'deck-card-grid-section-commander': group.section === 'commander' }"
      >
        <h3
          class="deck-card-grid-heading"
          :class="{
            'deck-card-grid-heading-section': group.kind === 'section',
            'deck-card-grid-heading-type': group.kind === 'type',
          }"
        >
          {{ sectionHeading(group) }}
        </h3>

        <div class="deck-card-grid-items">
          <figure
            v-for="card in group.cards"
            :key="cardKey(card)"
            class="deck-card-grid-item"
            :class="{ 'is-unowned': !isFullyOwned(card) }"
          >
            <span v-if="card.qty > 1" class="deck-card-grid-qty">×{{ card.qty }}</span>

            <div class="deck-card-grid-image-wrap">
              <CardInteractiveImage
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.cardName"
                :card="card"
                :show-details="false"
              />
              <div v-else class="deck-card-grid-placeholder">{{ card.cardName }}</div>
            </div>

            <figcaption class="deck-card-grid-caption">
              <span class="deck-card-grid-name-row">
                <ManaSymbols :colors="card.colors" :size="16" />
                <RouterLink
                  v-if="cardRoute(card)"
                  :to="cardRoute(card)"
                  class="deck-card-grid-name deck-card-grid-name-link"
                >
                  {{ cardDisplayName(card) }}
                </RouterLink>
                <span v-else class="deck-card-grid-name">{{ cardDisplayName(card) }}</span>
              </span>
              <span class="deck-card-grid-meta">
                <span v-if="card.currentValue != null">{{ formatEuro(card.currentValue) }}</span>
                <span>{{ ownedLabel(card) }}</span>
              </span>
            </figcaption>
          </figure>
        </div>
      </section>
    </template>
  </div>
</template>
