<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { buildDonutSegments } from "../utils/deckOverview";
import { powerCardRoute } from "../utils/deckPower";
import { MANA_COLORS } from "../utils/manaPips";
import CardFinishBadge from "./CardFinishBadge.vue";
import ManaSymbols from "./ManaSymbols.vue";

const props = defineProps({
  title: { type: String, required: true },
  rows: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  colors: { type: Array, default: () => [] },
  emptyLabel: { type: String, default: "No data yet." },
  unitLabel: { type: String, default: "cards" },
  cardsById: { type: Object, default: () => ({}) },
  deckId: { type: [String, Number], default: "" },
  interactive: { type: Boolean, default: false },
  /** Show Scryfall mana pips beside legend labels when row ids are WUBRG/C. */
  manaLegend: { type: Boolean, default: false },
});

const manaIdSet = new Set(MANA_COLORS);

function legendManaColors(rowId) {
  const id = String(rowId || "").toUpperCase();
  if (!manaIdSet.has(id)) {
    return null;
  }
  return id === "C" ? [] : [id];
}

const selectedId = ref(null);

const segments = computed(() => buildDonutSegments(props.rows, { radius: 48, stroke: 16 }));

const selectedRow = computed(() => (
  props.rows.find((row) => row.id === selectedId.value) || null
));

const selectedCards = computed(() => {
  if (!selectedId.value) {
    return [];
  }
  const cards = props.cardsById?.[selectedId.value];
  return Array.isArray(cards) ? cards : [];
});

const canSelect = computed(() => props.interactive && props.rows.some((row) => row.count > 0));

function colorFor(index) {
  if (!props.colors.length) {
    return "#94a3b8";
  }
  return props.colors[index % props.colors.length];
}

function formatShare(share) {
  return `${Math.round((Number(share) || 0) * 100)}%`;
}

function toggleRow(row) {
  if (!props.interactive || !row?.count) {
    return;
  }
  selectedId.value = selectedId.value === row.id ? null : row.id;
}

watch(
  () => props.rows,
  (rows) => {
    if (selectedId.value == null) {
      return;
    }
    const row = rows.find((item) => item.id === selectedId.value);
    if (!row?.count) {
      selectedId.value = null;
    }
  },
);
</script>

