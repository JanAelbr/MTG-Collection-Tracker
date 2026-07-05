<script setup>
defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ["binder", "deck", "storage"].includes(value),
  },
});
</script>

<template>
  <svg
    class="storage-location-type-icon"
    :class="`storage-location-type-icon--${type}`"
    viewBox="0 0 24 24"
    aria-hidden="true"
    focusable="false"
  >
    <template v-if="type === 'binder'">
      <path
        d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7 0v18H5V5h7zm2 0h5v18h-5V5z"
        fill="currentColor"
      />
    </template>
    <template v-else-if="type === 'deck'">
      <path
        d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14z"
        fill="currentColor"
        opacity="0.35"
      />
      <path
        d="M19 7H5c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2z"
        fill="currentColor"
      />
    </template>
    <template v-else>
      <path
        d="M20.54 5.23l-1.39-1.68C18.88 3.21 18.47 3 18 3H6c-.47 0-.88.21-1.16.55L3.46 5.23C3.17 5.57 3 6.02 3 6.5V19c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6.5c0-.48-.17-.93-.46-1.27zM12 17.5L6.5 12H10v-2h4v2h3.5L12 17.5zM5.12 5l.81-1h12l.94 1H5.12z"
        fill="currentColor"
      />
    </template>
  </svg>
</template>
