<script setup>
import { computed, onMounted, ref, watch } from "vue";
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
});

const payload = ref(null);
const loading = ref(false);
const error = ref("");

const bracket = computed(() => payload.value?.bracket || 1);
const components = computed(() => payload.value?.components || {});
const counts = computed(() => payload.value?.counts || {});
const categoryCards = computed(() => payload.value?.categoryCards || {});

async function loadPower() {
  if (!props.deckId) {
    payload.value = null;
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    payload.value = await api.getDeckPower(props.deckId);
  } catch (err) {
    error.value = err?.message || "Could not load power assessment.";
    payload.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(loadPower);
watch(() => [props.deckId, props.refreshKey], loadPower);
</script>

<template>
  <section class="deck-power-panel">
    <div v-if="loading" class="deck-power-loading">
      <LoadingIndicator label="Assessing deck…" />
    </div>

    <p v-else-if="error" class="deck-power-error">{{ error }}</p>

    <template v-else-if="payload">
      <header class="deck-power-hero">
        <div class="deck-power-hero-main">
          <span class="deck-power-bracket-value">{{ bracket }}</span>
          <div>
            <p class="deck-power-bracket-label">{{ bracketLabel(bracket) }}</p>
            <p class="deck-power-bracket-copy">{{ bracketDescription(bracket) }}</p>
          </div>
        </div>
        <div class="deck-power-hero-meta">
          <span class="deck-power-confidence">{{ confidenceLabel(payload.confidence) }}</span>
          <span v-if="payload.powerSignal != null" class="deck-power-signal">
            Signal {{ payload.powerSignal }}
          </span>
        </div>
      </header>

      <div v-if="payload.highlights?.length" class="deck-power-chip-row">
        <span
          v-for="item in payload.highlights"
          :key="item"
          class="deck-power-chip deck-power-chip--highlight"
        >
          {{ item }}
        </span>
      </div>

      <div v-if="payload.warnings?.length" class="deck-power-chip-row">
        <span
          v-for="item in payload.warnings"
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
