<script setup>
import { computed, ref, watch } from "vue";

import { formatEuro, formatProfit } from "../utils/format";
import {
  HISTORY_SCALE_ABSOLUTE,
  HISTORY_SCALE_RELATIVE,
} from "../utils/breakdownHistory";
import { normalizePriceSyncMovers } from "../composables/startupPriceSync";
import {
  aggregateArtStyleMovers,
  cardsForArtStyle,
  collectPriceSyncCards,
  rankMoverRows,
} from "../utils/priceSyncMovers";

const props = defineProps({
  open: { type: Boolean, default: false },
  movers: { type: Object, default: () => ({}) },
  cards: { type: Array, default: () => [] },
  filter: { type: Object, default: null },
});

const emit = defineEmits(["close"]);

const scale = ref(HISTORY_SCALE_ABSOLUTE);
const styleFilter = ref(null);

watch(
  () => [props.open, props.filter],
  () => {
    if (props.open) {
      styleFilter.value = props.filter || null;
    }
  },
  { immediate: true },
);

const allCards = computed(() => collectPriceSyncCards({
  cards: props.cards,
  movers: props.movers,
}));
const hasArtStyles = computed(() => (
  allCards.value.some((row) => String(row.artStyle || "").trim())
));
const showingStyles = computed(() => hasArtStyles.value && !styleFilter.value);
const activeRows = computed(() => {
  if (showingStyles.value) {
    return aggregateArtStyleMovers(allCards.value);
  }
  if (styleFilter.value) {
    return cardsForArtStyle(allCards.value, styleFilter.value);
  }
  const fallback = scale.value === HISTORY_SCALE_RELATIVE
    ? normalizePriceSyncMovers(props.movers).relative
    : normalizePriceSyncMovers(props.movers).absolute;
  return [...(fallback.risers || []), ...(fallback.fallers || [])];
});
const ranked = computed(() => rankMoverRows(activeRows.value, {
  scale: scale.value,
  limit: 25,
}));
const risers = computed(() => ranked.value.risers);
const fallers = computed(() => ranked.value.fallers);
const title = computed(() => {
  if (styleFilter.value) {
    const name = styleFilter.value.artStyle || styleFilter.value.label || "Art style";
    const setCode = styleFilter.value.setCode;
    return setCode ? `${name} · ${setCode}` : name;
  }
  return showingStyles.value ? "Price sync art styles" : "Price sync movers";
});
const intro = computed(() => {
  const scaleLabel = scale.value === HISTORY_SCALE_RELATIVE
    ? "percent change"
    : "euro change";
  if (styleFilter.value) {
    return `Card price changes for this art style, ranked by ${scaleLabel}. Moves under €1 are omitted.`;
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
          <h3 id="price-sync-movers-title">{{ title }}</h3>
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
        <div class="price-sync-movers-columns">
          <section class="price-sync-movers-column">
            <h4>Risers</h4>
            <ol v-if="risers.length" class="price-sync-movers-list">
              <li v-for="row in risers" :key="row.id || row.label">
                <button
                  v-if="showingStyles"
                  type="button"
                  class="price-sync-movers-item"
                  @click="openStyle(row)"
                >
                  <span class="price-sync-movers-name">{{ row.label }}</span>
                  <span class="price-sync-movers-meta">
                    {{ row.setCode }} · {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                  </span>
                  <strong class="price-sync-movers-change is-up">
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_ABSOLUTE }">
                      {{ formatDelta(row) }}
                    </span>
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_RELATIVE }">
                      {{ formatPercent(row) }}
                    </span>
                  </strong>
                </button>
                <div v-else class="price-sync-movers-item">
                  <span class="price-sync-movers-name">{{ row.label }}</span>
                  <span class="price-sync-movers-meta">
                    {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                  </span>
                  <strong class="price-sync-movers-change is-up">
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_ABSOLUTE }">
                      {{ formatDelta(row) }}
                    </span>
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_RELATIVE }">
                      {{ formatPercent(row) }}
                    </span>
                  </strong>
                </div>
              </li>
            </ol>
            <p v-else class="price-sync-movers-empty">No risers this sync.</p>
          </section>
          <section class="price-sync-movers-column">
            <h4>Fallers</h4>
            <ol v-if="fallers.length" class="price-sync-movers-list">
              <li v-for="row in fallers" :key="row.id || row.label">
                <button
                  v-if="showingStyles"
                  type="button"
                  class="price-sync-movers-item"
                  @click="openStyle(row)"
                >
                  <span class="price-sync-movers-name">{{ row.label }}</span>
                  <span class="price-sync-movers-meta">
                    {{ row.setCode }} · {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                  </span>
                  <strong class="price-sync-movers-change is-down">
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_ABSOLUTE }">
                      {{ formatDelta(row) }}
                    </span>
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_RELATIVE }">
                      {{ formatPercent(row) }}
                    </span>
                  </strong>
                </button>
                <div v-else class="price-sync-movers-item">
                  <span class="price-sync-movers-name">{{ row.label }}</span>
                  <span class="price-sync-movers-meta">
                    {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                  </span>
                  <strong class="price-sync-movers-change is-down">
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_ABSOLUTE }">
                      {{ formatDelta(row) }}
                    </span>
                    <span :class="{ 'is-primary': scale === HISTORY_SCALE_RELATIVE }">
                      {{ formatPercent(row) }}
                    </span>
                  </strong>
                </div>
              </li>
            </ol>
            <p v-else class="price-sync-movers-empty">No fallers this sync.</p>
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
