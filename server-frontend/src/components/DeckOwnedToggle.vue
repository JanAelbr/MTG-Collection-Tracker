<script setup>
import { computed, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import {
  effectiveDeckOwnedQty,
  isDeckCardFullyOwned,
  ownershipRevision,
  setOwnershipPatch,
} from "../composables/cardContextMenu";
import { cardFinish } from "../utils/finishes";

const props = defineProps({
  card: { type: Object, required: true },
  deckId: { type: String, required: true },
  compact: { type: Boolean, default: false },
  /** Flatten chrome for dense table rows. */
  inline: { type: Boolean, default: false },
  showLabel: { type: Boolean, default: true },
});

const emit = defineEmits(["changed"]);

const busy = ref(false);
const error = ref("");

const ownershipTick = computed(() => ownershipRevision.value);

const canToggle = computed(() => (
  Boolean(props.deckId && props.card?.setCode && props.card?.collectorNumber != null
    && String(props.card.collectorNumber).trim())
));

const fullyOwned = computed(() => {
  ownershipTick.value;
  return isDeckCardFullyOwned(props.card);
});

const ownedQty = computed(() => {
  ownershipTick.value;
  return effectiveDeckOwnedQty(props.card);
});

const partialLabel = computed(() => {
  ownershipTick.value;
  const qty = Number(props.card?.qty) || 0;
  if (fullyOwned.value || ownedQty.value <= 0 || ownedQty.value >= qty) {
    return "";
  }
  return `${ownedQty.value}/${qty}`;
});

const ariaLabel = computed(() => {
  const name = props.card?.cardName || "card";
  return fullyOwned.value
    ? `Mark ${name} as not owned in deck`
    : `Mark ${name} as owned in deck`;
});

async function onChange(event) {
  if (!canToggle.value || busy.value) {
    return;
  }
  const owned = Boolean(event?.target?.checked);
  busy.value = true;
  error.value = "";
  try {
    const result = await api.setDeckCardOwned(props.deckId, {
      setCode: props.card.setCode,
      collectorNumber: props.card.collectorNumber,
      finish: cardFinish(props.card),
      section: props.card.section || "main",
      owned,
    });
    setOwnershipPatch(
      props.card.setCode,
      props.card.collectorNumber,
      cardFinish(props.card),
      {
        owned: (result.ownedQty ?? 0) > 0,
        ownedCount: result.ownedQty ?? 0,
      },
    );
    clearClientCache();
    emit("changed", result);
  } catch (err) {
    error.value = err?.message || "Could not update owned status.";
    if (event?.target) {
      event.target.checked = fullyOwned.value;
    }
  } finally {
    busy.value = false;
  }
}

watch(
  () => [props.card?.ownedQty, props.card?.qty, ownershipRevision.value],
  () => {
    error.value = "";
  },
);
</script>

<template>
  <div
    v-if="canToggle"
    class="deck-owned-toggle"
    :class="{
      'deck-owned-toggle-compact': compact,
      'deck-owned-toggle-inline': inline,
      'is-owned': fullyOwned,
      'is-partial': !fullyOwned && ownedQty > 0,
      'is-missing': !fullyOwned && ownedQty <= 0,
    }"
    @click.stop
    @mousedown.stop
  >
    <label class="deck-owned-toggle-label">
      <input
        type="checkbox"
        class="deck-owned-toggle-input"
        :checked="fullyOwned"
        :disabled="busy"
        :aria-label="ariaLabel"
        @change="onChange"
      >
      <span v-if="showLabel && !compact" class="deck-owned-toggle-text">
        <template v-if="fullyOwned">Owned</template>
        <template v-else-if="partialLabel">{{ partialLabel }} owned</template>
        <template v-else>Missing</template>
      </span>
      <span
        v-else-if="compact && partialLabel"
        class="deck-owned-partial"
      >{{ partialLabel }}</span>
    </label>
    <p v-if="error" class="deck-owned-toggle-error">{{ error }}</p>
  </div>
  <span v-else-if="showLabel" class="deck-owned-toggle-fallback">
    {{ fullyOwned ? "Owned" : (partialLabel ? `${partialLabel} owned` : "Missing") }}
  </span>
</template>
