<script setup>
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { api, ignoreAborted } from "../api";
import CardContextMenu from "./CardContextMenu.vue";
import CardPreviewDialog from "./CardPreviewDialog.vue";
import { formatEuro, formatProfit } from "../utils/format";
import { cardFinish, cardRouteQuery } from "../utils/finishes";
import { moverRowToTileCard, priceChangeStyle, priceChangeTinted } from "../utils/priceSyncMovers";
import { scryfallSmallImageUri } from "../utils/scryfall";

const props = defineProps({
  rows: { type: Array, default: () => [] },
  sourceCards: { type: Array, default: () => [] },
  direction: { type: String, default: "" },
  variant: { type: String, default: "" },
  backgroundFloor: { type: Number, default: 0 },
});

const router = useRouter();
const zoomCard = ref(null);
const actionMenu = ref({ open: false, x: 0, y: 0, card: null });

function tileCard(row) {
  return moverRowToTileCard(row);
}

function changeClass(row) {
  if (props.direction === "down") {
    return "is-down";
  }
  if (props.direction === "up") {
    return "is-up";
  }
  return Number(row?.delta) < 0 ? "is-down" : "is-up";
}

function formatDelta(row) {
  return formatProfit((Number(row?.current) || 0) - (Number(row?.previous) || 0));
}

const deckPeak = computed(() => {
  let peak = 0;
  for (const row of props.rows || []) {
    peak = Math.max(peak, Math.abs(Number(row?.delta) || 0));
  }
  return peak;
});

function deckBarWidth(row) {
  if (!deckPeak.value) {
    return "0%";
  }
  const share = Math.abs(Number(row?.delta) || 0) / deckPeak.value;
  return `${Math.max(share > 0 ? 8 : 0, share * 100)}%`;
}

function deckCopies(row) {
  const qty = Number(row?.ownedQty) || 1;
  return qty > 1 ? qty : 0;
}

