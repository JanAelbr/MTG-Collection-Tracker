<script setup>
defineProps({
  size: { type: Number, default: 28 },
});
</script>

<template>
  <svg
    class="app-logo-icon"
    :width="size"
    :height="size"
    viewBox="0 0 32 32"
    aria-hidden="true"
    focusable="false"
  >
    <defs>
      <g id="app-logo-card-back">
        <rect width="10" height="14" rx="0.9" fill="#3a2618" />
        <rect x="0.35" y="0.35" width="9.3" height="13.3" rx="0.75" fill="#c9a24d" />
        <rect x="0.8" y="0.8" width="8.4" height="12.4" rx="0.55" fill="#173d7a" />
        <rect
          x="1.35"
          y="1.35"
          width="7.3"
          height="11.3"
          rx="0.35"
          fill="none"
          stroke="#e0c078"
          stroke-width="0.35"
        />
        <circle cx="5" cy="7" r="2.45" fill="#2b6cb0" />
        <circle cx="5" cy="7" r="1.55" fill="#4d97d4" />
        <path
          fill="#b8dff7"
          d="M5 4.35 5.45 5.95 7.1 5.55 5.95 6.75 7.35 7.55 5.75 7.2 5.55 8.75 5.35 7.2 3.75 7.55 5.15 6.75 4 5.55 5.65 5.95Z"
        />
        <path
          fill="#8ec5eb"
          opacity="0.85"
          d="M5 5.1 5.2 6.1 6.2 5.9 5.45 6.55 6.35 7.1 5.35 6.9 5.25 7.9 5.15 6.9 4.15 7.1 5.05 6.55 4.3 5.9 5.3 6.1Z"
        />
      </g>
    </defs>

    <!-- Left card -->
    <use href="#app-logo-card-back" transform="translate(2.5 10) rotate(-16 5 12)" />
    <!-- Right card -->
    <use href="#app-logo-card-back" transform="translate(19.5 10) rotate(16 5 12)" />
    <!-- Center card (on top) -->
    <use href="#app-logo-card-back" transform="translate(11 4)" />
  </svg>
</template>
