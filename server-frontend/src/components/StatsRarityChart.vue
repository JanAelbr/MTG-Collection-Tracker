<script setup>
import "../styles/stats.css";
import { computed } from "vue";
import { COLLECTION_RARITY_LABELS } from "../utils/collectionRarities";
import { rarityColor } from "../utils/mtgTheme";

const props = defineProps({
  rows: { type: Array, default: () => [] },
});

const buckets = computed(() =>
  (props.rows || []).map((row) => {
    const rarity = String(row.rarity || "unknown");
    const owned = Math.max(0, Number(row.owned) || 0);
    const catalog = Math.max(0, Number(row.catalog) || 0);
    return {
      id: rarity,
      label: COLLECTION_RARITY_LABELS[rarity] || rarity.replace(/_/g, " "),
      owned,
      catalog,
      percent: catalog > 0 ? Math.round((owned / catalog) * 100) : null,
      color: rarityColor(rarity),
    };
  }),
);

const hasData = computed(() => buckets.value.some((bucket) => bucket.catalog > 0 || bucket.owned > 0));
</script>

<template>
  <div class="stats-rarity-chart">
    <p v-if="!hasData" class="stats-rarity-chart-empty">No rarity data for this set yet.</p>

    <ul v-else class="stats-rarity-chart-summary">
      <li v-for="bucket in buckets" :key="`summary-${bucket.id}`">
        <strong :style="{ color: bucket.color }">{{ bucket.label }}</strong>
        <span>{{ bucket.owned }} / {{ bucket.catalog }}</span>
        <span v-if="bucket.percent != null" class="stats-rarity-chart-summary-pct">
          {{ bucket.percent }}%
        </span>
      </li>
    </ul>
  </div>
</template>
