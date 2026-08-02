<script setup>
import { computed, onMounted } from "vue";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { formatEuro } from "../utils/format";
import {
  galleryPricePair,
  hasStrategyPrices,
  LOWEST_STRATEGY_ID,
  strategyPriceRows,
  TREND_STRATEGY_ID,
} from "../utils/priceStrategies";

const props = defineProps({
  card: { type: Object, default: null },
  value: { type: Number, default: null },
  tag: { type: String, default: "span" },
  /** @deprecated Unused — galleries always show lowest + trend. */
  priceStrategy: { type: String, default: "" },
});

const { settings: pricingSettings } = usePricingSettings();

const priceStrategies = computed(
  () => pricingSettings.value?.priceStrategies || [],
);

const purchaseValue = computed(() => {
  const raw = props.card?.purchaseValue ?? props.card?.purchase_value ?? null;
  if (raw == null || Number.isNaN(Number(raw)) || Number(raw) === 0) {
    return null;
  }
  return Number(raw);
});

const displayLabel = computed(() => {
  // Explicit override (e.g. line totals) stays a single price.
  if (props.value != null) {
    return formatEuro(props.value);
  }

  const { low, high } = galleryPricePair(props.card);
  let range = null;
  if (low != null && high != null) {
    range = `${formatEuro(low)} ~ ${formatEuro(high)}`;
  } else if (low != null) {
    range = formatEuro(low);
  } else if (props.card?.currentValue != null) {
    range = formatEuro(props.card.currentValue);
  } else {
    range = formatEuro(null);
  }

  if (purchaseValue.value != null) {
    return `${range} (${formatEuro(purchaseValue.value)})`;
  }
  return range;
});

const showTooltip = computed(
  () => Boolean(props.card) && hasStrategyPrices(props.card) && priceStrategies.value.length > 0,
);

const strategyRows = computed(() => {
  const { high } = galleryPricePair(props.card);
  const rows = strategyPriceRows(props.card, priceStrategies.value, LOWEST_STRATEGY_ID);
  if (high == null) {
    return rows;
  }
  // Highlight lowest and trend when both appear in the gallery pair.
  return rows.map((row) => {
    if (row.id === LOWEST_STRATEGY_ID || row.id === TREND_STRATEGY_ID) {
      return { ...row, isActive: true };
    }
    return { ...row, isActive: false };
  });
});

onMounted(() => {
  fetchPricingSettings();
});
</script>

<template>
  <component
    :is="tag"
    class="price-strategy-value"
    :class="{ 'has-strategy-tooltip': showTooltip }"
    tabindex="0"
  >
    <span class="price-strategy-value-main">{{ displayLabel }}</span>
    <span
      v-if="showTooltip"
      class="price-strategy-tooltip"
      role="tooltip"
    >
      <span
        v-for="row in strategyRows"
        :key="row.id"
        class="price-strategy-tooltip-row"
        :class="{ 'is-active-strategy': row.isActive }"
        :title="row.description"
      >
        <span class="price-strategy-tooltip-label">{{ row.label }}</span>
        <span class="price-strategy-tooltip-price">{{ formatEuro(row.value) }}</span>
      </span>
      <span
        v-if="purchaseValue != null"
        class="price-strategy-tooltip-row price-strategy-tooltip-purchase"
      >
        <span class="price-strategy-tooltip-label">Bought for</span>
        <span class="price-strategy-tooltip-price">{{ formatEuro(purchaseValue) }}</span>
      </span>
    </span>
  </component>
</template>
