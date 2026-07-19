<script setup>
import { computed, ref, watch } from "vue";
import { api } from "../api";
import DeckBreakdownChart from "./DeckBreakdownChart.vue";
import DeckManaCurveChart from "./DeckManaCurveChart.vue";
import ManaCost from "./ManaCost.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import { cardFinish, cardRouteQuery } from "../utils/finishes";
import { buildManaCurveChartData } from "../utils/manaCurve";
import {
  OVERVIEW_TOP_CARD_LIMIT,
  ROLE_CHART_COLORS,
  TYPE_CHART_COLORS,
  buildRoleBreakdown,
  buildTypeBreakdown,
  filterCardsByType,
  mainDeckCardsForOverview,
  overviewTopCards,
} from "../utils/deckOverview";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  deckId: { type: String, default: "" },
  refreshKey: { type: [String, Number], default: "" },
});

const powerPayload = ref(null);
const powerLoading = ref(false);
const powerError = ref("");

const typeBreakdown = computed(() => buildTypeBreakdown(props.cards));
const roleBreakdown = computed(() => buildRoleBreakdown(powerPayload.value?.counts || {}));
const topCards = computed(() => overviewTopCards(props.cards, OVERVIEW_TOP_CARD_LIMIT));
const typeCardsById = computed(() => {
  const groups = {};
  for (const row of typeBreakdown.value.rows) {
    groups[row.id] = filterCardsByType(props.cards, row.id);
  }
  return groups;
});
const roleCardsById = computed(() => {
  const categoryCards = powerPayload.value?.categoryCards || {};
  const groups = {};
  for (const row of roleBreakdown.value.rows) {
    groups[row.id] = Array.isArray(categoryCards[row.id]) ? categoryCards[row.id] : [];
  }
  return groups;
});
const curveCards = computed(() => {
  const fromPower = powerPayload.value?.categoryCards?.curve;
  if (Array.isArray(fromPower) && fromPower.length) {
    return fromPower;
  }
  return mainDeckCardsForOverview(props.cards).filter((card) => {
    const cardType = String(card.cardType || card.card_type || "").toLowerCase();
    if (cardType === "land" || card.isBasicLand || card.is_basic_land) {
      return false;
    }
    return Number(card.cmc) > 0;
  });
});
const curveMeta = computed(() => buildManaCurveChartData(curveCards.value));
const summaryBits = computed(() => {
  const bits = [];
  if (typeBreakdown.value.total) {
    bits.push(`${typeBreakdown.value.total} cards`);
  }
  if (curveMeta.value.averageCmc != null) {
    bits.push(`avg CMC ${curveMeta.value.averageCmc}`);
  }
  const lands = typeBreakdown.value.rows.find((row) => row.id === "land");
  if (lands?.count) {
    bits.push(`${lands.count} lands`);
  }
  return bits;
});

async function loadPower() {
  if (!props.deckId) {
    powerPayload.value = null;
    powerLoading.value = false;
    powerError.value = "";
    return;
  }
  powerLoading.value = true;
  powerError.value = "";
  try {
    powerPayload.value = await api.getDeckPower(props.deckId);
  } catch (err) {
    powerError.value = err?.message || "Could not load role breakdown.";
    powerPayload.value = null;
  } finally {
    powerLoading.value = false;
  }
}

watch(
  () => [props.deckId, props.refreshKey],
  loadPower,
  { immediate: true },
);

function cardRoute(card) {
  if (!card?.setCode || !card?.collectorNumber) {
    return null;
  }
  const query = cardRouteQuery(cardFinish(card));
  if (props.deckId) {
    query.deck = props.deckId;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query,
  };
}
</script>

<template>
  <div class="deck-overview">
    <header v-if="summaryBits.length" class="deck-overview-summary">
      <span
        v-for="bit in summaryBits"
        :key="bit"
        class="deck-overview-summary-chip"
      >
        {{ bit }}
      </span>
    </header>

    <section class="deck-overview-panel deck-overview-top">
      <header class="deck-overview-panel-head">
        <h3 class="deck-overview-panel-title">Top value</h3>
        <span class="deck-overview-panel-meta">{{ OVERVIEW_TOP_CARD_LIMIT }} highest</span>
      </header>

      <p v-if="!topCards.length" class="deck-overview-empty">
        No priced cards in this deck yet.
      </p>

      <div v-else class="deck-overview-top-grid">
        <figure
          v-for="(card, index) in topCards"
          :key="`${card.setCode}-${card.collectorNumber}-${cardFinish(card)}-${index}`"
          class="deck-overview-top-card"
        >
          <div class="deck-overview-top-image-wrap">
            <span class="deck-overview-top-rank">{{ index + 1 }}</span>
            <CardFinishBadge :card="card" variant="overlay" compact />
            <RouterLink
              v-if="cardRoute(card)"
              :to="cardRoute(card)"
              class="deck-overview-top-image-link"
            >
              <img :src="card.imageUri" :alt="card.cardName" loading="lazy">
            </RouterLink>
            <img v-else :src="card.imageUri" :alt="card.cardName" loading="lazy">
          </div>

          <figcaption class="deck-overview-top-caption">
            <span class="deck-overview-top-name-row">
              <ManaCost class="deck-overview-top-mana" :mana-cost="card.manaCost || ''" :size="10" />
              <RouterLink
                v-if="cardRoute(card)"
                :to="cardRoute(card)"
                class="deck-overview-top-name"
                :title="card.cardName"
              >
                {{ card.cardName }}
              </RouterLink>
              <span v-else class="deck-overview-top-name is-plain" :title="card.cardName">
                {{ card.cardName }}
              </span>
            </span>
            <PriceStrategyValue :card="card" class="deck-overview-top-value" />
          </figcaption>
        </figure>
      </div>
    </section>

    <div class="deck-overview-grid">
      <DeckBreakdownChart
        class="deck-overview-panel"
        title="Card types"
        :rows="typeBreakdown.rows"
        :total="typeBreakdown.total"
        :colors="TYPE_CHART_COLORS"
        :cards-by-id="typeCardsById"
        :deck-id="deckId"
        interactive
        empty-label="No cards in this deck yet."
      />

      <div class="deck-overview-panel deck-overview-roles">
        <DeckBreakdownChart
          v-if="!powerLoading && !powerError"
          title="Deck roles"
          :rows="roleBreakdown.rows"
          :total="roleBreakdown.total"
          :colors="ROLE_CHART_COLORS"
          :cards-by-id="roleCardsById"
          :deck-id="deckId"
          interactive
          unit-label="roles"
          empty-label="No ramp, draw, or interaction tags found yet."
        />
        <template v-else>
          <header class="deck-breakdown-chart-head">
            <h3 class="deck-breakdown-chart-title">Deck roles</h3>
          </header>
          <div v-if="powerLoading" class="deck-overview-roles-status">
            <LoadingIndicator label="Loading roles…" />
          </div>
          <p v-else class="deck-overview-roles-status is-error">{{ powerError }}</p>
        </template>
      </div>

      <section class="deck-overview-panel deck-overview-curve">
        <header class="deck-overview-panel-head">
          <h3 class="deck-overview-panel-title">Mana curve</h3>
          <span v-if="curveMeta.hasData" class="deck-overview-panel-meta">
            {{ curveMeta.total }} spells · avg {{ curveMeta.averageCmc }}
          </span>
        </header>
        <DeckManaCurveChart
          :cards="curveCards"
          :deck-id="deckId"
          :show-meta="false"
          empty-message="No mana-cost data for nonland spells yet."
        />
      </section>
    </div>
  </div>
</template>
