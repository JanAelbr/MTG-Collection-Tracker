<script setup>
import "../styles/stats.css";
import { computed } from "vue";
import CardSetSymbol from "./CardSetSymbol.vue";
import { COLLECTION_RARITY_LABELS } from "../utils/collectionRarities";
import { rarityColor } from "../utils/mtgTheme";

const props = defineProps({
  rows: { type: Array, default: () => [] },
  setCode: { type: String, default: "" },
  familyRoot: { type: String, default: "" },
  iconUri: { type: String, default: "" },
});

const buckets = computed(() =>
  (props.rows || []).map((row) => {
    const rarity = String(row.rarity || "unknown");
    const owned = Math.max(0, Number(row.owned) || 0);
    const catalog = Math.max(0, Number(row.catalog) || 0);
    const percent = catalog > 0 ? (owned / catalog) * 100 : null;
    return {
      id: rarity,
      label: COLLECTION_RARITY_LABELS[rarity] || rarity.replace(/_/g, " "),
      owned,
      catalog,
      percent,
      color: rarityColor(rarity),
      barWidth: percent == null || percent <= 0
        ? 0
        : Math.min(100, Math.max(4, percent)),
      percentLabel: percent == null
        ? "—"
        : `${percent.toFixed(percent >= 10 || percent === 0 ? 0 : 1)}%`,
      title: catalog > 0 ? `${owned} / ${catalog} (${percent.toFixed(1)}%)` : `${owned} owned`,
    };
  }),
);

const hasData = computed(() => buckets.value.some((bucket) => bucket.catalog > 0 || bucket.owned > 0));
const showSetIcon = computed(() => {
  const code = String(props.setCode || "").trim().toUpperCase();
  return Boolean(code && code !== "ALL");
});
</script>

<template>
  <div class="stats-rarity-chart">
    <p v-if="!hasData" class="stats-rarity-chart-empty">No rarity data for this set yet.</p>

    <ul
      v-else
      class="stats-rarity-chart-summary"
      :class="{ 'has-set-icons': showSetIcon }"
    >
      <li v-for="bucket in buckets" :key="`summary-${bucket.id}`">
        <CardSetSymbol
          v-if="showSetIcon"
          class="stats-rarity-chart-set-icon"
          :set-code="setCode"
          :family-root="familyRoot"
          :icon-uri="iconUri"
          :rarity="bucket.id"
          :size="22"
        />
        <div class="stats-rarity-chart-copy">
          <strong :style="{ color: bucket.color }">{{ bucket.label }}</strong>
          <span class="stats-rarity-chart-counts">{{ bucket.owned }} / {{ bucket.catalog }}</span>
        </div>
        <div
          class="stats-completion-bar-wrap stats-rarity-chart-bar"
          :title="bucket.title"
          :aria-label="`${bucket.label}: ${bucket.title}`"
        >
          <div
            class="stats-completion-bar"
            :style="{
              width: `${bucket.barWidth}%`,
              background: `linear-gradient(90deg, ${bucket.color}55 0%, ${bucket.color}99 100%)`,
            }"
          />
          <span class="stats-completion-label">
            {{ bucket.percentLabel }}
          </span>
        </div>
      </li>
    </ul>
  </div>
</template>
