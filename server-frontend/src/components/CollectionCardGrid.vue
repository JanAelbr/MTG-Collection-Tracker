<script setup>
import { computed, ref } from "vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import { isEffectivelyOwned, ownershipRevision } from "../composables/cardContextMenu";
import { useFavorites } from "../composables/favorites";
import { cardSelectionKey } from "../utils/collectionScopeStats";
import CardFinishBadge from "./CardFinishBadge.vue";
import { formatProfitBracket } from "../utils/format";
import { cardDisplayName, cardFinish, cardRouteQuery } from "../utils/finishes";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  showUnownedBadge: { type: Boolean, default: false },
  showSetLabel: { type: Boolean, default: false },
  setLabelFor: { type: Function, default: null },
  browseNames: { type: Boolean, default: false },
  selectedName: { type: String, default: "" },
  cardScale: { type: Number, default: 100 },
  /** When set, lock to this column count (needed for virtualized scrolling). */
  columns: { type: Number, default: 0 },
  selectable: { type: Boolean, default: false },
  selectedKeys: { type: Object, default: null },
  focusedIndex: { type: Number, default: -1 },
  startIndex: { type: Number, default: 0 },
  showFavorites: { type: Boolean, default: true },
  reorderable: { type: Boolean, default: false },
  /** Optional section override for displayed / tooltip-active price strategy. */
  priceStrategy: { type: String, default: "" },
});

const emit = defineEmits([
  "browse-name",
  "ownership-changed",
  "toggle-select",
  "focus-index",
  "favorite-changed",
  "reorder",
]);

const { isCardFavorite, toggleCardFavorite } = useFavorites();
const dragFromIndex = ref(-1);
const dragOverIndex = ref(-1);

const gridStyle = computed(() => {
  const style = {
    "--collection-card-scale": String(props.cardScale / 100),
  };
  if (props.columns > 0) {
    style.gridTemplateColumns = `repeat(${props.columns}, minmax(0, 1fr))`;
  }
  return style;
});

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

async function onToggleFavorite(event, card) {
  event.preventDefault();
  event.stopPropagation();
  const result = await toggleCardFavorite(card, cardFinish(card));
  if (result) {
    emit("favorite-changed", result);
  }
}

function clearDragState() {
  dragFromIndex.value = -1;
  dragOverIndex.value = -1;
}

function onDragStart(index, event) {
  if (!props.reorderable) {
    return;
  }
  dragFromIndex.value = index;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(index));
  }
}

function onDragOver(index, event) {
  if (!props.reorderable || dragFromIndex.value < 0) {
    return;
  }
  event.preventDefault();
  dragOverIndex.value = index;
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "move";
  }
}

function onDrop(index, event) {
  if (!props.reorderable) {
    return;
  }
  event.preventDefault();
  const from = dragFromIndex.value;
  clearDragState();
  if (from < 0 || from === index) {
    return;
  }
  const next = props.cards.slice();
  const [moved] = next.splice(from, 1);
  next.splice(index, 0, moved);
  emit("reorder", next);
}
</script>

<template>
  <div class="collection-card-grid" :class="{ 'is-reorderable': reorderable }" :style="gridStyle">
    <figure
      v-for="(card, index) in cards"
      :key="cardKey(card)"
      class="collection-card-grid-item"
      :class="{
        'is-unowned': showUnownedBadge && !cardIsOwned(card),
        'is-selected': isCardSelected(card) || isBulkSelected(card),
        'is-focused': isFocused(index),
        'is-selectable': selectable,
        'is-dragging': reorderable && dragFromIndex === index,
        'is-drop-target': reorderable && dragOverIndex === index && dragFromIndex !== index,
      }"
      :draggable="reorderable && !browseNames"
      :tabindex="!selectable && focusedIndex === startIndex + index ? 0 : -1"
      @mousedown="onTileMouseDown"
      @click="onTileClick(card, index, $event)"
      @focus="onTileFocus(index)"
      @dragstart="onDragStart(index, $event)"
      @dragover="onDragOver(index, $event)"
      @drop="onDrop(index, $event)"
      @dragend="clearDragState"
    >
      <span
        v-if="reorderable && !browseNames"
        class="collection-card-drag-handle"
        title="Drag to reorder"
        aria-hidden="true"
      >⋮⋮</span>
      <button
        v-if="showFavorites && !browseNames"
        type="button"
        class="collection-card-favorite"
        :class="{ 'is-favorite': isCardFavorite(card) }"
        :aria-pressed="isCardFavorite(card) ? 'true' : 'false'"
        :aria-label="isCardFavorite(card) ? `Unfavourite ${cardDisplayName(card)}` : `Favourite ${cardDisplayName(card)}`"
        :title="isCardFavorite(card) ? 'Unfavourite card' : 'Favourite card'"
        @click="onToggleFavorite($event, card)"
      >
        {{ isCardFavorite(card) ? "★" : "☆" }}
      </button>
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
        <span class="collection-card-grid-name-row">
          <RouterLink
            :to="cardRoute(card)"
            class="collection-card-grid-name"
            @mousedown="onTileMouseDown"
            @click="selectable ? onTileClick(card, index, $event) : onCardActivate(card, $event)"
            @focus="onTileFocus(index)"
          >
            #{{ String(card.collectorNumber).padStart(3, "0") }} · {{ card.name || card.cardName }}
          </RouterLink>
          <CardFinishBadge :card="card" compact />
        </span>
        <span v-if="showSetLabel" class="collection-card-grid-set">
          <CollectionSetLink
            :set-code="card.setCode"
            :art-style="card.artStyle || ''"
            :label="setLabel(card)"
          />
        </span>
        <span class="collection-card-grid-value">
          <PriceStrategyValue :card="card" :price-strategy="priceStrategy" />
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
