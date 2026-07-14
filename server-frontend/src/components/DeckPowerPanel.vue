<script setup>
import { computed, ref, watch } from "vue";
import { api } from "../api";
import DeckPowerCategorySection from "./DeckPowerCategorySection.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import {
  POWER_COMPONENTS,
  bracketDescription,
  bracketLabel,
  confidenceLabel,
} from "../utils/deckPower";

const props = defineProps({
  deckId: { type: [String, Number], default: "" },
  refreshKey: { type: [String, Number], default: "" },
  powerPayload: { type: Object, default: null },
});

const displayPayload = ref(null);
const loading = ref(false);
const error = ref("");

const bracket = computed(() => displayPayload.value?.bracket || 1);
const components = computed(() => displayPayload.value?.components || {});
const counts = computed(() => displayPayload.value?.counts || {});
const categoryCards = computed(() => displayPayload.value?.categoryCards || {});

async function loadPower() {
  if (props.powerPayload) {
    displayPayload.value = props.powerPayload;
    loading.value = false;
    error.value = "";
    return;
  }
  if (!props.deckId) {
    displayPayload.value = null;
    loading.value = false;
    error.value = "";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    displayPayload.value = await api.getDeckPower(props.deckId);
  } catch (err) {
    error.value = err?.message || "Could not load power assessment.";
    displayPayload.value = null;
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.deckId, props.refreshKey, props.powerPayload],
  loadPower,
  { immediate: true },
);
</script>

<template>
  <section class="deck-power-panel">
    <div v-if="loading" class="deck-power-loading">
      <LoadingIndicator label="Assessing deck…" />
    </div>

    <p v-else-if="error" class="deck-power-error">{{ error }}</p>

    <p v-else-if="!displayPayload" class="deck-power-empty">
      Power analysis is not available for this proposal yet.
    </p>

    <template v-else>
      <header class="deck-power-hero">
        <div class="deck-power-hero-main">
          <span class="deck-power-bracket-value">{{ bracket }}</span>
          <div>
            <p class="deck-power-bracket-label">{{ bracketLabel(bracket) }}</p>
            <p class="deck-power-bracket-copy">{{ bracketDescription(bracket) }}</p>
          </div>
        </div>
        <div class="deck-power-hero-meta">
          <span class="deck-power-confidence">{{ confidenceLabel(displayPayload.confidence) }}</span>
          <span v-if="displayPayload.powerSignal != null" class="deck-power-signal">
            Signal {{ displayPayload.powerSignal }}
          </span>
        </div>
      </header>

      <div v-if="displayPayload.highlights?.length" class="deck-power-chip-row">
        <span
          v-for="item in displayPayload.highlights"
          :key="item"
          class="deck-power-chip deck-power-chip--highlight"
        >
          {{ item }}
        </span>
      </div>

      <div v-if="displayPayload.warnings?.length" class="deck-power-chip-row">
        <span
          v-for="item in displayPayload.warnings"
          :key="item"
          class="deck-power-chip deck-power-chip--warning"
        >
          {{ item }}
        </span>
      </div>

      <div class="deck-power-categories">
        <DeckPowerCategorySection
          v-for="component in POWER_COMPONENTS"
          :key="component.id"
          :component="component"
          :score="components[component.id] ?? 0"
          :counts="counts"
          :cards="categoryCards[component.id] || []"
          :deck-id="deckId"
        />
      </div>
    </template>
  </section>
</template>
