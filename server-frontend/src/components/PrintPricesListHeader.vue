<script setup>
import { computed } from "vue";

import { formatEuro } from "../utils/format";

const props = defineProps({
  group: { type: Object, required: true },
  showSetIcon: { type: Boolean, default: true },
  showFullSetName: { type: Boolean, default: true },
  includeTimestamp: { type: Boolean, default: false },
  generatedAt: { type: Date, default: null },
  onIconError: { type: Function, default: null },
  strategyLabel: { type: String, default: "" },
  minimumPrice: { type: [String, Number], default: "" },
});

function titleText(group, showFullSetName) {
  if (showFullSetName) {
    return group.setName || group.setCode;
  }
  return group.setCode;
}

const hasMinimum = computed(() => {
  const value = Number(props.minimumPrice);
  return props.minimumPrice !== "" && props.minimumPrice != null && Number.isFinite(value);
});

const metaLine = computed(() => {
  const bits = [props.group.artStyle].filter(Boolean);
  if (props.strategyLabel) {
    bits.push(props.strategyLabel);
  }
  if (hasMinimum.value) {
    bits.push(`min > ${formatEuro(Number(props.minimumPrice))}`);
  }
  return bits.join(" · ");
});
</script>

<template>
  <header class="print-prices-list-header">
    <h2 class="print-prices-list-title">
      <img
        v-if="showSetIcon && group.setIconUri"
        class="print-prices-list-title-icon"
        :src="group.setIconUri"
        alt=""
        @error="onIconError?.($event, group)"
      />
      <span>{{ titleText(group, showFullSetName) }}</span>
    </h2>
    <p v-if="metaLine">{{ metaLine }}</p>
    <time v-if="includeTimestamp && generatedAt" :datetime="generatedAt.toISOString().slice(0, 10)">
      {{ generatedAt.toLocaleDateString() }}
    </time>
  </header>
</template>
