<script setup>
import { computed } from "vue";

import SeparatorStyleSection from "./SeparatorStyleSection.vue";

const strategy = defineModel("strategy", { type: String, default: "trend" });
const minimumPrice = defineModel("minimumPrice", { type: [String, Number], default: "" });
const sort = defineModel("sort", { type: String, default: "collector" });
const ownedOnly = defineModel("ownedOnly", { type: Boolean, default: true });
const includeTimestamp = defineModel("includeTimestamp", { type: Boolean, default: false });
const showSetIcon = defineModel("showSetIcon", { type: Boolean, default: true });
const showFullSetName = defineModel("showFullSetName", { type: Boolean, default: true });
const fontScale = defineModel("fontScale", { type: Number, default: 100 });
const columnCount = defineModel("columnCount", { type: Number, default: 1 });

const props = defineProps({
  priceStrategies: { type: Array, default: () => [] },
  artStyleGroups: { type: Array, default: () => [] },
  selectedArtStyles: { type: Set, default: () => new Set() },
});

const emit = defineEmits(["toggle-art-style", "select-all-art-styles", "select-set-art-styles"]);

const artStyleCount = computed(() =>
  props.artStyleGroups.reduce((total, group) => total + (group.styles?.length || 0), 0),
);

const strategyLabel = computed(
  () => props.priceStrategies.find((item) => item.id === strategy.value)?.label || strategy.value,
);

const priceSummary = computed(() => {
  const bits = [ownedOnly.value ? "Owned" : "All", strategyLabel.value];
  if (minimumPrice.value !== "" && minimumPrice.value != null) {
    bits.push(`> €${minimumPrice.value}`);
  }
  return bits.join(" · ");
});

const layoutSummary = computed(() => {
  const bits = [
    sort.value === "price" ? "Price" : "Collector #",
  ];
  if (includeTimestamp.value) {
    bits.push("Date");
  }
  if (showSetIcon.value) {
    bits.push("Icon");
  }
  bits.push(showFullSetName.value ? "Full name" : "Set code");
  if (fontScale.value !== 100) {
    bits.push(`${fontScale.value}%`);
  }
  if (columnCount.value > 1) {
    bits.push(`${columnCount.value} cols`);
  }
  return bits.join(" · ");
});

const artStyleSummary = computed(() => {
  if (!artStyleCount.value) {
    return "None yet";
  }
  return `${props.selectedArtStyles.size} of ${artStyleCount.value}`;
});
</script>

<template>
  <section class="binder-style-panel" aria-label="Price list options">
    <div class="binder-style-panel-header">
      <h2 class="binder-style-panel-title">Print options</h2>
    </div>

    <SeparatorStyleSection title="Pricing" :summary="priceSummary" default-open>
      <div class="separators-mode" role="group" aria-label="Cards to print">
        <button
          type="button"
          class="separators-mode-btn"
          :class="{ 'is-active': ownedOnly }"
          @click="ownedOnly = true"
        >
          Owned
        </button>
        <button
          type="button"
          class="separators-mode-btn"
          :class="{ 'is-active': !ownedOnly }"
          @click="ownedOnly = false"
        >
          All
        </button>
      </div>
      <label class="print-prices-field">
        <span>Strategy</span>
        <select v-model="strategy">
          <option v-for="item in priceStrategies" :key="item.id" :value="item.id">
            {{ item.label }}
          </option>
        </select>
      </label>
      <label class="print-prices-field">
        <span>Minimum price (exclusive)</span>
        <input v-model="minimumPrice" type="number" min="0" step="0.01" placeholder="All prices" />
      </label>
    </SeparatorStyleSection>

    <SeparatorStyleSection title="Layout" :summary="layoutSummary">
      <label class="print-prices-field">
        <span>Sort rows by</span>
        <select v-model="sort">
          <option value="collector">Collector number</option>
          <option value="price">Price (high to low)</option>
        </select>
      </label>
      <label class="print-prices-choice">
        <input v-model="includeTimestamp" type="checkbox" />
        Include date
      </label>
      <label class="print-prices-choice">
        <input v-model="showSetIcon" type="checkbox" />
        Set icon in title
      </label>
      <label class="print-prices-choice">
        <input v-model="showFullSetName" type="checkbox" />
        Full set name in title
      </label>
      <label class="print-prices-field">
        <span>Text size ({{ fontScale }}%)</span>
        <input v-model.number="fontScale" type="range" min="60" max="100" step="5" />
      </label>
      <label class="print-prices-field">
        <span>Columns</span>
        <select v-model.number="columnCount">
          <option :value="1">1</option>
          <option :value="2">2</option>
          <option :value="3">3</option>
          <option :value="4">4</option>
        </select>
      </label>
    </SeparatorStyleSection>

    <SeparatorStyleSection title="Art styles" :summary="artStyleSummary">
      <p v-if="!artStyleGroups.length" class="print-prices-panel-muted">
        Select loaded sets to list art styles.
      </p>
      <template v-else>
        <button
          type="button"
          class="btn btn-secondary btn-small"
          @click="emit('select-all-art-styles')"
        >
          Select all
        </button>
        <div
          v-for="group in artStyleGroups"
          :key="group.setCode"
          class="print-prices-art-set"
        >
          <div class="print-prices-art-set-header">
            <span class="print-prices-art-set-name">{{ group.setName }}</span>
            <button
              type="button"
              class="btn btn-secondary btn-small"
              @click="emit('select-set-art-styles', group)"
            >
              All
            </button>
          </div>
          <label
            v-for="style in group.styles"
            :key="style.key"
            class="print-prices-choice"
          >
            <input
              type="checkbox"
              :checked="selectedArtStyles.has(style.key)"
              @change="emit('toggle-art-style', style.key)"
            />
            {{ style.artStyle }}
          </label>
        </div>
      </template>
    </SeparatorStyleSection>
  </section>
</template>
