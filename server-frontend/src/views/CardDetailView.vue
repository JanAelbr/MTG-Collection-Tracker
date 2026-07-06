<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache } from "../api";
import CardVariantGallery from "../components/CardVariantGallery.vue";
import CardOwnedQtyControl from "../components/CardOwnedQtyControl.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { isFinishDataOwned } from "../composables/cardContextMenu";
import { formatEuro, formatPriceChange, formatProfit } from "../utils/format";
import { priceStrategyDescription } from "../utils/priceStrategies";
import { FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, finishLabel, normalizeFinish } from "../utils/finishes";
import { collectionScopeToQuery } from "../utils/setScope";
import DeckCardQtyControl from "../components/DeckCardQtyControl.vue";

const route = useRoute();
const router = useRouter();

const card = ref(null);
const selectedFinish = ref(FINISH_NONFOIL);
const priceStrategy = ref("trend");
const purchaseDrafts = ref({});
const purchaseSaving = ref(null);
const finishSaving = ref(null);
const { loading, run } = useAsyncLoad();

const availableFinishes = computed(() =>
  Array.from(
    new Set(
      Object.entries(card.value?.finishes || {})
        .map(([key, item]) => normalizeFinish(item?.finish ?? key))
        .filter((finish) => [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].includes(finish)),
    ),
  ).sort((left, right) => left - right),
);

const finishRows = computed(() =>
  availableFinishes.value.map((finish) => ({
    finish,
    label: finishLabel(finish),
    data: card.value?.finishes?.[String(finish)] || null,
  })),
);

const showNonfoilGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.nonfoil != null),
);

const showFoilGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.foil != null),
);

const showEtchedGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.etched != null),
);

const showNeighborGallery = computed(
  () => (card.value?.setGallery?.cards?.length || 0) > 1,
);

const menuCard = computed(() => {
  if (!card.value) {
    return null;
  }
  return {
    ...card.value,
    finish: selectedFinish.value,
    hasNonfoil: availableFinishes.value.includes(FINISH_NONFOIL),
    hasFoil: availableFinishes.value.includes(FINISH_FOIL),
    hasEtched: availableFinishes.value.includes(FINISH_ETCHED),
  };
});

const showVariantGallery = computed(
  () => (card.value?.variantGallery?.cards?.length || 0) > 1,
);

const hasAnyOwned = computed(() =>
  finishRows.value.some((row) => isFinishDataOwned(row.data)),
);

const activeFinishRow = computed(() => ({
  finish: selectedFinish.value,
  label: finishLabel(selectedFinish.value),
  data: card.value?.finishes?.[String(selectedFinish.value)] || null,
}));

const collectionSetLink = computed(() => {
  if (!card.value?.setCode) {
    return null;
  }
  return {
    path: "/collection/all",
    query: collectionScopeToQuery(card.value.setCode, card.value.artStyle || ""),
  };
});

const defaultDeckId = computed(() =>
  typeof route.query.deck === "string" ? route.query.deck : "",
);
const activeDeckLabel = ref("");
const deckCardSlot = ref(null);
const imageZoomOpen = ref(false);

watch(
  defaultDeckId,
  async (deckId) => {
    if (!deckId) {
      activeDeckLabel.value = "";
      return;
    }
    try {
      const payload = await api.listDecks();
      const deck = (payload.decks || []).find((item) => String(item.id) === String(deckId));
      activeDeckLabel.value = deck?.label || deck?.name || "";
    } catch {
      activeDeckLabel.value = "";
    }
  },
  { immediate: true },
);

async function onDeckCardRemoved() {
  clearClientCache();
  deckCardSlot.value = null;
  await loadCard();
}

async function onDeckCardChanged() {
  clearClientCache();
  await loadCard();
}

function findDeckCardSlot(cards, setCode, collectorNumber, finish) {
  const matches = (cards || []).filter(
    (row) =>
      row.setCode === setCode &&
      String(row.collectorNumber) === String(collectorNumber) &&
      normalizeFinish(row.finish ?? row.foil ?? 0) === finish,
  );
  if (!matches.length) {
    return null;
  }
  return matches.find((row) => row.section === "main") || matches[0];
}

function isFinishOwnedElsewhere(finish) {
  return finishRows.value.some(
    (row) => row.finish !== finish && isFinishDataOwned(row.data),
  );
}

