<script setup>
import { computed } from "vue";
import { manaSymbolUrl, parseManaCostSymbols } from "../utils/deckStackStyles.js";

const props = defineProps({
  manaCost: { type: String, default: "" },
  symbol: { type: String, default: "" },
  size: { type: Number, default: 16 },
});

const symbols = computed(() => {
  const single = String(props.symbol || "").trim();
  if (single) {
    return [single];
  }
  return parseManaCostSymbols(props.manaCost);
});
</script>

<template>
  <span v-if="symbols.length" class="mana-symbols" :style="{ '--mana-size': `${size}px` }">
    <img
      v-for="(entry, index) in symbols"
      :key="`${entry}-${index}`"
      class="mana-symbol"
      :src="manaSymbolUrl(entry)"
      :alt="entry"
      loading="lazy"
    >
  </span>
  <span v-else>—</span>
</template>
