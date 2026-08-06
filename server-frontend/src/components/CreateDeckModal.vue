<script setup>
import { computed, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import CommanderGalleryPicker from "./CommanderGalleryPicker.vue";
import { cardFinish } from "../utils/finishes";

const MAX_COMMANDERS = 4;

const DECK_FORMATS = [
  { id: "commander", label: "Commander" },
];

const props = defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "created"]);

const deckFormat = ref("commander");
const deckName = ref("");
const nameTouched = ref(false);
const selectedCommanders = ref([]);
const createError = ref("");
const creating = ref(false);
const modalBodyRef = ref(null);

const canCreate = computed(() => {
  if (creating.value) {
    return false;
  }
  if (deckFormat.value === "commander" && selectedCommanders.value.length < 1) {
    return false;
  }
  return Boolean(deckName.value.trim());
});

const selectedPrintKeys = computed(() => {
  const keys = new Set();
  for (const card of selectedCommanders.value) {
    keys.add(commanderKey(card));
  }
  return keys;
});

function commanderKey(card) {
  return `${card.setCode}|${card.collectorNumber}|${cardFinish(card)}`;
}

function resetState() {
  deckFormat.value = "commander";
  deckName.value = "";
  nameTouched.value = false;
  selectedCommanders.value = [];
  createError.value = "";
  creating.value = false;
}

function closeModal() {
  resetState();
  emit("close");
}

function onNameInput() {
  nameTouched.value = true;
}

function syncDefaultName() {
  if (nameTouched.value || !selectedCommanders.value.length) {
    return;
  }
  const first = selectedCommanders.value[0];
  deckName.value = first.cardName || first.name || "";
}

function toggleCommander(card) {
  if (!card?.setCode || !card?.collectorNumber) {
    return;
  }
  createError.value = "";
  const key = commanderKey(card);
  if (selectedCommanders.value.some((item) => commanderKey(item) === key)) {
    selectedCommanders.value = selectedCommanders.value.filter(
      (item) => commanderKey(item) !== key,
    );
    syncDefaultName();
    return;
  }
  if (selectedCommanders.value.length >= MAX_COMMANDERS) {
    createError.value = `You can select up to ${MAX_COMMANDERS} commanders.`;
    return;
  }
  selectedCommanders.value = [
    ...selectedCommanders.value,
    {
      ...card,
      cardName: card.cardName || card.name || "Unknown",
    },
  ];
  syncDefaultName();
}

function removeCommander(card) {
  selectedCommanders.value = selectedCommanders.value.filter(
    (item) => commanderKey(item) !== commanderKey(card),
  );
  syncDefaultName();
}

async function createDeck() {
  if (!canCreate.value) {
    return;
  }
  creating.value = true;
  createError.value = "";
  try {
    const result = await api.createDeck({
      format: deckFormat.value,
      name: deckName.value.trim(),
      commanders: selectedCommanders.value.map((card) => ({
        setCode: card.setCode,
        collectorNumber: card.collectorNumber,
        finish: cardFinish(card),
      })),
    });
    clearClientCache();
    emit("created", result.deck);
    closeModal();
  } catch (error) {
    createError.value = error.message || "Could not create deck.";
  } finally {
    creating.value = false;
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      resetState();
    }
  },
);
</script>

<template>
  <div
    v-if="open"
    class="modal-backdrop deck-create-modal-backdrop"
    @click.self="closeModal"
  >
    <form class="modal-card deck-create-modal" @submit.prevent="createDeck">
      <header class="deck-create-modal-head">
        <div>
          <h3>New deck</h3>
          <p class="deck-create-modal-subtitle">
            Pick commander(s) from your collection, then name the deck.
          </p>
        </div>
        <button type="button" class="btn btn-secondary btn-small" @click="closeModal">
          Close
        </button>
      </header>

      <div ref="modalBodyRef" class="deck-create-modal-body">
        <section class="deck-create-section">
          <h4 class="deck-create-section-title">Format</h4>
          <div class="button-group deck-create-format-group">
            <button
              v-for="format in DECK_FORMATS"
              :key="format.id"
              type="button"
              class="filter-button"
              :class="{ active: deckFormat === format.id }"
              @click="deckFormat = format.id"
            >
              {{ format.label }}
            </button>
          </div>
        </section>

        <section v-if="deckFormat === 'commander'" class="deck-create-section deck-create-commander-section">
          <h4 class="deck-create-section-title">Commander</h4>
          <p class="deck-create-section-help">
            Browse owned legendaries. Filter by name or color identity. Click again to deselect.
          </p>

          <div v-if="selectedCommanders.length" class="deck-create-commander-list">
            <figure
              v-for="card in selectedCommanders"
              :key="commanderKey(card)"
              class="deck-create-commander-chip"
            >
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.cardName"
                loading="lazy"
              />
              <figcaption>
                <span class="deck-create-commander-name">{{ card.cardName }}</span>
                <button
                  type="button"
                  class="deck-create-commander-remove"
                  @click="removeCommander(card)"
                >
                  Remove
                </button>
              </figcaption>
            </figure>
          </div>

          <CommanderGalleryPicker
            :selected-keys="selectedPrintKeys"
            :scroll-root="modalBodyRef"
            :card-scale="110"
            search-placeholder="Filter by commander name…"
            @pick-card="toggleCommander"
          />
        </section>

        <section v-if="selectedCommanders.length" class="deck-create-section">
          <h4 class="deck-create-section-title">Deck name</h4>
          <label class="deck-create-name-field">
            <span>Name</span>
            <input
              v-model="deckName"
              type="text"
              maxlength="120"
              required
              @input="onNameInput"
            />
          </label>
        </section>

        <p v-if="createError" class="deck-create-error">{{ createError }}</p>
      </div>

      <div class="modal-actions">
        <button type="button" class="btn btn-secondary" @click="closeModal">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" :disabled="!canCreate">
          {{ creating ? "Creating…" : "Create deck" }}
        </button>
      </div>
    </form>
  </div>
</template>