function finishChangeOptions(fromFinish) {
  return availableFinishes.value
    .filter((finish) => finish === fromFinish || !isFinishOwnedElsewhere(finish))
    .map((finish) => ({
      value: finish,
      label: finishLabel(finish),
    }));
}

async function changeOwnedFinish(fromFinish, event) {
  const toFinish = normalizeFinish(event.target.value);
  if (!card.value || fromFinish === toFinish) {
    return;
  }

  finishSaving.value = fromFinish;
  try {
    await api.changeOwnershipFinish({
      setCode: card.value.setCode,
      collectorNumber: card.value.collectorNumber,
      fromFinish,
      toFinish,
    });
    clearClientCache();
    if (selectedFinish.value === fromFinish) {
      selectedFinish.value = toFinish;
      await router.replace({
        params: {
          setCode: route.params.setCode,
          collectorNumber: route.params.collectorNumber,
        },
        query: toFinish === FINISH_NONFOIL ? {} : { finish: String(toFinish) },
      });
    }
    await loadCard();
  } catch {
    event.target.value = String(fromFinish);
  } finally {
    finishSaving.value = null;
  }
}

function formatGainLoss(value) {
  return formatProfit(value);
}

function closeImageZoom() {
  imageZoomOpen.value = false;
}

function onImageZoomKeydown(event) {
  if (event.key === "Escape") {
    closeImageZoom();
  }
}

watch(imageZoomOpen, (open) => {
  if (open) {
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onImageZoomKeydown);
    return;
  }
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onImageZoomKeydown);
});

function syncPurchaseDrafts() {
  const next = {};
  for (const finish of availableFinishes.value) {
    const purchaseValue = card.value?.finishes?.[String(finish)]?.purchaseValue;
    next[finish] = purchaseValue != null ? String(purchaseValue) : "";
  }
  purchaseDrafts.value = next;
}

function applySavedPurchasePrice(finish, purchaseValue) {
  const finishKey = String(finish);
  const finishData = card.value?.finishes?.[finishKey];
  if (!finishData || !card.value) {
    return;
  }
  const currentValue = finishData.currentValue;
  const profitLoss = currentValue != null ? currentValue - purchaseValue : null;
  card.value = {
    ...card.value,
    finishes: {
      ...card.value.finishes,
      [finishKey]: {
        ...finishData,
        purchaseValue,
        profitLoss,
      },
    },
  };
  syncPurchaseDrafts();
}

async function cancelPendingCardLoad() {
  await run(async () => {});
}

function parsePurchaseInput(raw) {
  if (raw === "" || raw == null) {
    return null;
  }
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) {
    return undefined;
  }
  return value;
}

async function savePurchasePrice(finish) {
  const finishData = card.value?.finishes?.[String(finish)];
  if (!card.value || !isFinishDataOwned(finishData)) {
    return;
  }

  const draft = purchaseDrafts.value[finish];
  const parsed = parsePurchaseInput(draft);
  if (parsed === undefined) {
    syncPurchaseDrafts();
    return;
  }
  if (parsed == null) {
    syncPurchaseDrafts();
    return;
  }

  const current = finishData?.purchaseValue;
  if (current != null && Math.abs(parsed - current) < 0.0001) {
    return;
  }
  if (current == null && parsed === 0) {
    return;
  }

  purchaseSaving.value = finish;
  try {
    await cancelPendingCardLoad();
    await api.updateOwnership({
      setCode: card.value.setCode,
      collectorNumber: card.value.collectorNumber,
      finish,
      owned: true,
      purchaseValue: parsed,
    });
    clearClientCache();
    applySavedPurchasePrice(finish, parsed);
  } catch {
    syncPurchaseDrafts();
  } finally {
    purchaseSaving.value = null;
  }
}

async function loadCard(options = {}) {
  await run(async (isCurrent) => {
    const finishQuery = route.query.finish == null
      ? undefined
      : normalizeFinish(route.query.finish);
    const nextCard = await api.getCardDetail(
      route.params.setCode,
      route.params.collectorNumber,
      { finish: finishQuery },
    );
    if (!isCurrent()) {
      return;
    }
    card.value = nextCard;
    selectedFinish.value = normalizeFinish(card.value.selectedFinish ?? FINISH_NONFOIL);
    priceStrategy.value = card.value.priceStrategy || "trend";
    deckCardSlot.value = null;
    if (defaultDeckId.value) {
      try {
        const browse = await api.getDeckBrowse(defaultDeckId.value);
        if (isCurrent()) {
          deckCardSlot.value = findDeckCardSlot(
            browse.cards,
            card.value.setCode,
            card.value.collectorNumber,
            selectedFinish.value,
          );
        }
      } catch {
        deckCardSlot.value = null;
      }
    }
    if (!options.preserveDrafts) {
      syncPurchaseDrafts();
    }
  });
}

