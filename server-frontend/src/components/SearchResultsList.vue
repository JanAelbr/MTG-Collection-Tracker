<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import CardPreview from "./CardPreview.vue";
import CardSetSymbol from "./CardSetSymbol.vue";
import ManaCost from "./ManaCost.vue";
import { usePricingSettings } from "../composables/pricingSettings";
import {
  displayCardValue,
  formatPowerToughness,
  formatRarityLabel,
  formatTypeLabel,
} from "../utils/searchResults";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  selectedName: { type: String, default: "" },
  setLabelFor: { type: Function, default: null },
  loadingMore: { type: Boolean, default: false },
  hasMore: { type: Boolean, default: false },
});

const emit = defineEmits(["browse-name", "load-more"]);

const { settings: pricingSettings } = usePricingSettings();
const loadMoreSentinelRef = ref(null);
let loadMoreObserver = null;

function setLabel(card) {
  if (!props.setLabelFor || !card?.setCode) {
    return card?.setCode || "—";
  }
  return props.setLabelFor(card.setCode);
}

function onRowClick(card) {
  if (card?.name) {
    emit("browse-name", card.name);
  }
}

function disconnectLoadMoreObserver() {
  loadMoreObserver?.disconnect();
  loadMoreObserver = null;
}

async function setupLoadMoreObserver() {
  disconnectLoadMoreObserver();
  await nextTick();
  const sentinel = loadMoreSentinelRef.value;
  if (!sentinel || !props.hasMore) {
    return;
  }
  loadMoreObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        emit("load-more");
      }
    },
    { rootMargin: "240px" },
  );
  loadMoreObserver.observe(sentinel);
}

watch(
  () => [props.hasMore, props.cards.length],
  () => {
    setupLoadMoreObserver();
  },
);

onMounted(setupLoadMoreObserver);
onBeforeUnmount(disconnectLoadMoreObserver);
</script>

<template>
  <div class="search-results-list">
    <table class="reports-table search-results-table">
      <thead>
        <tr>
          <th>Card</th>
          <th>Set</th>
          <th>Type</th>
          <th>Mana</th>
          <th>Rarity</th>
          <th>P/T</th>
          <th>Value</th>
          <th>Owned</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="card in cards"
          :key="`${card.name}-${card.setCode}-${card.collectorNumber}`"
          class="search-results-row"
          :class="{ 'is-selected': selectedName === card.name }"
          @click="onRowClick(card)"
        >
          <td class="search-results-card-cell">
            <CardPreview
              :image-uri="card.imageUri || ''"
              :image-uri-back="card.imageUriBack || ''"
            >
              <span class="search-results-card-name">
                <CardSetSymbol :set-code="card.setCode" :rarity="card.rarity || ''" />
                <span class="reports-card-link">{{ card.name }}</span>
              </span>
            </CardPreview>
          </td>
          <td class="search-results-set-cell">
            <span class="search-results-set-row">
              <CardSetSymbol
                :set-code="card.setCode"
                variant="generic"
                :size="16"
              />
              <span class="search-results-set-label">{{ setLabel(card) }}</span>
            </span>
            <span v-if="card.artStyle" class="search-results-art-style">{{ card.artStyle }}</span>
          </td>
          <td>{{ formatTypeLabel(card) }}</td>
          <td class="search-results-mana-cell">
            <ManaCost :mana-cost="card.manaCost || ''" :size="16" />
          </td>
          <td>{{ formatRarityLabel(card.rarity) }}</td>
          <td class="search-results-num-cell">{{ formatPowerToughness(card) }}</td>
          <td class="search-results-num-cell">
            {{ displayCardValue(card, pricingSettings?.priceStrategy || "trend") }}
          </td>
          <td>
            <span
              class="search-results-owned"
              :class="card.owned ? 'search-results-owned-yes' : 'search-results-owned-no'"
            >
              {{ card.owned ? "Owned" : "—" }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
    <div
      v-if="hasMore"
      ref="loadMoreSentinelRef"
      class="manager-load-more-sentinel"
      aria-hidden="true"
    />
  </div>
</template>
