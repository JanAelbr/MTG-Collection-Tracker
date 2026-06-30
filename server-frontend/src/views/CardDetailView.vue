<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api";
import CardVariantGallery from "../components/CardVariantGallery.vue";
import CardInteractiveImage from "../components/CardInteractiveImage.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { formatEuro, formatPriceChange, formatProfit } from "../utils/format";
import { FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, finishLabel, normalizeFinish } from "../utils/finishes";

const route = useRoute();
const router = useRouter();

const card = ref(null);
const selectedFinish = ref(FINISH_NONFOIL);
const priceStrategy = ref("trend");
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

const showEtchedGuidePrices = computed(() =>
  availableFinishes.value.includes(FINISH_ETCHED)
    || card.value?.guidePriceMatrix?.rows?.some((row) => row.etched != null),
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
  };
});

const showVariantGallery = computed(
  () => (card.value?.variantGallery?.cards?.length || 0) > 1,
);

function formatGainLoss(value) {
  return formatProfit(value);
}

function storageRoute(slug) {
  return { path: "/storage", query: { location: slug } };
}

async function loadCard() {
  await run(async () => {
    const finishQuery = route.query.finish == null
      ? undefined
      : normalizeFinish(route.query.finish);
    card.value = await api.getCardDetail(
      route.params.setCode,
      route.params.collectorNumber,
      { finish: finishQuery },
    );
    selectedFinish.value = normalizeFinish(card.value.selectedFinish ?? FINISH_NONFOIL);
    priceStrategy.value = card.value.priceStrategy || "trend";
  });
}

watch(
  () => [route.params.setCode, route.params.collectorNumber, route.query.finish],
  () => {
    loadCard();
  },
);

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
              {{ formatEuro(row.data?.purchaseValue) }}
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
          <table class="card-detail-guide-table">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Non-foil</th>
                <th>Foil</th>
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
                <td>{{ formatEuro(row.nonfoil) }}</td>
                <td>{{ formatEuro(row.foil) }}</td>
                <td v-if="showEtchedGuidePrices">{{ formatEuro(row.etched) }}</td>
              </tr>
            </tbody>
          </table>
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
