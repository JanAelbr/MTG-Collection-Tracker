<script setup>
defineProps({
  imageUri: { type: String, default: "" },
  imageUriBack: { type: String, default: "" },
});
</script>

<template>
  <span
    class="card-preview"
    :data-image="imageUri || undefined"
    :data-image-back="imageUriBack || undefined"
    :class="{ 'card-preview-disabled': !imageUri }"
  >
    <slot />
  </span>
</template>
