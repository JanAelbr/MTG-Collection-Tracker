<script setup>
import { computed, ref, watch } from "vue";
import DeckSwapCardModal from "./DeckSwapCardModal.vue";
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
  colorIdentity: { type: Array, default: null },
  isTypeExpanded: { type: Function, default: () => true },
});

const emit = defineEmits(["deck-added", "deck-removed", "deck-changed", "toggle-type"]);

const selectedCard = ref(null);
const commanderIndex = ref(0);

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

const commanderColumn = computed(
  () => stackColumns.value.find((group) => isCommanderColumn(group)) || null,
);

const commanderCards = computed(() => commanderColumn.value?.cards || []);

const activeCommander = computed(
  () => commanderCards.value[commanderIndex.value] || commanderCards.value[0] || null,
);

watch(
  () => props.groups,
  () => {
    if (!selectedCard.value) {
      return;
    }
    for (const group of stackColumns.value) {
      const match = group.cards?.find((card) => cardKey(card) === cardKey(selectedCard.value));
      if (match) {
        selectedCard.value = match;
        return;
      }
    }
    selectedCard.value = null;
  },
);

watch(commanderCards, (cards) => {
  if (commanderIndex.value >= cards.length) {
    commanderIndex.value = Math.max(0, cards.length - 1);
  }
});

watch(activeCommander, (card) => {
  if (!card || !selectedCard.value || selectedCard.value.section !== "commander") {
    return;
  }
  selectedCard.value = card;
});

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

function typeExpanded(group) {
  if (group.kind !== "type") {
    return true;
  }
  return props.isTypeExpanded(group.key);
}

function visibleCards(group) {
  if (!isCommanderColumn(group)) {
    return group.cards || [];
  }
  return activeCommander.value ? [activeCommander.value] : [];
}

function showPrevCommander() {
  const total = commanderCards.value.length;
  if (total < 2) {
    return;
  }
  commanderIndex.value = (commanderIndex.value - 1 + total) % total;
}

function showNextCommander() {
  const total = commanderCards.value.length;
  if (total < 2) {
    return;
  }
  commanderIndex.value = (commanderIndex.value + 1) % total;
}

const selectedTypeCollapsed = computed(() => {
  if (!selectedCard.value) {
    return false;
  }
  for (const group of stackColumns.value) {
    if (!group.cards?.some((card) => cardKey(card) === cardKey(selectedCard.value))) {
      continue;
    }
    return group.kind === "type" && !typeExpanded(group);
  }
  return false;
});

watch(selectedTypeCollapsed, (collapsed) => {
  if (collapsed) {
    selectedCard.value = null;
  }
});

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
          :class="{
            'is-commander': isCommanderColumn(group),
            'is-collapsed': group.kind === 'type' && !typeExpanded(group),
          }"
        >
          <button
            v-if="group.kind === 'type'"
            type="button"
            class="deck-stacks-column-header deck-type-heading deck-type-collapse-button"
            :class="{ 'is-collapsed': !typeExpanded(group) }"
            :aria-expanded="typeExpanded(group)"
            @click="emit('toggle-type', group.key)"
          >
            <span class="deck-type-collapse-chevron" aria-hidden="true">▾</span>
            <DeckTypeIcon :type="deckTypeIconType(group)" />
            <span>{{ formatDeckGroupHeading(group) }}</span>
          </button>
          <header
            v-else
            class="deck-stacks-column-header deck-type-heading"
            :class="{ 'deck-stacks-commander-header': isCommanderColumn(group) }"
          >
            <DeckTypeIcon :type="deckTypeIconType(group)" />
            <span>{{ formatDeckGroupHeading(group) }}</span>
            <span
              v-if="isCommanderColumn(group) && commanderCards.length > 1"
              class="deck-stacks-commander-meta"
            >
              {{ commanderIndex + 1 }}/{{ commanderCards.length }}
            </span>
            <div
              v-if="isCommanderColumn(group) && commanderCards.length > 1"
              class="deck-stacks-commander-nav-row"
            >
              <button
                type="button"
                class="deck-cards-commander-nav"
                aria-label="Previous commander"
                @click="showPrevCommander"
              >
                ‹
              </button>
              <button
                type="button"
                class="deck-cards-commander-nav"
                aria-label="Next commander"
                @click="showNextCommander"
              >
                ›
              </button>
            </div>
          </header>

          <div v-show="typeExpanded(group)" class="deck-stacks-column-body">
            <div
              class="deck-stacks-pile"
              :class="{ 'is-commander': isCommanderColumn(group) }"
              :style="{ '--card-count': visibleCards(group).length }"
            >
              <article
                v-for="(card, index) in visibleCards(group)"
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

      <DeckSwapCardModal
        v-if="defaultDeckId"
        :open="addModal.open"
        mode="add"
        :deck-id="defaultDeckId"
        :deck-name="deckName"
        :section="addModal.section"
        :card-type="addModal.cardType"
        :type-label="addModal.typeLabel"
        :color-identity="colorIdentity"
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
