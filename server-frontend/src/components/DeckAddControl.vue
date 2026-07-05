<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import { normalizeCardMenuTarget } from "../composables/cardContextMenu";
import { cardFinish } from "../utils/finishes";

const props = defineProps({
  card: { type: Object, required: true },
  defaultDeckId: { type: String, default: "" },
  compact: { type: Boolean, default: false },
});

const emit = defineEmits(["added"]);

const decks = ref([]);
const selectedDeckId = ref("");
const section = ref("main");
const loading = ref(false);
const message = ref("");
const error = ref("");

const target = computed(() => normalizeCardMenuTarget(props.card));
const canAdd = computed(() => Boolean(target.value?.setCode && target.value?.collectorNumber));

const selectedDeck = computed(
  () => decks.value.find((deck) => String(deck.id) === String(selectedDeckId.value)) || null,
);

const quickAddLabel = computed(() => {
  if (!selectedDeck.value) {
    return "Add to deck";
  }
  if (props.compact && props.defaultDeckId && String(props.defaultDeckId) === String(selectedDeckId.value)) {
    return `Add to ${selectedDeck.value.name}`;
  }
  return "Add";
});

async function loadDecks() {
  const payload = await api.listDecks();
  decks.value = payload.decks || [];
  syncSelectedDeck();
}

function syncSelectedDeck() {
  if (
    props.defaultDeckId
    && decks.value.some((deck) => String(deck.id) === String(props.defaultDeckId))
  ) {
    selectedDeckId.value = String(props.defaultDeckId);
    return;
  }
  if (!selectedDeckId.value && decks.value.length) {
    selectedDeckId.value = String(decks.value[0].id);
  }
}

async function addToDeck() {
  if (!canAdd.value || !selectedDeckId.value || loading.value) {
    return;
  }
  loading.value = true;
  error.value = "";
  message.value = "";
  try {
    const result = await api.addCardToDeck(selectedDeckId.value, {
      setCode: target.value.setCode,
      collectorNumber: target.value.collectorNumber,
      finish: cardFinish(props.card),
      section: section.value,
    });
    clearClientCache();
    message.value = result.created
      ? `Added to ${result.deckName}`
      : `Qty ${result.qty} in ${result.deckName}`;
    emit("added", result);
  } catch (err) {
    error.value = err.message || "Could not add card to deck.";
  } finally {
    loading.value = false;
  }
}

watch(() => props.defaultDeckId, syncSelectedDeck);

onMounted(async () => {
  try {
    await loadDecks();
  } catch (err) {
    error.value = err.message || "Could not load decks.";
  }
});
</script>

<template>
  <div
    class="deck-add-control"
    :class="{ 'deck-add-control-compact': compact, 'deck-add-control-inline': !compact }"
    @click.stop
    @mousedown.stop
  >
    <template v-if="decks.length && canAdd">
      <button
        v-if="compact && defaultDeckId && String(defaultDeckId) === String(selectedDeckId)"
        type="button"
        class="deck-add-control-quick"
        :disabled="loading"
        @click.stop="addToDeck"
      >
        {{ quickAddLabel }}
      </button>

      <template v-else>
        <label v-if="!compact" class="deck-add-control-label">Add to deck</label>
        <div class="deck-add-control-row">
          <select
            v-model="selectedDeckId"
            class="deck-add-control-select"
            :disabled="loading"
            aria-label="Deck"
            @click.stop
            @mousedown.stop
          >
            <option v-for="deck in decks" :key="deck.id" :value="String(deck.id)">
              {{ deck.label || deck.name }}
            </option>
          </select>
          <select
            v-if="!compact"
            v-model="section"
            class="deck-add-control-section"
            :disabled="loading"
            aria-label="Section"
            @click.stop
            @mousedown.stop
          >
            <option value="commander">Commander</option>
            <option value="main">Main</option>
            <option value="sideboard">Sideboard</option>
          </select>
          <button
            type="button"
            class="deck-add-control-submit"
            :disabled="loading"
            @click.stop="addToDeck"
          >
            {{ quickAddLabel }}
          </button>
        </div>
      </template>
    </template>

    <p v-else-if="!decks.length && !error" class="deck-add-control-hint">
      No decks yet. Create one from the Decks page or import from Settings.
    </p>

    <p v-if="message" class="deck-add-control-status">{{ message }}</p>
    <p v-else-if="error" class="deck-add-control-status error">{{ error }}</p>
  </div>
</template>
