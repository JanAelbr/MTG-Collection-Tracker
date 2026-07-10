<script setup>
import { computed } from "vue";
import { FINISH_FOIL, FINISH_NONFOIL, normalizeFinish } from "../utils/finishes";

const props = defineProps({
  finish: { type: [Number, String], default: FINISH_NONFOIL },
  disabled: { type: Boolean, default: false },
});

defineEmits(["toggle"]);

const normalizedFinish = computed(() => normalizeFinish(props.finish));
const isFoil = computed(() => normalizedFinish.value === FINISH_FOIL);
const ariaLabel = computed(() => (
  isFoil.value ? "Switch to non-foil" : "Switch to foil"
));
const title = computed(() => (
  isFoil.value ? "Foil — click for non-foil" : "Non-foil — click for foil"
));
</script>

<template>
  <button
    type="button"
    class="finish-toggle-btn"
    :class="{ 'is-foil': isFoil }"
    :disabled="disabled"
    :aria-label="ariaLabel"
    :title="title"
    @click.stop="$emit('toggle')"
  >
    <svg
      v-if="isFoil"
      class="finish-toggle-icon"
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <path
        d="M8 1.2 9.7 5.9 14.6 6.1 10.7 9.1 12.1 14 8 11.4 3.9 14 5.3 9.1 1.4 6.1 6.3 5.9Z"
        fill="currentColor"
      />
    </svg>
    <svg
      v-else
      class="finish-toggle-icon"
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <rect
        x="3.25"
        y="2.25"
        width="9.5"
        height="11.5"
        rx="1.35"
        fill="currentColor"
      />
      <rect
        x="5.1"
        y="5"
        width="5.8"
        height="1.1"
        rx="0.35"
        fill="#fff"
        opacity="0.42"
      />
      <rect
        x="5.1"
        y="7.1"
        width="4.2"
        height="1.1"
        rx="0.35"
        fill="#fff"
        opacity="0.42"
      />
    </svg>
  </button>
</template>
