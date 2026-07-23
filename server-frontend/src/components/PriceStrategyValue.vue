<script setup>
import { computed, onMounted } from "vue";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { formatEuro } from "../utils/format";
import { hasStrategyPrices, strategyPriceRows } from "../utils/priceStrategies";

const props = defineProps({
  card: { type: Object, default: null },
  value: { type: Number, default: null },
  tag: { type: String, default: "span" },
  /** When set, highlight/tooltip use this strategy instead of the global setting. */
  priceStrategy: { type: String, default: "" },
});

const { settings: pricingSettings } = usePricingSettings();

const activePriceStrategy = computed(
  () => props.priceStrategy || pricingSettings.value?.priceStrategy || "trend",
);

const priceStrategies = computed(
  () => pricingSettings.value?.priceStrategies || [],
);

const displayValue = computed(() => {
  if (props.value != null) {
    return props.value;
  }
  return props.card?.currentValue ?? null;
});

const showTooltip = computed(
  () => Boolean(props.card) && hasStrategyPrices(props.card) && priceStrategies.value.length > 0,
);

const strategyRows = computed(
  () => strategyPriceRows(props.card, priceStrategies.value, activePriceStrategy.value),
);

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
    <span class="price-strategy-value-main">{{ formatEuro(displayValue) }}</span>
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
    </span>
  </component>
</template>
