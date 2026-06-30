<script setup>
import { computed } from "vue";

const props = defineProps({
  colors: { type: Array, default: () => [] },
  size: { type: Number, default: 18 },
});

const symbols = computed(() => {
  if (!props.colors?.length) {
    return ["C"];
  }
  return props.colors;
});

function symbolUrl(symbol) {
  return `https://svgs.scryfall.io/card-symbols/${encodeURIComponent(symbol)}.svg`;
}
</script>

<template>
  <span class="mana-symbols" :style="{ '--mana-size': `${size}px` }">
    <img
      v-for="symbol in symbols"
      :key="symbol"
      class="mana-symbol"
      :src="symbolUrl(symbol)"
      :alt="symbol"
      loading="lazy"
    >
  </span>
</template>