async function onCardFinishChanged(toFinish) {
  const normalized = normalizeFinish(toFinish);
  if (selectedFinish.value === normalized) {
    await loadCard();
    return;
  }
  selectedFinish.value = normalized;
  await router.replace({
    params: {
      setCode: route.params.setCode,
      collectorNumber: route.params.collectorNumber,
    },
    query: normalized === FINISH_NONFOIL ? {} : { finish: String(normalized) },
  });
}

watch(
  () => [route.params.setCode, route.params.collectorNumber, route.query.finish],
  () => {
    loadCard();
  },
);

async function onOwnershipChanged() {
  if (purchaseSaving.value != null || !card.value) {
    return;
  }
  await loadCard({ preserveDrafts: true });
}

onMounted(loadCard);

onUnmounted(() => {
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onImageZoomKeydown);
});
</script>

<template>
  <div v-if="card" class="card-detail-page">
    <header class="card-detail-header-bar">
      <button type="button" class="card-detail-back" @click="router.back()">← Back</button>
    </header>

    <section class="card-detail-panel card-detail-main">
      <div class="card-detail-image-wrap">
        <button
          v-if="card.imageUri"
          type="button"
          class="card-detail-image-button"
          aria-label="View larger image"
          @click="imageZoomOpen = true"
        >
          <img
            :src="card.imageUri"
            :alt="card.name"
            class="card-detail-image"
          >
        </button>
        <div v-else class="card-detail-image card-detail-image-empty">No image</div>
      </div>

      <div class="card-detail-meta">
        <h1>{{ card.name }}</h1>
        <p class="card-detail-set">
          <RouterLink
            v-if="collectionSetLink"
            :to="collectionSetLink"
            class="card-detail-set-link"
          >
            {{ card.setLabel }}
          </RouterLink>
          <span v-else>{{ card.setLabel }}</span>
        </p>
        <p class="card-detail-subtitle">#{{ String(card.collectorNumber).padStart(3, "0") }}</p>
        <p v-if="card.artStyle" class="card-detail-art-style">{{ card.artStyle }}</p>

        <div class="card-detail-actions">
          <DeckCardQtyControl
            v-if="menuCard && defaultDeckId && deckCardSlot"
            :card="{ ...menuCard, ...deckCardSlot }"
            :deck-id="defaultDeckId"
            :deck-name="activeDeckLabel"
            @changed="onDeckCardChanged"
            @removed="onDeckCardRemoved"
          />

          <CardOwnedQtyControl
            v-if="menuCard"
            :card="menuCard"
            @ownership-changed="onOwnershipChanged"
          />

          <div class="card-detail-pricing-tile card-owned-qty-tile">
            <div class="card-owned-qty-tile-row card-owned-qty-tile-row-head">
              <span class="card-owned-qty-tile-label">Pricing</span>
              <span class="card-detail-pricing-finish">{{ activeFinishRow.label }}</span>
            </div>

            <div
              v-if="hasAnyOwned && isFinishDataOwned(activeFinishRow.data)"
              class="card-detail-pricing-stat"
            >
              <span class="card-detail-pricing-stat-label">Owned as</span>
              <span class="card-detail-pricing-stat-value">
                <select
                  v-if="finishChangeOptions(activeFinishRow.finish).length > 1"
                  class="card-detail-finish-select"
                  :value="activeFinishRow.finish"
                  :disabled="finishSaving === activeFinishRow.finish || loading"
                  @change="changeOwnedFinish(activeFinishRow.finish, $event)"
                >
                  <option
                    v-for="option in finishChangeOptions(activeFinishRow.finish)"
                    :key="`${activeFinishRow.finish}-${option.value}`"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
                <span v-else>{{ activeFinishRow.label }}</span>
              </span>
            </div>

            <div class="card-detail-pricing-stat">
              <span class="card-detail-pricing-stat-label">Current value</span>
              <span class="card-detail-pricing-stat-value">
                <a
                  v-if="card.cardmarketUrl"
                  :href="card.cardmarketUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="reports-market-link"
                >
                  {{ formatEuro(activeFinishRow.data?.currentValue) }}
                </a>
                <template v-else>{{ formatEuro(activeFinishRow.data?.currentValue) }}</template>
              </span>
            </div>

            <div class="card-detail-pricing-stat">
              <span class="card-detail-pricing-stat-label">Change</span>
              <span class="card-detail-pricing-stat-value">
                {{ formatPriceChange(activeFinishRow.data?.priceChange, activeFinishRow.data?.previousValue) }}
              </span>
            </div>

            <div class="card-detail-pricing-stat">
              <span class="card-detail-pricing-stat-label">Purchase</span>
              <span class="card-detail-pricing-stat-value">
                <label
                  v-if="isFinishDataOwned(activeFinishRow.data)"
                  class="card-detail-purchase-field"
                >
                  <span class="card-detail-purchase-currency">€</span>
                  <input
                    v-model="purchaseDrafts[activeFinishRow.finish]"
                    type="number"
                    min="0"
                    step="0.01"
                    inputmode="decimal"
                    class="card-detail-purchase-input"
                    :disabled="purchaseSaving === activeFinishRow.finish || loading"
                    placeholder="0.00"
                    @blur="savePurchasePrice(activeFinishRow.finish)"
                    @keydown.enter="$event.target.blur()"
                  />
                </label>
                <span v-else class="card-detail-pricing-empty">—</span>
              </span>
            </div>

            <div class="card-detail-pricing-stat">
              <span class="card-detail-pricing-stat-label">Gain / loss</span>
              <span
                class="card-detail-pricing-stat-value"
                :class="{
                  'reports-gain': activeFinishRow.data?.profitLoss != null && activeFinishRow.data.profitLoss >= 0,
                  'reports-loss': activeFinishRow.data?.profitLoss != null && activeFinishRow.data.profitLoss < 0,
                }"
              >
                {{ formatGainLoss(activeFinishRow.data?.profitLoss) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="card-detail-side">
        <div class="card-detail-guide-panel">
          <h2>Cardmarket prices (EUR)</h2>
          <div class="card-detail-guide-table-wrap">
            <table class="card-detail-guide-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th v-if="showNonfoilGuidePrices">Non-foil</th>
                  <th v-if="showFoilGuidePrices">Foil</th>
                  <th v-if="showEtchedGuidePrices">Etched</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in card.guidePriceMatrix.rows"
                  :key="row.strategyId"
                  :class="{ 'is-active-strategy': row.strategyId === priceStrategy }"
                >
                  <td>
                    <span
                      class="card-detail-strategy-label"
                      :title="priceStrategyDescription(row.strategyId)"
                    >
                      {{ row.label }}
                    </span>
                  </td>
                  <td v-if="showNonfoilGuidePrices">{{ formatEuro(row.nonfoil) }}</td>
                  <td v-if="showFoilGuidePrices">{{ formatEuro(row.foil) }}</td>
                  <td v-if="showEtchedGuidePrices">{{ formatEuro(row.etched) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <CardVariantGallery
      v-if="showVariantGallery"
      title="Alternative versions"
      :cards="card.variantGallery.cards"
      :current-index="card.variantGallery.currentIndex"
      :finish="selectedFinish"
      centered
    />

    <CardVariantGallery
      v-if="showNeighborGallery"
      title="Previous & next numbers"
      :cards="card.setGallery.cards"
      :current-index="card.setGallery.currentIndex"
      :finish="selectedFinish"
      show-name
      show-arrows
    />

    <Teleport to="body">
      <div
        v-if="imageZoomOpen && card.imageUri"
        class="card-image-zoom-backdrop"
        role="dialog"
        aria-modal="true"
        aria-label="Card image preview"
        @click.self="closeImageZoom"
      >
        <button
          type="button"
          class="card-image-zoom-close"
          aria-label="Close image preview"
          @click="closeImageZoom"
        >
          ×
        </button>
        <img
          :src="card.imageUri"
          :alt="card.name"
          class="card-image-zoom-image"
        >
      </div>
    </Teleport>
  </div>

  <div v-else class="card-detail-page">
    <LoadingIndicator label="Loading card…" />
  </div>
</template>
