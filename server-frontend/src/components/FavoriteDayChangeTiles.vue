<script setup>
import { computed, ref, useAttrs } from "vue";
import { formatEuro, formatProfit } from "../utils/format";
import { priceChangeStyle } from "../utils/priceSyncMovers";
import { applySetGalleryIconFallback, resolveSetIconUri, scryfallSmallImageUri } from "../utils/scryfall";
import CardContextMenu from "./CardContextMenu.vue";
import CardPreviewDialog from "./CardPreviewDialog.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps({
  items: { type: Array, default: () => [] },
  variant: { type: String, default: "tiles" },
  emptyLabel: { type: String, default: "No favourites yet." },
  columns: { type: Boolean, default: false },
  showPrice: { type: Boolean, default: false },
});

const attrs = useAttrs();
const showArt = computed(() => props.variant === "tiles" || props.variant === "list");
const showLabel = computed(() => props.variant !== "inline");

const emit = defineEmits(["select", "ownership-changed"]);

const zoomItem = ref(null);
const actionMenu = ref({ open: false, x: 0, y: 0, card: null });

function isCardTile(item) {
  return Boolean(item?.collectorNumber && item?.imageUri);
}

function openZoom(item) {
  zoomItem.value = item;
}

function closeZoom() {
  zoomItem.value = null;
}

function openActions(event, item) {
  const rect = event.currentTarget.getBoundingClientRect();
  actionMenu.value = {
    open: true,
    x: rect.left,
    y: rect.bottom + 4,
    card: item,
  };
}

function closeActions() {
  actionMenu.value = { ...actionMenu.value, open: false };
}

function formatSide(amount) {
  if (!Number(amount)) {
    return formatEuro(0);
  }
  return formatProfit(amount);
}

function priceChangeClass(delta) {
  const value = Number(delta) || 0;
  if (value < 0) {
    return "reports-loss";
  }
  if (value > 0) {
    return "reports-gain";
  }
  return "favorite-day-tile-flat";
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
  <p v-if="!items.length" v-bind="attrs" class="favorite-day-tiles-empty">{{ emptyLabel }}</p>
  <ul
    v-else
    v-bind="attrs"
    class="favorite-day-tiles"
    :class="[`is-${variant}`, { 'is-columns': columns }]"
  >
    <li v-for="item in items" :key="item.id">
      <div
        class="favorite-day-tile"
        :class="{
          'has-art': showArt && Boolean(item.imageUri),
          'has-extra': Boolean($slots.extra),
          'is-up': Number(item.delta) > 0,
          'is-down': Number(item.delta) < 0,
        }"
        :style="priceChangeStyle(item.delta)"
        @click="emit('select', item)"
      >
        <button
          v-if="showArt && item.imageUri"
          type="button"
          class="favorite-day-tile-zoom"
          :aria-label="`View larger image of ${item.label}`"
          @click.stop="openZoom(item)"
        >
          <img
            :src="scryfallSmallImageUri(item.imageUri)"
            alt=""
            class="favorite-day-tile-art"
            width="44"
            height="61"
            loading="lazy"
            decoding="async"
          >
        </button>
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
          <span v-if="showPrice" class="favorite-day-tile-price">
            <span>{{ formatEuro(item.current) }}</span>
            <strong :class="priceChangeClass(item.delta)">({{ formatProfit(item.delta) }})</strong>
          </span>
          <span v-else class="favorite-day-tile-sides">
            <strong v-if="Number(item.up)" class="reports-gain">{{ formatSide(item.up) }}</strong>
            <strong v-if="Number(item.down)" class="reports-loss">{{ formatSide(item.down) }}</strong>
            <strong v-if="!Number(item.up) && !Number(item.down)">{{ formatEuro(0) }}</strong>
          </span>
        </span>
        <button
          v-if="showArt && isCardTile(item)"
          type="button"
          class="favorite-day-tile-menu"
          :class="{ 'is-open': actionMenu.open && actionMenu.card?.id === item.id }"
          aria-label="Card actions"
          title="Card actions"
          @click.stop="openActions($event, item)"
        >
          <span aria-hidden="true">⋮</span>
        </button>
        <slot name="extra" :item="item" />
      </div>
    </li>
  </ul>
  <CardPreviewDialog
    v-if="zoomItem"
    :image-uri="zoomItem.imageUri"
    :alt="zoomItem.name || zoomItem.label || 'Card'"
    :set-code="zoomItem.setCode"
    :collector-number="zoomItem.collectorNumber"
    :finish="zoomItem.finish"
    :seed="zoomItem"
    @close="closeZoom"
  />
  <CardContextMenu
    v-if="actionMenu.open"
    :open="true"
    :card="actionMenu.card"
    :x="actionMenu.x"
    :y="actionMenu.y"
    @close="closeActions"
    @ownership-changed="emit('ownership-changed')"
  />
</template>
