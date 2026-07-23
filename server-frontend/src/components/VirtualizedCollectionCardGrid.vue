<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import CollectionCardGrid from "./CollectionCardGrid.vue";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  cardScale: { type: Number, default: 100 },
  showUnownedBadge: { type: Boolean, default: false },
  showSetLabel: { type: Boolean, default: false },
  setLabelFor: { type: Function, default: null },
  browseNames: { type: Boolean, default: false },
  selectedName: { type: String, default: "" },
  selectable: { type: Boolean, default: false },
  selectedKeys: { type: Object, default: null },
  focusedIndex: { type: Number, default: -1 },
  hasMore: { type: Boolean, default: false },
  loadMoreThreshold: { type: Number, default: 240 },
  priceStrategy: { type: String, default: "" },
});

const emit = defineEmits([
  "toggle-select",
  "focus-index",
  "keydown",
  "ownership-changed",
  "browse-name",
  "load-more",
  "favorite-changed",
]);

const rootRef = ref(null);
const viewportHeight = ref(640);
const scrollTop = ref(0);
const columnCount = ref(4);
const rowHeight = ref(320);
const overscanRows = 2;

/** Matches `.collection-card-grid` min column width. */
const BASE_COL_WIDTH = 118;
/** Matches `.collection-card-grid` gap. */
const BASE_GAP = 16;
/** Matches `.collection-card-grid` horizontal padding (4px + 4px). */
const GRID_PAD_X = 8;
/** Standard MTG card proportion (height / width). */
const CARD_ASPECT_RATIO = 88 / 63;
/** Matches `.collection-card-grid-caption` margin-top. */
const CAPTION_MARGIN_TOP = 6;
/** Reserved caption block; keep in sync with CSS min-heights. */
const CAPTION_HEIGHT_BASE = 32;
const CAPTION_HEIGHT_WITH_SET = 46;
const CAPTION_HEIGHT_WITH_BADGE = 12;

const gridStyle = computed(() => ({
  "--collection-card-scale": String(props.cardScale / 100),
}));

const scaleFactor = computed(() => props.cardScale / 100);

const totalRows = computed(() => {
  if (!props.cards.length || columnCount.value <= 0) {
    return 0;
  }
  return Math.ceil(props.cards.length / columnCount.value);
});

const totalHeight = computed(() => {
  if (!totalRows.value) {
    return 0;
  }
  return totalRows.value * rowHeight.value;
});

const visibleRange = computed(() => {
  if (!props.cards.length) {
    return { start: 0, end: 0, offsetY: 0 };
  }
  const stride = Math.max(rowHeight.value, 1);
  const startRow = Math.max(0, Math.floor(scrollTop.value / stride) - overscanRows);
  const visibleRows = Math.ceil(viewportHeight.value / stride) + overscanRows * 2;
  const endRow = Math.min(totalRows.value, startRow + visibleRows);
  const start = startRow * columnCount.value;
  const end = Math.min(props.cards.length, endRow * columnCount.value);
  return {
    start,
    end,
    offsetY: startRow * stride,
  };
});

const visibleCards = computed(() => props.cards.slice(visibleRange.value.start, visibleRange.value.end));

let lastMeasuredWidth = 0;
let measureRaf = 0;

function reservedCaptionHeight() {
  let height = props.showSetLabel ? CAPTION_HEIGHT_WITH_SET : CAPTION_HEIGHT_BASE;
  if (props.showUnownedBadge) {
    height += CAPTION_HEIGHT_WITH_BADGE;
  }
  return height * scaleFactor.value;
}

/** Deterministic row stride from column width — must stay >= rendered tile height. */
function rowStrideForColumnWidth(columnWidth) {
  const imageHeight = columnWidth * CARD_ASPECT_RATIO;
  const captionHeight = CAPTION_MARGIN_TOP * scaleFactor.value + reservedCaptionHeight();
  const gap = BASE_GAP * scaleFactor.value;
  return imageHeight + captionHeight + gap;
}

