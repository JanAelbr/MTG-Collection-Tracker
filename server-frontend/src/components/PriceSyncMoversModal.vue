<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { api, ignoreAborted } from "../api";
import CardFinishBadge from "./CardFinishBadge.vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import { formatEuro, formatProfit, setDisplayName } from "../utils/format";
import {
  HISTORY_SCALE_ABSOLUTE,
  HISTORY_SCALE_RELATIVE,
} from "../utils/breakdownHistory";
import { cardFinish, cardRouteQuery } from "../utils/finishes";
import {
  cardsForArtStyle,
  collectPriceSyncCards,
  collectPriceSyncStyleRows,
  moverRowToTileCard,
  rankMoverRows,
} from "../utils/priceSyncMovers";
import { applySetGalleryIconFallback, resolveSetIconUri } from "../utils/scryfall";

const props = defineProps({
  open: { type: Boolean, default: false },
  movers: { type: Object, default: () => ({}) },
  cards: { type: Array, default: () => [] },
  filter: { type: Object, default: null },
});

const emit = defineEmits(["close"]);

const scale = ref(HISTORY_SCALE_ABSOLUTE);
const styleFilter = ref(null);
const setsByCode = ref(new Map());

watch(
  () => [props.open, props.filter],
  () => {
    if (props.open) {
      styleFilter.value = props.filter || null;
      loadSetCatalog();
    }
  },
  { immediate: true },
);

async function loadSetCatalog() {
  const payload = await ignoreAborted(api.getReportsMeta());
  if (!payload) {
    return;
  }
  const next = new Map();
  for (const set of payload.sets || []) {
    const code = String(set.setCode || "").trim().toUpperCase();
    if (code && code !== "ALL") {
      next.set(code, set);
    }
  }
  setsByCode.value = next;
}

function setMeta(rowOrCode) {
  const code = String(rowOrCode?.setCode || rowOrCode || "").trim().toUpperCase();
  if (!code) {
    return null;
  }
  return setsByCode.value.get(code) || { setCode: code };
}

function setName(rowOrCode) {
  const set = setMeta(rowOrCode);
  return setDisplayName(set) || String(set?.setCode || "").toUpperCase();
}

function setIcon(rowOrCode) {
  const set = setMeta(rowOrCode);
  return set ? (set.iconUri || resolveSetIconUri(set)) : "";
}

function onSetIconError(event, rowOrCode) {
  if (!applySetGalleryIconFallback(event.target, setMeta(rowOrCode))) {
    event.target.style.display = "none";
  }
}

const storedCards = computed(() => collectPriceSyncCards({
  cards: props.cards,
  movers: props.movers,
}));
const styleRows = computed(() => collectPriceSyncStyleRows({
  cards: props.cards,
  movers: props.movers,
}));
const hasArtStyles = computed(() => styleRows.value.length > 0);
const showingStyles = computed(() => hasArtStyles.value && !styleFilter.value);
const activeRows = computed(() => {
  if (showingStyles.value) {
    return styleRows.value;
  }
  if (styleFilter.value) {
    return cardsForArtStyle(storedCards.value, styleFilter.value);
  }
  return storedCards.value;
});
const showingCardTiles = computed(() => Boolean(styleFilter.value));
const ranked = computed(() => rankMoverRows(activeRows.value, {
  scale: scale.value,
  limit: 25,
}));
const risers = computed(() => ranked.value.risers);
const fallers = computed(() => ranked.value.fallers);
const moverColumns = computed(() => {
  const columns = [
    { id: "up", title: "Risers", rows: risers.value, empty: "No risers this sync." },
    { id: "down", title: "Fallers", rows: fallers.value, empty: "No fallers this sync." },
  ];
  const filled = columns.filter((column) => column.rows.length);
  return filled.length === 1 ? filled : columns;
});
const singleMoverColumn = computed(() => moverColumns.value.length === 1);
const title = computed(() => {
  if (styleFilter.value) {
    return styleFilter.value.artStyle || styleFilter.value.label || "Art style";
  }
  return showingStyles.value ? "Price sync art styles" : "Price sync movers";
});
const titleSet = computed(() => (styleFilter.value ? setMeta(styleFilter.value) : null));
const intro = computed(() => {
  const scaleLabel = scale.value === HISTORY_SCALE_RELATIVE
    ? "percent change"
    : "euro change";
  if (styleFilter.value) {
    return `Card changes from the last price update for this art style, ranked by ${scaleLabel}. Moves under €1 are omitted.`;
  }
  if (showingStyles.value) {
    return `Top 25 art styles by ${scaleLabel}. Click a style to see its card changes. Moves under €1 are omitted.`;
  }
  return `Top 25 risers and fallers by ${scaleLabel}. Moves under €1 are omitted.`;
});