function tileRoute(row) {
  const card = tileCard(row);
  if (!card.setCode || !card.collectorNumber) {
    return null;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function openTile(row, event) {
  if (event.target instanceof Element && event.target.closest("button")) {
    return;
  }
  const to = tileRoute(row);
  if (to) {
    router.push(to);
  }
}

function openZoom(card) {
  if (!card?.imageUri) {
    return;
  }
  zoomCard.value = card;
}

function closeZoom() {
  zoomCard.value = null;
}

function menuCard(row) {
  const tile = tileCard(row);
  const finish = cardFinish(tile);
  const match = (props.sourceCards || []).find((card) => (
    String(card?.setCode || "").trim().toUpperCase() === tile.setCode
    && String(card?.collectorNumber || "").trim() === tile.collectorNumber
    && cardFinish(card) === finish
  ));
  return { ...(match || {}), ...row, ...tile };
}

async function openActions(event, row) {
  const rect = event.currentTarget.getBoundingClientRect();
  const card = menuCard(row);
  actionMenu.value = {
    open: true,
    x: rect.left,
    y: rect.bottom + 4,
    card,
  };
  if (card.cardmarketUrl || card.cardmarketUrlFoil || !card.setCode || !card.collectorNumber) {
    return;
  }
  try {
    const detail = await ignoreAborted(api.getCardDetail(card.setCode, card.collectorNumber, {
      finish: cardFinish(card),
    }));
    const current = actionMenu.value.card;
    if (
      !detail?.cardmarketUrl
      || !actionMenu.value.open
      || current?.setCode !== card.setCode
      || current?.collectorNumber !== card.collectorNumber
    ) {
      return;
    }
    actionMenu.value = {
      ...actionMenu.value,
      card: {
        ...card,
        cardmarketUrl: detail.cardmarketUrl,
      },
    };
  } catch {
    // Details, Scryfall, and the copy actions stay available without a Cardmarket link.
  }
}

function closeActions() {
  actionMenu.value = { ...actionMenu.value, open: false };
}

</script>

<template>
  <ol class="price-sync-movers-list is-tiles" :class="{ 'is-deck': variant === 'detail' }">
    <li
      v-for="(row, index) in rows"
      :key="row.id || row.label"
      :class="priceChangeTinted(row.delta, backgroundFloor) ? changeClass(row) : ''"
      :style="priceChangeStyle(row.delta, { floor: backgroundFloor })"
    >
      <div
        class="price-sync-mini-row"
        :class="{ 'is-link': Boolean(tileRoute(row)), 'is-deck': variant === 'detail' }"
        @click="openTile(row, $event)"
      >
        <span v-if="variant !== 'detail'" class="price-sync-mini-rank">{{ index + 1 }}</span>
        <span v-if="tileCard(row).imageUri" class="price-sync-mini-art-wrap">
          <button
            type="button"
            class="favorite-day-tile-zoom"
            :aria-label="`View larger image of ${tileCard(row).name || row.label}`"
            @click.prevent.stop="openZoom(tileCard(row))"
          >
            <img
              class="price-sync-mini-art"
              :src="scryfallSmallImageUri(tileCard(row).imageUri)"
              alt=""
              width="36"
              height="50"
              loading="lazy"
              decoding="async"
            >
          </button>
          <button
            type="button"
            class="favorite-day-tile-menu"
            :class="{ 'is-open': actionMenu.open && actionMenu.card?.id === row.id }"
            aria-label="Card actions"
            title="Card actions"
            @click.prevent.stop="openActions($event, row)"
          >
            <span aria-hidden="true">⋮</span>
          </button>
        </span>
        <span v-else class="price-sync-mini-art is-empty" aria-hidden="true"></span>
        <span v-if="variant === 'detail'" class="price-sync-deck-copy">
          <strong>{{ tileCard(row).name || row.label }}</strong>
          <span class="price-sync-deck-meta">
            <span v-if="tileCard(row).setCode" class="price-sync-deck-set">{{ tileCard(row).setCode }}</span>
            <span v-if="tileCard(row).collectorNumber">#{{ tileCard(row).collectorNumber }}</span>
            <span v-if="deckCopies(row)" class="price-sync-deck-qty">×{{ deckCopies(row) }}</span>
          </span>
          <span class="price-sync-deck-prices">
            <span class="was">{{ formatEuro(row.previous) }}</span>
            <span class="arrow" aria-hidden="true">→</span>
            <span class="now">{{ formatEuro(row.current) }}</span>
            <span v-if="deckCopies(row)" class="each">each</span>
          </span>
          <span class="price-sync-deck-bar" aria-hidden="true">
            <span :style="{ width: deckBarWidth(row) }"></span>
          </span>
        </span>
        <span v-else class="price-sync-mini-copy">
          <strong>{{ tileCard(row).name || row.label }}</strong>
          <small v-if="tileCard(row).collectorNumber">
            {{ tileCard(row).setCode }} #{{ tileCard(row).collectorNumber }}
          </small>
        </span>
        <strong
          v-if="variant === 'detail'"
          class="price-sync-deck-pill"
          :class="changeClass(row)"
        >{{ formatProfit(Number(row.delta) || 0) }}</strong>
        <strong v-else class="price-sync-movers-change" :class="changeClass(row)">
          <span class="price-sync-movers-range">
            {{ formatEuro(row.previous) }} → {{ formatEuro(row.current) }}
          </span>
          <span class="price-sync-movers-deltas">
            <span class="is-primary">{{ formatDelta(row) }}</span>
          </span>
        </strong>
      </div>
    </li>
  </ol>
  <CardPreviewDialog
    v-if="zoomCard"
    :image-uri="zoomCard.imageUri"
    :alt="zoomCard.name || zoomCard.label || 'Card'"
    :set-code="zoomCard.setCode"
    :collector-number="zoomCard.collectorNumber"
    :finish="zoomCard.finish"
    :seed="zoomCard"
    @close="closeZoom"
  />
  <CardContextMenu
    v-if="actionMenu.open"
    :open="true"
    :card="actionMenu.card"
    :x="actionMenu.x"
    :y="actionMenu.y"
    @close="closeActions"
  />
</template>
