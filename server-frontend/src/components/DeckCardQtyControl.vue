<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import { normalizeCardMenuTarget } from "../composables/cardContextMenu";
import { cardFinish } from "../utils/finishes";

const MAX_DECK_COPIES = 99;

const props = defineProps({
  card: { type: Object, required: true },
  deckId: { type: String, required: true },
  deckName: { type: String, default: "" },
  compact: { type: Boolean, default: false },
  /** Flatten chrome for dense table rows. */
  inline: { type: Boolean, default: false },
});

const emit = defineEmits(["changed", "removed"]);

const busy = ref(false);
const error = ref("");
const ready = ref(false);
const deckQty = ref(0);
const section = ref("main");

const target = computed(() => normalizeCardMenuTarget(props.card));
const canAdjust = computed(() => Boolean(target.value?.setCode && target.value?.collectorNumber && props.deckId));
const canIncrease = computed(() => deckQty.value < MAX_DECK_COPIES);
const canDecrease = computed(() => deckQty.value > 0);

function cardPayload() {
  return {
    setCode: target.value.setCode,
    collectorNumber: target.value.collectorNumber,
    finish: cardFinish(props.card),
    section: section.value,
  };
}

function pickDeckRow(cards) {
  const finish = cardFinish(props.card);
  const matches = (cards || []).filter(
    (row) =>
      row.setCode === target.value.setCode &&
      String(row.collectorNumber) === String(target.value.collectorNumber) &&
      cardFinish(row) === finish,
  );
  if (!matches.length) {
    return null;
  }
  return matches.find((row) => row.section === "main") || matches[0];
}

async function syncFromDeck() {
  if (!canAdjust.value) {
    ready.value = true;
    return;
  }
  if (props.card?.qty != null && props.card?.section) {
    deckQty.value = Number(props.card.qty) || 0;
    section.value = String(props.card.section).trim().toLowerCase() || "main";
    ready.value = true;
    return;
  }
  try {
    const browse = await api.getDeckBrowse(props.deckId);
    const row = pickDeckRow(browse.cards);
    if (row) {
      deckQty.value = Number(row.qty) || 0;
      section.value = String(row.section || "main").trim().toLowerCase();
    } else {
      deckQty.value = 0;
      section.value = "main";
    }
  } catch (err) {
    error.value = err.message || "Could not load deck count.";
  } finally {
    ready.value = true;
  }
}

async function onAdjust(delta) {
  if (!canAdjust.value || busy.value) {
    return;
  }
  if (delta > 0 && !canIncrease.value) {
    return;
  }
  if (delta < 0 && !canDecrease.value) {
    return;
  }

  const previousQty = deckQty.value;
  busy.value = true;
  error.value = "";
  deckQty.value = Math.max(0, previousQty + delta);

  try {
    const result = await api.adjustDeckCardQty(props.deckId, {
      ...cardPayload(),
      delta,
    });
    clearClientCache();
    deckQty.value = result.qty || 0;
    emit("changed", result);
    if (result.removed) {
      emit("removed", result);
    }
  } catch (err) {
    deckQty.value = previousQty;
    error.value = err.message || "Could not update deck count.";
  } finally {
    busy.value = false;
  }
}

async function onDelete() {
  if (!canAdjust.value || busy.value || deckQty.value <= 0) {
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const result = await api.removeCardFromDeck(props.deckId, {
      ...cardPayload(),
      qty: deckQty.value,
    });
    clearClientCache();
    deckQty.value = 0;
    emit("changed", result);
    emit("removed", result);
  } catch (err) {
    error.value = err.message || "Could not remove card from deck.";
  } finally {
    busy.value = false;
  }
}

onMounted(syncFromDeck);

watch(
  () => [
    props.deckId,
    props.card?.setCode,
    props.card?.collectorNumber,
    props.card?.finish,
    props.card?.qty,
    props.card?.section,
  ],
  syncFromDeck,
);
</script>

<template>
  <div
    v-if="ready && canAdjust && deckQty > 0"
    class="deck-card-qty-tile"
    :class="{
      'deck-card-qty-tile-compact': compact,
      'deck-card-qty-tile-inline': inline,
    }"
    @click.stop
    @mousedown.stop
  >
    <div class="deck-card-qty-tile-row">
      <div class="card-interactive-stepper deck-card-qty-tile-stepper">
        <button
          type="button"
          class="card-interactive-step"
          :disabled="busy || !canDecrease"
          aria-label="Remove one copy from deck"
          @click.stop="onAdjust(-1)"
        >
          −
        </button>
        <span class="card-interactive-count">{{ deckQty }}</span>
        <button
          type="button"
          class="card-interactive-step"
          :disabled="busy || !canIncrease"
          aria-label="Add one copy to deck"
          @click.stop="onAdjust(1)"
        >
          +
        </button>
      </div>
      <button
        type="button"
        class="deck-card-qty-tile-remove"
        aria-label="Remove from deck"
        title="Remove from deck"
        :disabled="busy"
        @click.stop="onDelete"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path
            d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
            fill="currentColor"
          />
        </svg>
      </button>
    </div>
    <p v-if="busy" class="deck-card-qty-tile-status">Updating…</p>
    <p v-else-if="error" class="deck-card-qty-tile-status error">{{ error }}</p>
  </div>
</template>