function formatPercent(row) {
  const percent = Number(row?.percent);
  if (!Number.isFinite(percent)) {
    return "";
  }
  const formatted = `${Math.abs(percent).toFixed(1)}%`;
  if (percent > 0) {
    return `+${formatted}`;
  }
  if (percent < 0) {
    return `−${formatted}`;
  }
  return "0.0%";
}

function formatDelta(row) {
  return formatProfit((Number(row?.current) || 0) - (Number(row?.previous) || 0));
}

function formatPrice(value) {
  return formatEuro(value);
}

function rowLabel(row) {
  if (showingStyles.value) {
    return row.artStyle || row.label;
  }
  return row.label;
}

function rowMeta(row) {
  if (showingStyles.value || !row.collectorNumber) {
    return "";
  }
  return `#${row.collectorNumber}`;
}

function tileCard(row) {
  return moverRowToTileCard(row);
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

function openStyle(row) {
  if (!showingStyles.value) {
    return;
  }
  styleFilter.value = {
    setCode: row.setCode,
    artStyle: row.artStyle,
    label: row.label,
  };
}

function clearStyleFilter() {
  styleFilter.value = null;
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop price-sync-movers-backdrop"
      role="presentation"
      @click.self="emit('close')"
    >
      <div
        class="modal-card price-sync-movers-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="price-sync-movers-title"
        @keydown.esc.stop="emit('close')"
      >
        <div class="price-sync-movers-header">
          <h3 id="price-sync-movers-title">
            <img
              v-if="titleSet && setIcon(titleSet)"
              :src="setIcon(titleSet)"
              alt=""
              class="price-sync-movers-set-icon"
              :title="setName(titleSet)"
              :aria-label="setName(titleSet)"
              @error="onSetIconError($event, titleSet)"
            >
            <span>{{ title }}</span>
          </h3>
          <div class="button-group" role="group" aria-label="Change scale">
            <button
              type="button"
              class="filter-button"
              :class="{ active: scale === HISTORY_SCALE_ABSOLUTE }"
              :aria-pressed="scale === HISTORY_SCALE_ABSOLUTE"
              @click="scale = HISTORY_SCALE_ABSOLUTE"
            >
              Absolute
            </button>
            <button
              type="button"
              class="filter-button"
              :class="{ active: scale === HISTORY_SCALE_RELATIVE }"
              :aria-pressed="scale === HISTORY_SCALE_RELATIVE"
              @click="scale = HISTORY_SCALE_RELATIVE"
            >
              Relative
            </button>
          </div>
        </div>
        <p class="price-sync-movers-intro">{{ intro }}</p>
        <div
          class="price-sync-movers-columns"
          :class="{ 'is-single': singleMoverColumn }"
        >
          <section
            v-for="column in moverColumns"
            :key="column.id"
            class="price-sync-movers-column"
          >
            <h4>{{ column.title }}</h4>
            <ol
              v-if="column.rows.length"
              class="price-sync-movers-list"
              :class="{ 'is-tiles': showingCardTiles }"
            >
              <li v-for="row in column.rows" :key="row.id || row.label">
                <figure
                  v-if="showingCardTiles"
                  class="price-sync-mover-tile"
                >
                  <div class="price-sync-mover-tile-image">
                    <CardInteractiveImage
                      v-if="tileCard(row).imageUri"
                      :src="tileCard(row).imageUri"
                      :alt="tileCard(row).name"
                      :card="tileCard(row)"
                      img-class="price-sync-mover-tile-art"
                      :show-details="false"
                      :show-copy-controls="false"
                    />
                    <div v-else class="price-sync-mover-tile-placeholder">
                      {{ tileCard(row).name || rowLabel(row) }}
                    </div>
                    <CardFinishBadge
                      :card="tileCard(row)"
                      variant="overlay"
                      compact
                    />
                  </div>
                  <figcaption class="price-sync-mover-tile-caption">
                    <RouterLink
                      v-if="tileRoute(row)"
                      :to="tileRoute(row)"
                      class="price-sync-mover-tile-name"
                      :title="tileCard(row).name || rowLabel(row)"
                    >
                      {{ tileCard(row).name || rowLabel(row) }}
                    </RouterLink>
                    <span
                      v-else
                      class="price-sync-mover-tile-name"
                      :title="tileCard(row).name || rowLabel(row)"
                    >
                      {{ tileCard(row).name || rowLabel(row) }}
                    </span>
                    <strong
                      class="price-sync-movers-change"
                      :class="column.id === 'up' ? 'is-up' : 'is-down'"
                    >
                      <span class="price-sync-movers-range">
                        {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                      </span>
                      <span class="price-sync-movers-deltas">
                        <span :class="{ 'is-primary': scale === HISTORY_SCALE_ABSOLUTE }">
                          {{ formatDelta(row) }}
                        </span>
                        <span :class="{ 'is-primary': scale === HISTORY_SCALE_RELATIVE }">
                          {{ formatPercent(row) }}
                        </span>
                      </span>
                    </strong>
                  </figcaption>
                </figure>
                <component
                  v-else
                  :is="showingStyles ? 'button' : 'div'"
                  class="price-sync-movers-item"
                  :class="{ 'has-set-icon': showingStyles }"
                  v-bind="showingStyles ? { type: 'button' } : {}"
                  @click="showingStyles ? openStyle(row) : undefined"
                >
                  <img
                    v-if="showingStyles && setIcon(row)"
                    :src="setIcon(row)"
                    alt=""
                    class="price-sync-movers-set-icon"
                    :title="setName(row)"
                    :aria-label="setName(row)"
                    @error="onSetIconError($event, row)"
                  >
                  <span class="price-sync-movers-copy">
                    <span class="price-sync-movers-name" :title="rowLabel(row)">{{ rowLabel(row) }}</span>
                    <span v-if="rowMeta(row)" class="price-sync-movers-meta">{{ rowMeta(row) }}</span>
                  </span>
                  <strong
                    class="price-sync-movers-change"
                    :class="column.id === 'up' ? 'is-up' : 'is-down'"
                  >
                    <span class="price-sync-movers-range">
                      {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                    </span>
                    <span class="price-sync-movers-deltas">
                      <span :class="{ 'is-primary': scale === HISTORY_SCALE_ABSOLUTE }">
                        {{ formatDelta(row) }}
                      </span>
                      <span :class="{ 'is-primary': scale === HISTORY_SCALE_RELATIVE }">
                        {{ formatPercent(row) }}
                      </span>
                    </span>
                  </strong>
                </component>
              </li>
            </ol>
            <p v-else class="price-sync-movers-empty">{{ column.empty }}</p>
          </section>
        </div>
        <div class="modal-actions">
          <button
            v-if="styleFilter"
            type="button"
            class="btn btn-secondary"
            @click="clearStyleFilter"
          >
            All art styles
          </button>
          <button type="button" class="btn btn-primary" @click="emit('close')">
            Close
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
