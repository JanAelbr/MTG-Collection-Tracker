<script setup>
import { ref } from "vue";
import DeckAddCardModal from "./DeckAddCardModal.vue";
import DeckCardTile from "./DeckCardTile.vue";
import DeckTypeIcon from "./DeckTypeIcon.vue";
import { deckTypeIconType, formatDeckGroupHeading } from "../utils/deckCards";

const props = defineProps({
  groups: { type: Array, default: () => [] },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

const emit = defineEmits(["deck-added", "deck-removed", "deck-changed"]);

const addModal = ref({
  open: false,
  section: "main",
  cardType: "",
  typeLabel: "",
});

function sectionHeading(group) {
  if (group.kind === "section" && group.cards?.length) {
    return formatDeckGroupHeading(group);
  }
  if (group.kind === "type" || group.count != null) {
    return formatDeckGroupHeading(group);
  }
  return group.label;
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

function onModalAdded(result) {
  emit("deck-added", result);
}
</script>

<template>
  <div class="deck-card-grid">
    <template v-for="group in groups" :key="group.key">
      <section
        v-if="group.kind === 'section' && !group.cards?.length"
        class="deck-card-grid-section deck-card-grid-section-title"
      >
        <h3 class="deck-card-grid-heading deck-card-grid-heading-section deck-type-heading">
          <DeckTypeIcon :type="deckTypeIconType(group)" />
          <span>{{ formatDeckGroupHeading(group) }}</span>
        </h3>
      </section>

      <section
        v-else-if="group.kind === 'type' || group.cards?.length"
        class="deck-card-grid-section"
      >
        <h3
          class="deck-card-grid-heading deck-type-heading"
          :class="{
            'deck-card-grid-heading-section': group.kind === 'section',
            'deck-card-grid-heading-type': group.kind === 'type',
          }"
        >
          <DeckTypeIcon :type="deckTypeIconType(group)" />
          <span>{{ sectionHeading(group) }}</span>
        </h3>

        <div class="deck-card-grid-items">
          <DeckCardTile
            v-for="card in group.cards"
            :key="`${group.key}-${card.section}-${card.setCode}-${card.collectorNumber}`"
            :card="card"
            :default-deck-id="props.defaultDeckId"
            :show-deck-remove="props.showDeckRemove"
            :deck-name="props.deckName"
            @deck-removed="$emit('deck-removed', $event)"
            @deck-changed="$emit('deck-changed', $event)"
          />
          <button
            v-if="group.kind === 'type' && props.defaultDeckId"
            type="button"
            class="deck-card-grid-add-slot"
            :title="`Add ${group.label.toLowerCase()} to deck`"
            @click="openAddModal(group)"
          >
            +
          </button>
        </div>
      </section>
    </template>

    <DeckAddCardModal
      v-if="props.defaultDeckId"
      :open="addModal.open"
      :deck-id="props.defaultDeckId"
      :deck-name="props.deckName"
      :section="addModal.section"
      :card-type="addModal.cardType"
      :type-label="addModal.typeLabel"
      @close="closeAddModal"
      @added="onModalAdded"
    />
  </div>
</template>
