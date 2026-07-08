<script setup>
import { computed } from "vue";
import { COLLECTION_TYPE_ORDER } from "../utils/collectionTypes";

const SUPPORTED_TYPES = new Set([
  ...COLLECTION_TYPE_ORDER,
  "commander",
  "sideboard",
]);

const props = defineProps({
  type: { type: String, default: "" },
  label: { type: String, default: "" },
});

const iconType = computed(() => {
  const normalized = String(props.type || "").toLowerCase();
  if (normalized === "tribal") {
    return "kindred";
  }
  return SUPPORTED_TYPES.has(normalized) ? normalized : "";
});
</script>

<template>
  <svg
    v-if="iconType"
    class="deck-type-icon"
    :class="`deck-type-icon--${iconType}`"
    viewBox="0 0 24 24"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : 'true'"
    focusable="false"
  >
    <!-- Creature: paw -->
    <template v-if="iconType === 'creature'">
      <circle cx="7.5" cy="8" r="2" fill="currentColor" />
      <circle cx="12" cy="6" r="2" fill="currentColor" />
      <circle cx="16.5" cy="8" r="2" fill="currentColor" />
      <circle cx="9" cy="11.5" r="1.8" fill="currentColor" />
      <circle cx="15" cy="11.5" r="1.8" fill="currentColor" />
      <path
        d="M12 14.5c-3.8 0-6.5 2.2-6.5 5 0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5c0-2.8-2.7-5-6.5-5z"
        fill="currentColor"
      />
    </template>

    <!-- Planeswalker: spark -->
    <template v-else-if="iconType === 'planeswalker'">
      <circle cx="12" cy="12" r="3.5" fill="currentColor" />
      <path
        d="M12 2.5v4M12 17.5v4M4.2 4.2l2.8 2.8M17 17l2.8 2.8M2.5 12h4M17.5 12h4M4.2 19.8l2.8-2.8M17 7l2.8-2.8"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      />
    </template>

    <!-- Enchantment: star aura -->
    <template v-else-if="iconType === 'enchantment'">
      <path
        d="M12 3l2.2 6.8H21l-5.5 4 2.1 6.7L12 17.2 6.4 20.5l2.1-6.7L3 9.8h6.8L12 3z"
        fill="currentColor"
      />
    </template>

    <!-- Artifact: gear -->
    <template v-else-if="iconType === 'artifact'">
      <path
        d="M12 8.2a3.8 3.8 0 100 7.6 3.8 3.8 0 000-7.6zm8.3 3.4l1.9-1.1-1.4-2.4-2.1.4a7.4 7.4 0 00-1.3-1.1l.4-2.1-2.4-1.4-1.1 1.9a7.6 7.6 0 00-2.2 0l-1.1-1.9-2.4 1.4.4 2.1c-.5.3-.9.7-1.3 1.1l-2.1-.4-1.4 2.4 1.9 1.1c-.1.7-.1 1.5 0 2.2l-1.9 1.1 1.4 2.4 2.1-.4c.4.4.8.8 1.3 1.1l-.4 2.1 2.4 1.4 1.1-1.9c.7.1 1.5.1 2.2 0l1.1 1.9 2.4-1.4-.4-2.1c.5-.3.9-.7 1.3-1.1l2.1.4 1.4-2.4-1.9-1.1c.1-.7.1-1.5 0-2.2z"
        fill="currentColor"
      />
    </template>

    <!-- Instant: bolt -->
    <template v-else-if="iconType === 'instant'">
      <path
        d="M13.2 2 4 14.2h6.3L9.8 22l9.2-11.4H13l.2-8.6z"
        fill="currentColor"
      />
    </template>

    <!-- Sorcery: flame -->
    <template v-else-if="iconType === 'sorcery'">
      <path
        d="M12 4c0 3.2-3.5 4.5-3.5 8a3.5 3.5 0 107 0c0-2.2-1.6-3.4-2.5-5.2C12.8 8.8 12 6.8 12 4z"
        fill="currentColor"
      />
    </template>

    <!-- Land: mountains -->
    <template v-else-if="iconType === 'land'">
      <path
        d="M3 20h18L15.5 9.5 12 14 8.5 8 3 20z"
        fill="currentColor"
      />
    </template>

    <!-- Battle: crossed blades -->
    <template v-else-if="iconType === 'battle'">
      <path
        d="M6.5 4 4 6.5 9.5 12 4 17.5 6.5 20 12 14.5 17.5 20 20 17.5 14.5 12 20 6.5 17.5 4 12 9.5 6.5 4z"
        fill="currentColor"
      />
    </template>

    <!-- Kindred / Tribal: pennant -->
    <template v-else-if="iconType === 'kindred'">
      <path d="M6 3v18" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      <path d="M8 5h11l-3 4 3 4H8V5z" fill="currentColor" />
    </template>

    <!-- Commander: crown -->
    <template v-else-if="iconType === 'commander'">
      <path
        d="M4 18v2h16v-2H4zm2.2-8 2.3 4.5 3.5-6.5 3.5 6.5 2.3-4.5L19 16H5l1.2-6z"
        fill="currentColor"
      />
    </template>

    <!-- Sideboard: card stack -->
    <template v-else-if="iconType === 'sideboard'">
      <rect x="5" y="5" width="12" height="15" rx="1.5" fill="currentColor" opacity="0.35" />
      <rect x="7" y="3" width="12" height="15" rx="1.5" fill="currentColor" opacity="0.6" />
      <rect x="9" y="6" width="12" height="15" rx="1.5" fill="currentColor" />
    </template>
  </svg>
</template>
