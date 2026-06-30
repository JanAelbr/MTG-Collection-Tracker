<script setup>
import { computed } from "vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import { isEffectivelyOwned, ownershipRevision } from "../composables/cardContextMenu";
import { formatEuro, formatPriceChangeEuroBracket, formatPriceChangePercentBracket, formatProfit } from "../utils/format";
import { cardDisplayName, cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  showUnownedBadge: { type: Boolean, default: false },
  showFinishBadge: { type: Boolean, default: false },
  showSetLabel: { type: Boolean, default: false },
  setLabelFor: { type: Function, default: null },
  browseNames: { type: Boolean, default: false },
  selectedName: { type: String, default: "" },
  cardScale: { type: Number, default: 100 },
  priceChangeMode: { type: String, default: "" },
});

const emit = defineEmits(["browse-name"]);

const gridStyle = computed(() => ({
  "--collection-card-scale": String(props.cardScale / 100),
}));

// Re-render owned styling when ownership changes.
const ownershipTick = computed(() => ownershipRevision.value);

function cardRoute(card) {
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function cardKey(card) {
  ownershipTick.value;
  return `${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`;
}

function cardIsOwned(card) {
  ownershipTick.value;
  return isEffectivelyOwned(card);
}

function gainLabel(card) {
  if (!cardIsOwned(card) || card.purchaseValue == null || card.purchaseValue === 0) {
    return null;
  }
  return formatProfit(card.profitLoss);
}

function priceChangeBracket(card) {
  if (props.priceChangeMode === "changeEuro") {
    return formatPriceChangeEuroBracket(card.priceChange);
  }
  if (props.priceChangeMode === "changePct") {
    return formatPriceChangePercentBracket(card.priceChange, card.previousValue);
  }
  return null;
}

function priceChangeClass(card) {
  const change = card.priceChange;
  if (change == null || change === 0) {
    return "";
  }
  return change > 0 ? "reports-change-up" : "reports-change-down";
}

function setLabel(card) {
  if (!props.showSetLabel) {
    return "";
  }
  if (props.setLabelFor) {
    return props.setLabelFor(card.setCode);
  }
  return card.setCode || "";
}

function onCardActivate(card, event) {
  if (props.browseNames && card?.name) {
    event?.preventDefault();
    emit("browse-name", card.name);
  }
}

function isCardSelected(card) {
  return Boolean(props.browseNames && props.selectedName && card.name === props.selectedName);
}
</script>

<template>
  <div class="collection-card-grid" :style="gridStyle">
    <figure
      v-for="card in cards"
      :key="cardKey(card)"
      class="collection-card-grid-item"
      :class="{
        'is-unowned': showUnownedBadge && !cardIsOwned(card),
        'is-selected': isCardSelected(card),
      }"
    >
      <button
        v-if="browseNames"
        type="button"
        class="collection-card-grid-select"
        @click="emit('browse-name', card.name)"
      >
        <img
          v-if="card.imageUri"
          :src="card.imageUri"
          :alt="card.name"
          class="collection-card-grid-image"
        />
        <div v-else class="collection-card-grid-placeholder">{{ card.name }}</div>
        <span class="collection-card-grid-name">{{ card.name }}</span>
      </button>
      <template v-else>
      <div class="collection-card-grid-image-wrap">
        <CardInteractiveImage
          v-if="card.imageUri"
          :src="card.imageUri"
          :alt="card.name"
          :card="card"
          :show-details="false"
        />
        <div v-else class="collection-card-grid-placeholder">{{ card.name }}</div>
      </div>
      <figcaption class="collection-card-grid-caption">
        <RouterLink
          :to="cardRoute(card)"
          class="collection-card-grid-name"
          @click="onCardActivate(card, $event)"
        >
          #{{ String(card.collectorNumber).padStart(3, "0") }} · {{ cardDisplayName(card) }}
        </RouterLink>
        <span v-if="showSetLabel" class="collection-card-grid-set">{{ setLabel(card) }}</span>
        <span
          v-if="showFinishBadge"
          class="collection-card-grid-finish"
          :class="`is-finish-${cardFinish(card)}`"
        >
          {{ finishLabel(cardFinish(card)) }}
        </span>
        <span class="collection-card-grid-value">
          {{ formatEuro(card.currentValue) }}<span
            v-if="priceChangeBracket(card)"
            class="collection-card-grid-change"
            :class="priceChangeClass(card)"
          > {{ priceChangeBracket(card) }}</span>
        </span>
        <span
          v-if="gainLabel(card)"
          class="collection-card-grid-gain"
          :class="{
            'reports-gain': card.profitLoss != null && card.profitLoss >= 0,
            'reports-loss': card.profitLoss != null && card.profitLoss < 0,
          }"
        >
          {{ gainLabel(card) }}
        </span>
        <span v-if="showUnownedBadge && !cardIsOwned(card)" class="reports-unowned-badge">
          Not owned
        </span>
      </figcaption>
      </template>
    </figure>
  </div>
</template>
