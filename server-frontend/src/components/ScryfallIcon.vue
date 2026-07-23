<script setup>
defineProps({
  size: { type: Number, default: 16 },
});
</script>

<template>
  <!-- Simplified Scryfall mark (lens + handle) for small link icons. -->
  <svg
    class="scryfall-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    aria-hidden="true"
    focusable="false"
  >
    <path
      fill="currentColor"
      fill-rule="evenodd"
      d="M10.5 3.25a7.25 7.25 0 1 0 4.556 12.882l4.156 4.156a.75.75 0 1 0 1.06-1.06l-4.155-4.156A7.25 7.25 0 0 0 10.5 3.25Zm-5.75 7.25a5.75 5.75 0 1 1 11.5 0 5.75 5.75 0 0 1-11.5 0Z"
    />
  </svg>
</template>
