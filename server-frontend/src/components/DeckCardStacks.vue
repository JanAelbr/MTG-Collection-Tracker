<script setup>
import { computed, ref, watch } from "vue";
import DeckAddCardModal from "./DeckAddCardModal.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import DeckStackCardDetail from "./DeckStackCardDetail.vue";
import DeckTypeIcon from "./DeckTypeIcon.vue";
import {
  effectiveDeckOwnedQty,
  isDeckCardFullyOwned,
  ownershipRevision,
} from "../composables/cardContextMenu";
import { cardFinish } from "../utils/finishes";
import { deckTypeIconType, formatDeckGroupHeading } from "../utils/deckCards";

const props = defineProps({
  groups: { type: Array, default: () => [] },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

const emit = defineEmits(["deck-added", "deck-removed", "deck-changed"]);

const selectedCard = ref(null);

const addModal = ref({
  open: false,
  section: "main",
  cardType: "",
  typeLabel: "",
});

const ownershipTick = computed(() => ownershipRevision.value);

const stackColumns = computed(() =>
  (props.groups || []).filter(
    (group) => group.kind === "type" || (group.kind === "section" && group.cards?.length),
  ),
);

watch(
  () => props.groups,
  () => {
    if (!selectedCard.value) {
      return;
    }
    const stillPresent = stackColumns.value.some((group) =>
      group.cards?.some((card) => cardKey(card) === cardKey(selectedCard.value)),
    );
    if (!stillPresent) {
      selectedCard.value = null;
    }
  },
);

function cardKey(card) {
  return `${card.section}-${card.setCode}-${card.collectorNumber}-${cardFinish(card)}-${card.cardName}`;
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

function isSelected(card) {
  return Boolean(selectedCard.value && cardKey(card) === cardKey(selectedCard.value));
}

function selectCard(card) {
  if (isSelected(card)) {
    selectedCard.value = null;
    return;
  }
  selectedCard.value = card;
}

function isCommanderColumn(group) {
  return group.kind === "section" && group.section === "commander";
}

function openAddModal(group) {
  addModal.value = {
    open: true,
    section: group.section || "main",
    cardType: group.type || "",
    typeLabel: group.label || "",
  };
}

function closeAddModal() {
  addModal.value = { ...addModal.value, open: false };
}
</script>

<template>
  <div class="deck-stacks-layout">
    <div class="deck-stacks">
      <div v-if="!stackColumns.length" class="storage-empty deck-stacks-empty">
        No cards to display.
      </div>

      <div v-else class="deck-stacks-scroll">
        <section
          v-for="group in stackColumns"
          :key="group.key"
          class="deck-stacks-column"
          :class="{ 'is-commander': isCommanderColumn(group) }"
        >
          <header class="deck-stacks-column-header deck-type-heading">
            <DeckTypeIcon :type="deckTypeIconType(group)" />
            <span>{{ formatDeckGroupHeading(group) }}</span>
          </header>

          <div class="deck-stacks-column-body">
            <div
              class="deck-stacks-pile"
              :class="{ 'is-commander': isCommanderColumn(group) }"
              :style="{ '--card-count': group.cards.length }"
            >
              <article
                v-for="(card, index) in group.cards"
                :key="`${group.key}-${cardKey(card)}`"
                class="deck-stacks-card"
                :class="[ownershipClass(card), { 'is-selected': isSelected(card) }]"
                :style="{ '--stack-index': index }"
                :aria-label="card.cardName"
                :aria-pressed="isSelected(card)"
                role="button"
                tabindex="0"
                @click="selectCard(card)"
                @keydown.enter.prevent="selectCard(card)"
                @keydown.space.prevent="selectCard(card)"
              >
                <div class="deck-stacks-card-face">
                  <CardFinishBadge :card="card" variant="overlay" compact />
                  <img
                    v-if="card.imageUri"
                    :src="card.imageUri"
                    :alt="card.cardName"
                    class="deck-stacks-card-image"
                    decoding="async"
                  >
                  <div v-else class="deck-stacks-card-placeholder" />

                  <span v-if="card.qty > 1" class="deck-stacks-qty">{{ card.qty }}</span>
                </div>
              </article>
              <div
                v-if="!isCommanderColumn(group)"
                class="deck-stacks-pile-spacer"
                aria-hidden="true"
              />
            </div>

            <button
              v-if="group.kind === 'type' && defaultDeckId"
              type="button"
              class="deck-stacks-add-slot"
              :title="`Add ${group.label.toLowerCase()} to deck`"
              @click="openAddModal(group)"
            >
              +
            </button>
          </div>
        </section>
      </div>

      <DeckAddCardModal
        v-if="defaultDeckId"
        :open="addModal.open"
        :deck-id="defaultDeckId"
        :deck-name="deckName"
        :section="addModal.section"
        :card-type="addModal.cardType"
        :type-label="addModal.typeLabel"
        @close="closeAddModal"
        @added="$emit('deck-added', $event)"
      />
    </div>

    <DeckStackCardDetail
      :card="selectedCard"
      :default-deck-id="defaultDeckId"
      :show-deck-remove="showDeckRemove"
      :deck-name="deckName"
      @deck-changed="$emit('deck-changed', $event)"
      @deck-removed="$emit('deck-removed', $event)"
    />
  </div>
</template>
