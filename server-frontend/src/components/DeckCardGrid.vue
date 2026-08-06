<script setup>
import { ref } from "vue";
import DeckSwapCardModal from "./DeckSwapCardModal.vue";
import DeckCardTile from "./DeckCardTile.vue";
import DeckTypeIcon from "./DeckTypeIcon.vue";
import { deckTypeIconType, formatDeckGroupHeading } from "../utils/deckCards";

const props = defineProps({
  groups: { type: Array, default: () => [] },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
  colorIdentity: { type: Array, default: null },
  isTypeExpanded: { type: Function, default: () => true },
});

const emit = defineEmits(["deck-added", "deck-removed", "deck-changed", "deck-swap", "toggle-type"]);

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

function typeExpanded(group) {
  if (group.kind !== "type") {
    return true;
  }
  return props.isTypeExpanded(group.key);
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
        :class="{ 'is-collapsed': group.kind === 'type' && !typeExpanded(group) }"
      >
        <button
          v-if="group.kind === 'type'"
          type="button"
          class="deck-card-grid-heading deck-type-heading deck-type-collapse-button"
          :class="{
            'deck-card-grid-heading-type': true,
            'is-collapsed': !typeExpanded(group),
          }"
          :aria-expanded="typeExpanded(group)"
          @click="emit('toggle-type', group.key)"
        >
          <span class="deck-type-collapse-chevron" aria-hidden="true">▾</span>
          <DeckTypeIcon :type="deckTypeIconType(group)" />
          <span>{{ sectionHeading(group) }}</span>
        </button>
        <h3
          v-else
          class="deck-card-grid-heading deck-type-heading"
          :class="{
            'deck-card-grid-heading-section': group.kind === 'section',
          }"
        >
          <DeckTypeIcon :type="deckTypeIconType(group)" />
          <span>{{ sectionHeading(group) }}</span>
        </h3>

        <div v-show="typeExpanded(group)" class="deck-card-grid-items">
          <DeckCardTile
            v-for="card in group.cards"
            :key="`${group.key}-${card.section}-${card.setCode}-${card.collectorNumber}`"
            :card="card"
            :default-deck-id="props.defaultDeckId"
            :show-deck-remove="props.showDeckRemove"
            :deck-name="props.deckName"
            @deck-removed="$emit('deck-removed', $event)"
            @deck-changed="$emit('deck-changed', $event)"
            @deck-swap="$emit('deck-swap', $event)"
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

    <DeckSwapCardModal
      v-if="props.defaultDeckId"
      :open="addModal.open"
      mode="add"
      :deck-id="props.defaultDeckId"
      :deck-name="props.deckName"
      :section="addModal.section"
      :card-type="addModal.cardType"
      :type-label="addModal.typeLabel"
      :color-identity="props.colorIdentity"
      @close="closeAddModal"
      @added="onModalAdded"
    />
  </div>
</template>
