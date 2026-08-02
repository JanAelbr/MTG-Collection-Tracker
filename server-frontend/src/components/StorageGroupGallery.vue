<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import VirtualizedCollectionCardGrid from "./VirtualizedCollectionCardGrid.vue";

const GROUP_VISIBLE_ROWS = 3;
const BASE_COL_WIDTH = 118;
const BASE_COL_GAP = 12;
const BASE_ROW_GAP = 8;
const GRID_PAD_X = 8;
const CARD_ASPECT_RATIO = 88 / 63;
const CAPTION_MARGIN_TOP = 4;
const CAPTION_HEIGHT_BASE = 40;

const props = defineProps({
  cards: { type: Array, default: () => [] },
  cardScale: { type: Number, default: 100 },
  /** Use a bounded, virtualized viewport when the group is large. */
  scrollable: { type: Boolean, default: false },
  showSetLabel: { type: Boolean, default: false },
  setLabelFor: { type: Function, default: null },
  showUnownedBadge: { type: Boolean, default: false },
  browseNames: { type: Boolean, default: false },
  selectedName: { type: String, default: "" },
  selectable: { type: Boolean, default: false },
  selectedKeys: { type: Object, default: null },
  showFavorites: { type: Boolean, default: true },
  zoomOnly: { type: Boolean, default: false },
});

const emit = defineEmits([
  "toggle-select",
  "browse-name",
  "cycle-variant",
  "ownership-changed",
  "favorite-changed",
  "load-more",
]);

const rootRef = ref(null);
const containerWidth = ref(640);

const scaleFactor = computed(() => Math.max(0.25, Number(props.cardScale) / 100 || 1));

const gridMetrics = computed(() => {
  const scale = scaleFactor.value;
  const minCol = BASE_COL_WIDTH * scale;
  const colGap = BASE_COL_GAP * scale;
  const usable = Math.max(minCol, containerWidth.value - GRID_PAD_X);
  const columns = Math.max(1, Math.floor((usable + colGap) / (minCol + colGap)));
  const colWidth = (usable - colGap * (columns - 1)) / columns;
  const rowStride = colWidth * CARD_ASPECT_RATIO
    + (CAPTION_MARGIN_TOP + CAPTION_HEIGHT_BASE + BASE_ROW_GAP) * scale;
  const cardCount = props.cards?.length || 0;
  const totalRows = cardCount ? Math.ceil(cardCount / columns) : 0;
  const visibleRows = Math.min(GROUP_VISIBLE_ROWS, Math.max(totalRows, 0));
  return {
    columns,
    rowStride,
    totalRows,
    visibleRows,
    height: visibleRows > 0 ? visibleRows * rowStride : 0,
  };
});

const galleryStyle = computed(() => {
  const scale = scaleFactor.value;
  const style = {
    "--collection-card-scale": String(scale),
    "--storage-group-row-stride": `${gridMetrics.value.rowStride}px`,
  };
  if (props.scrollable && gridMetrics.value.height > 0) {
    style.height = `${gridMetrics.value.height}px`;
    style["--storage-group-gallery-height"] = `${gridMetrics.value.height}px`;
  } else if (!props.scrollable && gridMetrics.value.totalRows >= GROUP_VISIBLE_ROWS) {
    style.minHeight = `${GROUP_VISIBLE_ROWS * gridMetrics.value.rowStride}px`;
  }
  return style;
});

function measureWidth() {
  const width = rootRef.value?.clientWidth;
  if (width && Math.abs(width - containerWidth.value) >= 1) {
    containerWidth.value = width;
  } else if (width && !containerWidth.value) {
    containerWidth.value = width;
  }
}

let resizeObserver = null;

onMounted(() => {
  measureWidth();
  if (typeof ResizeObserver !== "undefined" && rootRef.value) {
    resizeObserver = new ResizeObserver(() => {
      measureWidth();
    });
    resizeObserver.observe(rootRef.value);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});

watch(
  () => [props.cardScale, props.cards?.length, props.scrollable],
  () => {
    nextTick(measureWidth);
  },
);
</script>

<template>
  <div
    ref="rootRef"
    class="storage-set-group-gallery"
    :class="{ 'is-scrollable-group': scrollable }"
    :style="galleryStyle"
  >
    <VirtualizedCollectionCardGrid
      v-if="scrollable"
      :cards="cards"
      :card-scale="cardScale"
      :show-set-label="showSetLabel"
      :set-label-for="setLabelFor"
      :show-unowned-badge="showUnownedBadge"
      :browse-names="browseNames"
      :selected-name="selectedName"
      :selectable="selectable"
      :selected-keys="selectedKeys"
      :show-favorites="showFavorites"
      :zoom-only="zoomOnly"
      @toggle-select="emit('toggle-select', $event)"
      @browse-name="emit('browse-name', $event)"
      @cycle-variant="emit('cycle-variant', $event)"
      @ownership-changed="emit('ownership-changed', $event)"
      @favorite-changed="emit('favorite-changed', $event)"
      @load-more="emit('load-more', $event)"
    />
    <CollectionCardGrid
      v-else
      :cards="cards"
      :card-scale="cardScale"
      :show-set-label="showSetLabel"
      :set-label-for="setLabelFor"
      :show-unowned-badge="showUnownedBadge"
      :browse-names="browseNames"
      :selected-name="selectedName"
      :selectable="selectable"
      :selected-keys="selectedKeys"
      :show-favorites="showFavorites"
      :zoom-only="zoomOnly"
      @toggle-select="emit('toggle-select', $event)"
      @browse-name="emit('browse-name', $event)"
      @cycle-variant="emit('cycle-variant', $event)"
      @ownership-changed="emit('ownership-changed', $event)"
      @favorite-changed="emit('favorite-changed', $event)"
    />
  </div>
</template>
