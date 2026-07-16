<script setup>
import { computed } from "vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import { isEffectivelyOwned, ownershipRevision } from "../composables/cardContextMenu";
import { cardSelectionKey } from "../utils/collectionScopeStats";
import { formatProfitBracket } from "../utils/format";
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
  selectable: { type: Boolean, default: false },
  selectedKeys: { type: Object, default: null },
  focusedIndex: { type: Number, default: -1 },
  startIndex: { type: Number, default: 0 },
});

const emit = defineEmits(["browse-name", "ownership-changed", "toggle-select", "focus-index"]);

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

function gainBracket(card) {
  if (!cardIsOwned(card) || card.purchaseValue == null || card.purchaseValue === 0) {
    return null;
  }
  return formatProfitBracket(card.profitLoss);
}

function gainClass(card) {
  if (card.profitLoss == null) {
    return "";
  }
  return card.profitLoss >= 0 ? "reports-gain" : "reports-loss";
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

function isBulkSelected(card) {
  return Boolean(props.selectedKeys?.has(cardSelectionKey(card)));
}

function isFocused(index) {
  return props.focusedIndex === index;
}

function onTileMouseDown(event) {
  if (props.selectable) {
    event.preventDefault();
  }
}

function onTileClick(card, index, event) {
  if (props.selectable) {
    event?.preventDefault();
    emit("toggle-select", card);
    return;
  }
  emit("focus-index", props.startIndex + index);
}

function onTileFocus(index) {
  if (props.selectable) {
    return;
  }
  emit("focus-index", props.startIndex + index);
}
</script>

<template>
  <div class="collection-card-grid" :style="gridStyle">
    <figure
      v-for="(card, index) in cards"
      :key="cardKey(card)"
      class="collection-card-grid-item"
      :class="{
        'is-unowned': showUnownedBadge && !cardIsOwned(card),
        'is-selected': isCardSelected(card) || isBulkSelected(card),
        'is-focused': isFocused(index),
        'is-selectable': selectable,
      }"
      :tabindex="!selectable && focusedIndex === startIndex + index ? 0 : -1"
      @mousedown="onTileMouseDown"
      @click="onTileClick(card, index, $event)"
      @focus="onTileFocus(index)"
    >
      <button
        v-if="browseNames"
        type="button"
        class="collection-card-grid-select"
        @click="emit('browse-name', card.name)"
      >
        <div class="collection-card-grid-image-wrap">
          <span
            v-if="isCardSelected(card)"
            class="collection-card-grid-browse-selected-badge"
          >
            Selected
          </span>
          <CardInteractiveImage
            v-if="card.imageUri"
            :src="card.imageUri"
            :alt="card.name"
            :card="card"
            :show-details="false"
            img-class="collection-card-grid-image"
            @ownership-changed="emit('ownership-changed')"
          />
          <div v-else class="collection-card-grid-placeholder">{{ card.name }}</div>
        </div>
        <span class="collection-card-grid-name">{{ card.name }}</span>
      </button>
      <template v-else>
      <div class="collection-card-grid-image-wrap">
        <span v-if="selectable && isBulkSelected(card)" class="collection-card-grid-check" aria-hidden="true">✓</span>
        <CardInteractiveImage
          v-if="card.imageUri"
          :src="card.imageUri"
          :alt="card.name"
          :card="card"
          :show-details="false"
          @ownership-changed="emit('ownership-changed')"
        />
        <div v-else class="collection-card-grid-placeholder">{{ card.name }}</div>
      </div>
      <figcaption class="collection-card-grid-caption">
        <RouterLink
          :to="cardRoute(card)"
          class="collection-card-grid-name"
          @mousedown="onTileMouseDown"
          @click="selectable ? onTileClick(card, index, $event) : onCardActivate(card, $event)"
          @focus="onTileFocus(index)"
        >
          #{{ String(card.collectorNumber).padStart(3, "0") }} · {{ cardDisplayName(card) }}
        </RouterLink>
        <span v-if="showSetLabel" class="collection-card-grid-set">
          <CollectionSetLink
            :set-code="card.setCode"
            :art-style="card.artStyle || ''"
            :label="setLabel(card)"
          />
        </span>
        <span
          v-if="showFinishBadge"
          class="collection-card-grid-finish"
          :class="`is-finish-${cardFinish(card)}`"
        >
          {{ finishLabel(cardFinish(card)) }}
        </span>
        <span class="collection-card-grid-value">
          <PriceStrategyValue :card="card" />
          <span
            v-if="gainBracket(card)"
            class="collection-card-grid-gain"
            :class="gainClass(card)"
          >{{ gainBracket(card) }}</span>
        </span>
        <span v-if="showUnownedBadge && !cardIsOwned(card)" class="reports-unowned-badge">
          Not owned
        </span>
      </figcaption>
      </template>
    </figure>
  </div>
</template>