function measureLayout({ force = false } = {}) {
  const root = rootRef.value;
  if (!root) {
    return;
  }

  const width = root.clientWidth || 640;
  const height = root.clientHeight || 640;
  viewportHeight.value = height;

  const widthChanged = Math.abs(width - lastMeasuredWidth) >= 1;
  if (!force && !widthChanged && columnCount.value > 0) {
    scrollTop.value = root.scrollTop;
    return;
  }
  lastMeasuredWidth = width;

  const prevColumns = columnCount.value;
  const prevRowHeight = rowHeight.value;
  const prevScroll = root.scrollTop;
  const firstIndex = prevColumns > 0
    ? Math.floor(prevScroll / Math.max(prevRowHeight, 1)) * prevColumns
    : 0;

  const gap = BASE_GAP * scaleFactor.value;
  const minColWidth = BASE_COL_WIDTH * scaleFactor.value;
  const usable = Math.max(minColWidth, width - GRID_PAD_X);
  const nextColumns = Math.max(1, Math.floor((usable + gap) / (minColWidth + gap)));
  const nextColWidth = (usable - gap * (nextColumns - 1)) / nextColumns;
  const nextRowHeight = rowStrideForColumnWidth(nextColWidth);

  columnCount.value = nextColumns;
  rowHeight.value = nextRowHeight;

  if (
    prevColumns > 0
    && (prevColumns !== nextColumns || Math.abs(prevRowHeight - nextRowHeight) > 1)
  ) {
    const nextScroll = Math.floor(firstIndex / nextColumns) * nextRowHeight;
    if (Math.abs(root.scrollTop - nextScroll) > 1) {
      root.scrollTop = nextScroll;
    }
  }
  scrollTop.value = root.scrollTop;
}

function scheduleMeasure(options = {}) {
  if (measureRaf) {
    return;
  }
  measureRaf = requestAnimationFrame(() => {
    measureRaf = 0;
    measureLayout(options);
  });
}

function onScroll(event) {
  const el = event.target;
  scrollTop.value = el.scrollTop;
  if (!props.hasMore) {
    return;
  }
  const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
  if (remaining <= props.loadMoreThreshold) {
    emit("load-more");
  }
}

function scrollToIndex(index) {
  if (index < 0 || !columnCount.value) {
    return;
  }
  const row = Math.floor(index / columnCount.value);
  const root = rootRef.value;
  if (!root) {
    return;
  }
  root.scrollTop = Math.max(0, row * rowHeight.value - rowHeight.value);
  scrollTop.value = root.scrollTop;
}

watch(
  () => [props.cards.length, props.cardScale, props.showSetLabel, props.showUnownedBadge],
  () => {
    nextTick(() => scheduleMeasure({ force: true }));
  },
);

let resizeObserver = null;

function onWindowResize() {
  scheduleMeasure({ force: true });
}

onMounted(() => {
  measureLayout({ force: true });
  if (typeof ResizeObserver !== "undefined" && rootRef.value) {
    resizeObserver = new ResizeObserver(() => scheduleMeasure());
    resizeObserver.observe(rootRef.value);
  } else {
    window.addEventListener("resize", onWindowResize);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  window.removeEventListener("resize", onWindowResize);
  if (measureRaf) {
    cancelAnimationFrame(measureRaf);
  }
});

defineExpose({ scrollToIndex, rootRef });
</script>

<template>
  <div
    ref="rootRef"
    class="collection-virtual-grid"
    :style="gridStyle"
    tabindex="0"
    @scroll="onScroll"
    @keydown="emit('keydown', $event)"
  >
    <div class="collection-virtual-grid-spacer" :style="{ height: `${totalHeight}px` }">
      <div
        class="collection-virtual-grid-window"
        :style="{ transform: `translateY(${visibleRange.offsetY}px)` }"
      >
        <CollectionCardGrid
          :cards="visibleCards"
          :columns="columnCount"
          :show-unowned-badge="showUnownedBadge"
          :show-set-label="showSetLabel"
          :set-label-for="setLabelFor"
          :card-scale="cardScale"
          :browse-names="browseNames"
          :selected-name="selectedName"
          :selectable="selectable"
          :selected-keys="selectedKeys"
          :focused-index="focusedIndex >= 0 ? focusedIndex - visibleRange.start : -1"
          :start-index="visibleRange.start"
          :price-strategy="priceStrategy"
          @toggle-select="emit('toggle-select', $event)"
          @focus-index="emit('focus-index', $event)"
          @browse-name="emit('browse-name', $event)"
          @ownership-changed="emit('ownership-changed')"
          @favorite-changed="emit('favorite-changed', $event)"
        />
      </div>
    </div>
  </div>
</template>
