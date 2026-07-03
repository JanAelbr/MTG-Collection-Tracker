<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache } from "../api";
import CardVariantGallery from "../components/CardVariantGallery.vue";
import CardInteractiveImage from "../components/CardInteractiveImage.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { getOwnershipPatch, isFinishDataOwned } from "../composables/cardContextMenu";
import { formatEuro, formatPriceChange, formatProfit } from "../utils/format";
import { FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, finishLabel, hasFinish, normalizeFinish } from "../utils/finishes";

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

const pricingGridStyle = computed(() => ({
  "--finish-columns": String(Math.max(availableFinishes.value.length, 1)),
}));

const hasAnyLocations = computed(() =>
  finishRows.value.some((row) => row.data?.locations?.length),
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

function storageRoute(slug) {
  return { path: "/storage", query: { location: slug } };
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
  const finish = selectedFinish.value;
  const patch = getOwnershipPatch({ ...card.value, finish });
  if (!patch) {
    return;
  }
  const finishKey = String(finish);
  const existing = card.value.finishes?.[finishKey];
  if (!existing) {
    return;
  }
  const owned = patch.owned;
  const purchaseValue = owned ? (existing.purchaseValue ?? 0) : null;
  const currentValue = existing.currentValue;
  const profitLoss = purchaseValue != null && currentValue != null
    ? currentValue - purchaseValue
    : null;
  card.value = {
    ...card.value,
    finishes: {
      ...card.value.finishes,
      [finishKey]: {
        ...existing,
        owned,
        purchaseValue,
        profitLoss,
      },
    },
  };
  syncPurchaseDrafts();
}

onMounted(loadCard);
</script>

<template>
  <div v-if="card" class="card-detail-page">
    <header class="card-detail-header-bar">
      <button type="button" class="card-detail-back" @click="router.back()">← Back</button>
    </header>

    <section class="card-detail-panel card-detail-main">
      <div class="card-detail-image-wrap">
        <CardInteractiveImage
          v-if="card.imageUri"
          :src="card.imageUri"
          :alt="card.name"
          :card="menuCard"
          img-class="card-detail-image"
          @finish-changed="onCardFinishChanged"
          @ownership-changed="onOwnershipChanged"
        />
        <div v-else class="card-detail-image card-detail-image-empty">No image</div>
      </div>

      <div class="card-detail-meta">
        <h1>{{ card.name }}</h1>
        <p class="card-detail-set">{{ card.setLabel }}</p>
        <p class="card-detail-subtitle">#{{ String(card.collectorNumber).padStart(3, "0") }}</p>
        <p v-if="card.artStyle" class="card-detail-art-style">{{ card.artStyle }}</p>

        <div v-if="hasAnyLocations" class="card-detail-locations">
          <span class="card-detail-locations-label">Stored in</span>
          <div
            v-for="row in finishRows"
            :key="`locations-${row.finish}`"
            class="card-detail-location-group"
          >
            <template v-if="row.data?.locations?.length">
              <span class="card-detail-location-finish">{{ row.label }}</span>
              <RouterLink
                v-for="location in row.data.locations"
                :key="`${row.finish}-${location.slug}`"
                :to="storageRoute(location.slug)"
                class="card-detail-location-link"
              >
                {{ location.label }}<span v-if="location.count > 1"> ×{{ location.count }}</span>
              </RouterLink>
            </template>
          </div>
        </div>

        <div class="card-detail-pricing-grid" :style="pricingGridStyle">
          <div class="card-detail-pricing-row card-detail-pricing-header">
            <span class="card-detail-pricing-label"></span>
            <span
              v-for="row in finishRows"
              :key="`header-${row.finish}`"
              class="card-detail-pricing-value"
            >
              {{ row.label }}
            </span>
          </div>
          <div v-if="hasAnyOwned" class="card-detail-pricing-row">
            <span class="card-detail-pricing-label">Owned as</span>
            <span
              v-for="row in finishRows"
              :key="`owned-finish-${row.finish}`"
              class="card-detail-pricing-value"
            >
              <select
                v-if="isFinishDataOwned(row.data) && finishChangeOptions(row.finish).length > 1"
                class="card-detail-finish-select"
                :value="row.finish"
                :disabled="finishSaving === row.finish || loading"
                @change="changeOwnedFinish(row.finish, $event)"
              >
                <option
                  v-for="option in finishChangeOptions(row.finish)"
                  :key="`${row.finish}-${option.value}`"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
              <span v-else-if="isFinishDataOwned(row.data)">{{ row.label }}</span>
              <span v-else class="card-detail-pricing-empty">—</span>
            </span>
          </div>
          <div class="card-detail-pricing-row">
            <span class="card-detail-pricing-label">Current value</span>
            <span
              v-for="row in finishRows"
              :key="`value-${row.finish}`"
              class="card-detail-pricing-value"
            >
              <a
                v-if="card.cardmarketUrl"
                :href="card.cardmarketUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="reports-market-link"
              >
                {{ formatEuro(row.data?.currentValue) }}
              </a>
              <template v-else>{{ formatEuro(row.data?.currentValue) }}</template>
            </span>
          </div>
          <div class="card-detail-pricing-row">
            <span class="card-detail-pricing-label">Change</span>
            <span
              v-for="row in finishRows"
              :key="`change-${row.finish}`"
              class="card-detail-pricing-value"
            >
              {{ formatPriceChange(row.data?.priceChange, row.data?.previousValue) }}
            </span>
          </div>
          <div class="card-detail-pricing-row">
            <span class="card-detail-pricing-label">Purchase</span>
            <span
              v-for="row in finishRows"
              :key="`purchase-${row.finish}`"
              class="card-detail-pricing-value"
            >
              <label
                v-if="isFinishDataOwned(row.data)"
                class="card-detail-purchase-field"
              >
                <span class="card-detail-purchase-currency">€</span>
                <input
                  v-model="purchaseDrafts[row.finish]"
                  type="number"
                  min="0"
                  step="0.01"
                  inputmode="decimal"
                  class="card-detail-purchase-input"
                  :disabled="purchaseSaving === row.finish || loading"
                  placeholder="0.00"
                  @blur="savePurchasePrice(row.finish)"
                  @keydown.enter="$event.target.blur()"
                />
              </label>
              <span v-else class="card-detail-pricing-empty">—</span>
            </span>
          </div>
          <div class="card-detail-pricing-row">
            <span class="card-detail-pricing-label">Gain / loss</span>
            <span
              v-for="row in finishRows"
              :key="`gain-${row.finish}`"
              class="card-detail-pricing-value"
              :class="{
                'reports-gain': row.data?.profitLoss != null && row.data.profitLoss >= 0,
                'reports-loss': row.data?.profitLoss != null && row.data.profitLoss < 0,
              }"
            >
              {{ formatGainLoss(row.data?.profitLoss) }}
            </span>
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
                  <td>{{ row.label }}</td>
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
  </div>

  <div v-else class="card-detail-page">
    <LoadingIndicator label="Loading card…" />
  </div>
</template>
