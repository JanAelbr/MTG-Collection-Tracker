<script setup>
import { computed } from "vue";

const props = defineProps({
  modelValue: { type: Number, default: 100 },
  options: { type: Array, default: () => [75, 100, 125, 150] },
});

const emit = defineEmits(["update:modelValue"]);

const normalizedOptions = computed(() =>
  props.options.map((scale) => Number(scale)).filter((scale) => Number.isFinite(scale)),
);

const currentIndex = computed(() => {
  const index = normalizedOptions.value.indexOf(props.modelValue);
  return index >= 0 ? index : 0;
});

const displayScale = computed(() => normalizedOptions.value[currentIndex.value] ?? props.modelValue);

const canDecrease = computed(() => currentIndex.value > 0);
const canIncrease = computed(() => currentIndex.value < normalizedOptions.value.length - 1);

const readout = computed(() => `${displayScale.value}%`);

function decrease() {
  if (!canDecrease.value) {
    return;
  }
  emit("update:modelValue", normalizedOptions.value[currentIndex.value - 1]);
}

function increase() {
  if (!canIncrease.value) {
    return;
  }
  emit("update:modelValue", normalizedOptions.value[currentIndex.value + 1]);
}
</script>

<template>
  <div
    class="collection-gallery-scale"
    role="group"
    :aria-label="`Image size, ${readout}`"
  >
    <button
      type="button"
      class="collection-gallery-scale-btn"
      :disabled="!canDecrease"
      aria-label="Smaller images"
      title="Smaller images"
      @click="decrease"
    >
      −
    </button>
    <span class="collection-gallery-scale-label">
      <svg
        class="collection-gallery-scale-icon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="10.5" cy="10.5" r="6.25" fill="none" stroke="currentColor" stroke-width="2" />
        <path
          d="M15.5 15.5L20 20"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        />
      </svg>
      <span class="collection-gallery-scale-readout" aria-hidden="true">{{ readout }}</span>
    </span>
    <button
      type="button"
      class="collection-gallery-scale-btn"
      :disabled="!canIncrease"
      aria-label="Larger images"
      title="Larger images"
      @click="increase"
    >
      +
    </button>
  </div>
</template>