<template>
  <section class="deck-breakdown-chart" :class="{ 'is-interactive': canSelect }">
    <header class="deck-breakdown-chart-head">
      <h3 class="deck-breakdown-chart-title">{{ title }}</h3>
      <span v-if="canSelect" class="deck-breakdown-chart-hint">Click a slice</span>
    </header>

    <p v-if="!rows.length" class="deck-breakdown-chart-empty">{{ emptyLabel }}</p>

    <template v-else>
      <div class="deck-breakdown-chart-body">
        <div class="deck-breakdown-donut-wrap">
          <svg
            class="deck-breakdown-donut"
            viewBox="0 0 128 128"
            role="img"
            :aria-label="`${title} chart`"
          >
            <circle
              class="deck-breakdown-donut-track"
              cx="64"
              cy="64"
              r="48"
              fill="none"
              stroke-width="16"
            />
            <circle
              v-for="segment in segments"
              :key="segment.id"
              class="deck-breakdown-donut-segment"
              :class="{
                'is-clickable': interactive && segment.count > 0,
                'is-selected': selectedId === segment.id,
                'is-dimmed': selectedId && selectedId !== segment.id,
              }"
              cx="64"
              cy="64"
              :r="segment.radius"
              fill="none"
              :stroke="colorFor(segment.colorIndex)"
              :stroke-width="segment.stroke"
              :stroke-dasharray="segment.dasharray"
              :stroke-dashoffset="segment.dashoffset"
              stroke-linecap="butt"
              transform="rotate(-90 64 64)"
              :tabindex="interactive && segment.count > 0 ? 0 : undefined"
              :role="interactive && segment.count > 0 ? 'button' : undefined"
              :aria-pressed="interactive && segment.count > 0 ? selectedId === segment.id : undefined"
              :aria-label="interactive && segment.count > 0
                ? `View ${segment.count} ${segment.label}`
                : undefined"
              @click="toggleRow(segment)"
              @keydown.enter.prevent="toggleRow(segment)"
              @keydown.space.prevent="toggleRow(segment)"
            >
              <title>{{ segment.label }}: {{ segment.count }}</title>
            </circle>
          </svg>
          <div class="deck-breakdown-donut-center">
            <span class="deck-breakdown-donut-center-value">{{ total }}</span>
            <span v-if="unitLabel" class="deck-breakdown-donut-center-label">{{ unitLabel }}</span>
          </div>
        </div>

        <ul class="deck-breakdown-legend">
          <li
            v-for="(row, index) in rows"
            :key="row.id"
            class="deck-breakdown-legend-item"
            :class="{
              'is-clickable': interactive && row.count > 0,
              'is-selected': selectedId === row.id,
            }"
            :tabindex="interactive && row.count > 0 ? 0 : undefined"
            :role="interactive && row.count > 0 ? 'button' : undefined"
            :aria-pressed="interactive && row.count > 0 ? selectedId === row.id : undefined"
            @click="toggleRow(row)"
            @keydown.enter.prevent="toggleRow(row)"
            @keydown.space.prevent="toggleRow(row)"
          >
            <span class="deck-breakdown-legend-mark">
              <span
                class="deck-breakdown-swatch"
                :style="{ background: colorFor(row.colorIndex ?? index) }"
              />
              <ManaSymbols
                v-if="manaLegend && legendManaColors(row.id)"
                class="deck-breakdown-legend-mana"
                :colors="legendManaColors(row.id)"
                :size="14"
              />
            </span>
            <span class="deck-breakdown-legend-label">{{ row.label }}</span>
            <span class="deck-breakdown-legend-count">{{ row.count }}</span>
            <span class="deck-breakdown-legend-share">{{ formatShare(row.share) }}</span>
          </li>
        </ul>
      </div>

      <section v-if="selectedRow" class="deck-breakdown-selection">
        <header class="deck-breakdown-selection-header">
          <h4 class="deck-breakdown-selection-title">{{ selectedRow.label }}</h4>
          <span class="deck-breakdown-selection-count">
            {{ selectedCards.length || selectedRow.count }}
            {{ (selectedCards.length || selectedRow.count) === 1 ? "card" : "cards" }}
          </span>
        </header>

        <div v-if="selectedCards.length" class="deck-power-card-grid deck-breakdown-card-grid">
          <figure
            v-for="(card, index) in selectedCards"
            :key="`${selectedId}-${card.setCode}-${card.collectorNumber}-${card.finish}-${index}`"
            class="deck-power-card"
          >
            <div class="deck-power-card-image-wrap">
              <CardFinishBadge :card="card" variant="overlay" compact />
              <RouterLink
                v-if="powerCardRoute(card, deckId)"
                :to="powerCardRoute(card, deckId)"
                class="deck-power-card-image-link"
              >
                <img
                  v-if="card.imageUri"
                  :src="card.imageUri"
                  :alt="card.cardName"
                  class="deck-power-card-image"
                  loading="lazy"
                >
                <div v-else class="deck-power-card-placeholder">{{ card.cardName }}</div>
              </RouterLink>
              <template v-else>
                <img
                  v-if="card.imageUri"
                  :src="card.imageUri"
                  :alt="card.cardName"
                  class="deck-power-card-image"
                  loading="lazy"
                >
                <div v-else class="deck-power-card-placeholder">{{ card.cardName }}</div>
              </template>
            </div>

            <figcaption class="deck-power-card-caption">
              <RouterLink
                v-if="powerCardRoute(card, deckId)"
                :to="powerCardRoute(card, deckId)"
                class="deck-power-card-name"
              >
                {{ card.cardName }}
              </RouterLink>
              <span v-else class="deck-power-card-name is-plain">{{ card.cardName }}</span>
              <span v-if="card.qty > 1" class="deck-power-card-meta">×{{ card.qty }}</span>
            </figcaption>
          </figure>
        </div>

        <p v-else class="deck-breakdown-selection-empty">
          No cards in this group.
        </p>
      </section>
    </template>
  </section>
</template>
