<script setup>
import { computed } from "vue";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  cardFinish,
  finishLabel,
} from "../utils/finishes";

const props = defineProps({
  card: { type: Object, default: null },
  finish: { type: [Number, String], default: null },
  variant: {
    type: String,
    default: "inline",
    validator: (value) => ["inline", "overlay"].includes(value),
  },
  compact: { type: Boolean, default: false },
});

const resolvedFinish = computed(() => {
  if (props.finish != null && props.finish !== "") {
    return cardFinish({ finish: props.finish });
  }
  return cardFinish(props.card);
});

const show = computed(() => resolvedFinish.value !== FINISH_NONFOIL);
const isFoil = computed(() => resolvedFinish.value === FINISH_FOIL);
const isEtched = computed(() => resolvedFinish.value === FINISH_ETCHED);
const label = computed(() => finishLabel(resolvedFinish.value));
</script>

<template>
  <span
    v-if="show"
    class="card-finish-badge"
    :class="[
      `is-finish-${resolvedFinish}`,
      variant === 'overlay' ? 'card-finish-badge--overlay' : 'card-finish-badge--inline',
      { 'card-finish-badge--compact': compact },
    ]"
    :title="label"
    :aria-label="label"
  >
    <svg
      v-if="isFoil"
      class="card-finish-badge-icon"
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <path
        d="M8 1.2 9.7 5.9 14.6 6.1 10.7 9.1 12.1 14 8 11.4 3.9 14 5.3 9.1 1.4 6.1 6.3 5.9Z"
        fill="currentColor"
      />
    </svg>
    <span v-if="!compact || isEtched" class="card-finish-badge-label">
      {{ isEtched ? "Etched" : "Foil" }}
    </span>
  </span>
</template>
