<script setup>
import { computed } from "vue";
import { formatEuro, formatProfit } from "../utils/format";
import { applySetGalleryIconFallback, resolveSetIconUri } from "../utils/scryfall";

const props = defineProps({
  items: { type: Array, default: () => [] },
  variant: { type: String, default: "tiles" },
  emptyLabel: { type: String, default: "No favourites yet." },
});

const showArt = computed(() => props.variant === "tiles");
const showLabel = computed(() => props.variant !== "inline");

const emit = defineEmits(["select"]);

function formatSide(amount) {
  if (!Number(amount)) {
    return formatEuro(0);
  }
  return formatProfit(amount);
}

function setIcon(item) {
  return item.iconUri || resolveSetIconUri({ setCode: item.setCode }) || "";
}

function onSetIconError(event, item) {
  if (!applySetGalleryIconFallback(event.target, { setCode: item.setCode })) {
    event.target.style.display = "none";
  }
}
</script>

<template>
  <p v-if="!items.length" class="favorite-day-tiles-empty">{{ emptyLabel }}</p>
  <ul v-else class="favorite-day-tiles" :class="`is-${variant}`">
    <li v-for="item in items" :key="item.id">
      <button
        type="button"
        class="favorite-day-tile"
        :class="{ 'has-art': showArt && Boolean(item.imageUri) }"
        @click="emit('select', item)"
      >
        <img
          v-if="showArt && item.imageUri"
          :src="item.imageUri"
          alt=""
          class="favorite-day-tile-art"
        >
        <img
          v-else-if="showArt && setIcon(item)"
          :src="setIcon(item)"
          alt=""
          class="favorite-day-tile-icon"
          :title="item.setCode"
          @error="onSetIconError($event, item)"
        >
        <span class="favorite-day-tile-copy">
          <span
            v-if="showLabel"
            class="favorite-day-tile-label"
            :title="item.label"
          >{{ item.label }}</span>
          <span class="favorite-day-tile-sides">
            <strong class="reports-gain">{{ formatSide(item.up) }}</strong>
            <strong class="reports-loss">{{ formatSide(item.down) }}</strong>
          </span>
        </span>
      </button>
    </li>
  </ul>
</template>
