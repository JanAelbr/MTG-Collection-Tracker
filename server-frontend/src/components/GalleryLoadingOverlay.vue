<script setup>
import LoadingIndicator from "./LoadingIndicator.vue";

defineProps({
  loading: { type: Boolean, default: false },
  label: { type: String, default: "Loading…" },
});
</script>

<template>
  <div class="gallery-loading-wrap" :class="{ 'is-loading': loading }">
    <div
      v-if="loading"
      class="gallery-loading-overlay"
      aria-live="polite"
      aria-busy="true"
    >
      <LoadingIndicator :label="label" />
    </div>
    <div class="gallery-loading-content">
      <slot />
    </div>
  </div>
</template>
