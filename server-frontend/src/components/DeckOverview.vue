<script setup>
import { computed, ref, watch } from "vue";
import { api } from "../api";
import DeckBreakdownChart from "./DeckBreakdownChart.vue";
import DeckLandManaChart from "./DeckLandManaChart.vue";
import DeckManaCurveChart from "./DeckManaCurveChart.vue";
import ManaCost from "./ManaCost.vue";
import ManaSymbols from "./ManaSymbols.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import CardSetSymbol from "./CardSetSymbol.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import { cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import { buildManaCurveChartData } from "../utils/manaCurve";
import {
  buildColorPipBreakdown,
  buildManaSourceStack,
  filterCardsByPipColor,
  PIP_CHART_COLORS,
} from "../utils/manaPips";
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
import { commanderColorIdentity, splitCommanderCards } from "../utils/deckCards";
import { formatDeckOwned, formatDeckValueRange, formatEuro } from "../utils/format";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  stats: { type: Object, default: null },
  deckId: { type: String, default: "" },
  refreshKey: { type: [String, Number], default: "" },
  refreshingUnpriced: { type: Boolean, default: false },
  unpricedMessage: { type: String, default: "" },
  unpricedError: { type: String, default: "" },
});

const emit = defineEmits(["refresh-unpriced"]);

const powerPayload = ref(null);
const powerLoading = ref(false);
const powerError = ref("");

