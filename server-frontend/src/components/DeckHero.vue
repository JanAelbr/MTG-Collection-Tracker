<script setup>
import { computed } from "vue";
import { formatDeckOwned, formatDeckValueRange, formatEuro } from "../utils/format";

const props = defineProps({
  deck: { type: Object, default: null },
  stats: { type: Object, default: null },
  deckId: { type: String, default: "" },
});

const deckSize = computed(() => props.stats?.deckSize || 0);
const ownedQty = computed(() => props.stats?.ownedQty || 0);
const missingQty = computed(() => props.stats?.missingQty || 0);

const completionPercent = computed(() => {
  if (props.stats?.ownedCoverage != null) {
    return Math.min(100, Math.max(0, props.stats.ownedCoverage));
  }
  if (!deckSize.value) {
    return 0;
  }
  return Math.min(100, (ownedQty.value / deckSize.value) * 100);
});

const completionLabel = computed(() => {
  const ownedText = formatDeckOwned(ownedQty.value, deckSize.value) || String(ownedQty.value);
  if (missingQty.value > 0) {
    return `${ownedText} owned · ${missingQty.value} missing`;
  }
  return `${ownedText} owned · complete`;
});

const secondaryMeta = computed(() => {
  const parts = [];
  if (props.stats?.purchasePrice != null) {
    parts.push(`Purchase ${formatEuro(props.stats.purchasePrice)}`);
  }
  if (props.stats?.trackedCoverage != null) {
    parts.push(`Priced ${props.stats.trackedCoverage}%`);
  }
  return parts.join(" · ");
});
</script>

<template>
  <section v-if="deck && stats" class="deck-hero">
    <p class="deck-hero-deck-value">
      {{ formatDeckValueRange(stats.ownedCurrent, stats.current) }}
    </p>

    <div class="deck-hero-completion">
      <div
        class="deck-hero-completion-bar"
        role="progressbar"
        :aria-valuenow="Math.round(completionPercent)"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="`${Math.round(completionPercent)}% owned`"
      >
        <span
          class="deck-hero-completion-fill"
          :class="{ 'is-complete': completionPercent >= 100 }"
          :style="{ width: `${completionPercent}%` }"
        />
      </div>
      <p class="deck-hero-completion-meta">
        <strong>{{ Math.round(completionPercent) }}%</strong>
        <span>{{ completionLabel }}</span>
      </p>
      <p v-if="secondaryMeta" class="deck-hero-secondary-meta">{{ secondaryMeta }}</p>
    </div>
  </section>
</template>
