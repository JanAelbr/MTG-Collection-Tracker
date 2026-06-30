<script setup>
defineProps({
  imageUri: { type: String, default: "" },
});
</script>

<template>
  <span
    class="card-preview"
    :data-image="imageUri || undefined"
    :class="{ 'card-preview-disabled': !imageUri }"
  >
    <slot />
  </span>
</template>