const commanderCards = computed(() => splitCommanderCards(props.cards).commanders);
const commanderIdentity = computed(() => commanderColorIdentity(commanderCards.value));
const typeBreakdown = computed(() => buildTypeBreakdown(props.cards));
const roleBreakdown = computed(() => buildRoleBreakdown(powerPayload.value?.counts || {}));
const pipBreakdown = computed(() => buildColorPipBreakdown(props.cards));
const manaSourceStack = computed(() => buildManaSourceStack(props.cards));
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
const pipCardsById = computed(() => {
  const groups = {};
  for (const row of pipBreakdown.value.rows) {
    groups[row.id] = filterCardsByPipColor(props.cards, row.id);
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
  if (pipBreakdown.value.total) {
    bits.push(`${pipBreakdown.value.total} color pips`);
  }
  return bits;
});

const deckSize = computed(() => props.stats?.deckSize || 0);
const ownedQty = computed(() => props.stats?.ownedQty || 0);
const missingQty = computed(() => props.stats?.missingQty || 0);

const completionPercent = computed(() => {
  if (props.stats?.ownedCoverage != null) {
    return Math.min(100, Math.max(0, props.stats.ownedCoverage));
  }
  if (!deckSize.value) {
    return 0;
  }
  return Math.min(100, (ownedQty.value / deckSize.value) * 100);
});

const completionLabel = computed(() => {
  const ownedText = formatDeckOwned(ownedQty.value, deckSize.value) || String(ownedQty.value);
  if (missingQty.value > 0) {
    return `${ownedText} owned · ${missingQty.value} missing`;
  }
  return `${ownedText} owned · complete`;
});

const secondaryMeta = computed(() => {
  const parts = [];
  if (props.stats?.purchasePrice != null) {
    parts.push(`Purchase ${formatEuro(props.stats.purchasePrice)}`);
  }
  if (props.stats?.trackedCoverage != null) {
    parts.push(`Priced ${props.stats.trackedCoverage}%`);
  }
  return parts.join(" · ");
});

const hasStatusTile = computed(() => Boolean(props.stats));

const unknownCards = computed(() => props.stats?.unknownCards || []);
const hasUnpricedTile = computed(() => (Number(props.stats?.unknownCount) || 0) > 0);
const unpricedCardCount = computed(() => {
  const qty = Number(props.stats?.unknownQty);
  if (Number.isFinite(qty) && qty > 0) {
    return qty;
  }
  return Number(props.stats?.unknownCount) || 0;
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

function unknownCardRoute(card) {
  const setCode = card.setCode || card.set_code || "";
  const collectorNumber = String(card.collectorNumber ?? card.collector_number ?? "");
  if (!setCode || !collectorNumber) {
    return null;
  }
  const query = cardRouteQuery(card.finish ?? card.foil ?? 0);
  if (props.deckId) {
    query.deck = props.deckId;
  }
  return {
    name: "card",
    params: { setCode, collectorNumber },
    query,
  };
}

function unknownCardName(card) {
  return card.cardName || card.card_name || "Unknown";
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

    <div class="deck-overview-top-row">
      <section
        v-if="commanderCards.length"
        class="deck-overview-panel deck-overview-commander"
        aria-label="Commander"
      >
        <header class="deck-overview-panel-head">
          <h3 class="deck-overview-panel-title">
            {{ commanderCards.length > 1 ? "Commanders" : "Commander" }}
          </h3>
          <ManaSymbols
            v-if="commanderIdentity?.length"
            class="deck-overview-commander-identity"
            :colors="commanderIdentity"
            :size="14"
          />
        </header>

        <div
          class="deck-overview-commander-list"
          :class="{ 'is-partner': commanderCards.length > 1 }"
        >
          <figure
            v-for="(card, index) in commanderCards"
            :key="`${card.setCode}-${card.collectorNumber}-${cardFinish(card)}-${index}`"
            class="deck-overview-commander-card"
          >
            <div class="deck-overview-commander-image-wrap">
              <RouterLink
                v-if="card.imageUri && cardRoute(card)"
                :to="cardRoute(card)"
                class="deck-overview-commander-image-link"
              >
                <img :src="card.imageUri" :alt="card.cardName" loading="lazy">
              </RouterLink>
              <img
                v-else-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.cardName"
                loading="lazy"
              >
              <div v-else class="deck-overview-commander-placeholder">No art</div>
            </div>
            <figcaption class="deck-overview-commander-caption">
              <span class="deck-overview-commander-name-row">
                <CardSetSymbol
                  v-if="card.setCode"
                  :set-code="card.setCode"
                  :family-root="card.familyRoot || ''"
                  :rarity="card.rarity || ''"
                />
                <ManaCost
                  class="deck-overview-commander-mana"
                  :mana-cost="card.manaCost || ''"
                  :size="12"
                />
                <RouterLink
                  v-if="cardRoute(card)"
                  :to="cardRoute(card)"
                  class="deck-overview-commander-name"
                  :title="card.cardName"
                >
                  {{ card.cardName }}
                </RouterLink>
                <span v-else class="deck-overview-commander-name is-plain" :title="card.cardName">
                  {{ card.cardName }}
                </span>
                <CardFinishBadge :card="card" compact />
              </span>
            </figcaption>
          </figure>
        </div>
      </section>

      <section
        v-if="hasStatusTile"
        class="deck-overview-panel deck-overview-status"
        aria-label="Deck completion"
      >
        <header class="deck-overview-panel-head">
          <h3 class="deck-overview-panel-title">Completion</h3>
          <span class="deck-overview-panel-meta">{{ Math.round(completionPercent) }}%</span>
        </header>

        <p class="deck-overview-status-value">
          {{ formatDeckValueRange(stats.ownedCurrent, stats.current) }}
        </p>

        <div class="deck-overview-status-completion">
          <div
            class="deck-overview-status-bar"
            role="progressbar"
            :aria-valuenow="Math.round(completionPercent)"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="`${Math.round(completionPercent)}% owned`"
          >
            <span
              class="deck-overview-status-fill"
              :class="{ 'is-complete': completionPercent >= 100 }"
              :style="{ width: `${completionPercent}%` }"
            />
          </div>
          <p class="deck-overview-status-meta">
            <strong>{{ Math.round(completionPercent) }}%</strong>
            <span>{{ completionLabel }}</span>
          </p>
          <p v-if="secondaryMeta" class="deck-overview-status-secondary">{{ secondaryMeta }}</p>
        </div>
      </section>

      <section
        v-if="hasUnpricedTile"
        class="deck-overview-panel deck-overview-unpriced"
        aria-label="Unpriced cards"
      >
        <header class="deck-overview-panel-head">
          <h3 class="deck-overview-panel-title">Unpriced</h3>
          <span class="deck-overview-panel-meta">{{ unpricedCardCount }}</span>
        </header>

        <p class="deck-overview-unpriced-intro">
          No current market price. Refresh set metadata, then sync prices if needed.
        </p>

        <button
          type="button"
          class="btn btn-secondary btn-small deck-overview-unpriced-refresh"
          :disabled="refreshingUnpriced"
          @click="emit('refresh-unpriced')"
        >
          {{ refreshingUnpriced ? "Refreshing…" : "Refresh set metadata" }}
        </button>

        <p v-if="unpricedMessage" class="deck-overview-unpriced-status">{{ unpricedMessage }}</p>
        <p v-if="unpricedError" class="deck-overview-unpriced-status is-error">{{ unpricedError }}</p>

        <ul class="deck-overview-unpriced-list">
          <li
            v-for="(card, index) in unknownCards"
            :key="`${card.set_code || card.setCode}-${card.collector_number || card.collectorNumber}-${index}`"
            class="deck-overview-unpriced-item"
          >
            <CollectionSetLink
              class="deck-overview-unpriced-set"
              :set-code="card.setCode || card.set_code || ''"
            />
            <span class="deck-overview-unpriced-num">
              {{ card.collectorNumber ?? card.collector_number ?? "—" }}
            </span>
            <RouterLink
              v-if="unknownCardRoute(card)"
              :to="unknownCardRoute(card)"
              class="deck-overview-unpriced-name"
              :title="unknownCardName(card)"
            >
              {{ unknownCardName(card) }}
            </RouterLink>
            <span v-else class="deck-overview-unpriced-name is-plain" :title="unknownCardName(card)">
              {{ unknownCardName(card) }}
            </span>
            <span class="deck-overview-unpriced-meta">
              ×{{ card.qty ?? 1 }}
              <template v-if="finishLabel(card.finish ?? card.foil ?? 0) !== 'Non-foil'">
                · {{ finishLabel(card.finish ?? card.foil ?? 0) }}
              </template>
            </span>
          </li>
        </ul>
      </section>

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
                <CardSetSymbol
                  v-if="card.setCode"
                  :set-code="card.setCode"
                  :family-root="card.familyRoot || ''"
                  :rarity="card.rarity || ''"
                />
                <ManaCost class="deck-overview-top-mana" :mana-cost="card.manaCost || ''" :size="12" />
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
                <CardFinishBadge :card="card" compact />
              </span>
              <PriceStrategyValue :card="card" class="deck-overview-top-value" />
            </figcaption>
          </figure>
        </div>
      </section>
    </div>

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

      <DeckBreakdownChart
        class="deck-overview-panel deck-overview-pips"
        title="Color pips"
        :rows="pipBreakdown.rows"
        :total="pipBreakdown.total"
        :colors="PIP_CHART_COLORS"
        :cards-by-id="pipCardsById"
        :deck-id="deckId"
        interactive
        mana-legend
        unit-label="pips"
        empty-label="No colored mana symbols in this deck yet."
      />

      <section class="deck-overview-panel deck-overview-land-mana">
        <header class="deck-overview-panel-head">
          <h3 class="deck-overview-panel-title">Mana sources</h3>
          <span v-if="manaSourceStack.hasData" class="deck-overview-panel-meta">
            {{ manaSourceStack.sourceCount }} sources
            <template v-if="manaSourceStack.anyColorCount">
              · {{ manaSourceStack.anyColorCount }} any-color
            </template>
          </span>
        </header>
        <DeckLandManaChart
          :comparison="manaSourceStack"
          :deck-id="deckId"
        />
      </section>

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
