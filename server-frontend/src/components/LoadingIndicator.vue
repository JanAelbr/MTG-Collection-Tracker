<script setup>
defineProps({
  label: {
    type: String,
    default: "Loading…",
  },
  compact: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <div
    class="loading-indicator"
    :class="{ 'loading-indicator--compact': compact }"
    aria-live="polite"
    aria-busy="true"
  >
    <span class="loading-spinner" />
    <span>{{ label }}</span>
  </div>
</template>
