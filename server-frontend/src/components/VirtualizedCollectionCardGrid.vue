<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import CollectionCardGrid from "./CollectionCardGrid.vue";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  cardScale: { type: Number, default: 100 },
  showUnownedBadge: { type: Boolean, default: false },
  showFinishBadge: { type: Boolean, default: false },
  browseNames: { type: Boolean, default: false },
  selectedName: { type: String, default: "" },
  selectable: { type: Boolean, default: false },
  selectedKeys: { type: Object, default: null },
  focusedIndex: { type: Number, default: -1 },
  hasMore: { type: Boolean, default: false },
  loadMoreThreshold: { type: Number, default: 240 },
});

const emit = defineEmits([
  "toggle-select",
  "focus-index",
  "keydown",
  "ownership-changed",
  "browse-name",
  "load-more",
]);

const rootRef = ref(null);
const viewportHeight = ref(640);
const scrollTop = ref(0);
const columnCount = ref(4);
const rowHeight = ref(260);
const overscanRows = 2;

const BASE_COL_WIDTH = 118;
const BASE_GAP = 16;
const BASE_ROW_HEIGHT = 250;

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
  return totalRows.value * rowHeight.value + BASE_GAP * scaleFactor.value;
});

const visibleRange = computed(() => {
  if (!props.cards.length) {
    return { start: 0, end: 0, offsetY: 0 };
  }
  const startRow = Math.max(0, Math.floor(scrollTop.value / rowHeight.value) - overscanRows);
  const visibleRows = Math.ceil(viewportHeight.value / rowHeight.value) + overscanRows * 2;
  const endRow = Math.min(totalRows.value, startRow + visibleRows);
  const start = startRow * columnCount.value;
  const end = Math.min(props.cards.length, endRow * columnCount.value);
  return {
    start,
    end,
    offsetY: startRow * rowHeight.value,
  };
});

const visibleCards = computed(() => props.cards.slice(visibleRange.value.start, visibleRange.value.end));

function measureLayout() {
  const root = rootRef.value;
  if (!root) {
    return;
  }
  viewportHeight.value = root.clientHeight || 640;
  const width = root.clientWidth || 640;
  const colWidth = (BASE_COL_WIDTH + BASE_GAP) * scaleFactor.value;
  columnCount.value = Math.max(1, Math.floor((width + BASE_GAP * scaleFactor.value) / colWidth));
  rowHeight.value = BASE_ROW_HEIGHT * scaleFactor.value;
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
  () => [props.cards.length, props.cardScale],
  () => {
    nextTick(measureLayout);
  },
);

let resizeObserver = null;

onMounted(() => {
  measureLayout();
  if (typeof ResizeObserver !== "undefined" && rootRef.value) {
    resizeObserver = new ResizeObserver(() => measureLayout());
    resizeObserver.observe(rootRef.value);
  } else {
    window.addEventListener("resize", measureLayout);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  window.removeEventListener("resize", measureLayout);
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
          :show-unowned-badge="showUnownedBadge"
          :show-finish-badge="showFinishBadge"
          :card-scale="cardScale"
          :browse-names="browseNames"
          :selected-name="selectedName"
          :selectable="selectable"
          :selected-keys="selectedKeys"
          :focused-index="focusedIndex >= 0 ? focusedIndex - visibleRange.start : -1"
          :start-index="visibleRange.start"
          @toggle-select="emit('toggle-select', $event)"
          @focus-index="emit('focus-index', $event)"
          @browse-name="emit('browse-name', $event)"
          @ownership-changed="emit('ownership-changed')"
        />
      </div>
    </div>
  </div>
</template>
