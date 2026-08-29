<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import ManaSymbols from "./ManaSymbols.vue";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  groups: { type: Array, default: null },
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
  showFavorites: { type: Boolean, default: true },
  zoomOnly: { type: Boolean, default: false },
  priceTileTint: { type: Boolean, default: false },
});

const emit = defineEmits([
  "toggle-select",
  "focus-index",
  "keydown",
  "ownership-changed",
  "browse-name",
  "cycle-variant",
  "load-more",
  "favorite-changed",
]);

const rootRef = ref(null);
const viewportHeight = ref(640);
const scrollTop = ref(0);
const columnCount = ref(4);
const rowHeight = ref(320);
const overscanRows = 2;

/** Matches `.collection-card-grid` min column width (175% of the old 118px base). */
const BASE_COL_WIDTH = 207;
/** Matches `.collection-card-grid` column-gap / `--collection-card-col-gap`. */
const BASE_COL_GAP = 16;
/** Matches `.collection-card-grid.has-price-tile-tint` column-gap. */
const TINT_COL_GAP = 8;
/** Matches `.collection-card-grid` row-gap / `--collection-card-row-gap`. */
const BASE_ROW_GAP = 12;
/** Matches `.collection-card-grid.has-price-tile-tint` row-gap. */
const TINT_ROW_GAP = 8;
/** Matches `--collection-card-tile-pad`. */
const BASE_TILE_PAD = 6;
/** Matches `--collection-card-tile-pad` when price tints are on. */
const TINT_TILE_PAD = 8;
/** Matches `.collection-card-grid` horizontal padding (8px + 8px). */
const GRID_PAD_X = 16;
/** Standard MTG card proportion (height / width). */
const CARD_ASPECT_RATIO = 88 / 63;
/** Matches `.collection-card-grid-caption` margin-top. */
const CAPTION_MARGIN_TOP = 2;
/** Matches `.collection-card-grid-select` gap (search/browse tiles). */
const CAPTION_MARGIN_TOP_BROWSE = 8;
/**
 * Reserved caption block; must be >= rendered height or virtual rows overlap
 * (duplicate-looking cards while scrolling). Keep in sync with CSS min-heights.
 * Base includes name row + price row (+ gap).
 */
const CAPTION_HEIGHT_BASE = 28;
/** Name + price; variant-cycle buttons are 26px in the same row. */
const CAPTION_HEIGHT_BROWSE = 36;
const CAPTION_HEIGHT_WITH_SET = 40;
const CAPTION_HEIGHT_WITH_BADGE = 10;
/** Matches `.catalog-gallery-group-header` height + margin. */
const GROUP_HEADER_HEIGHT = 52;

const gridStyle = computed(() => ({
  "--collection-card-scale": String(props.cardScale / 100),
}));

const scaleFactor = computed(() => props.cardScale / 100);

const isGrouped = computed(() => Array.isArray(props.groups) && props.groups.length > 0);

const totalRows = computed(() => {
  if (!props.cards.length || columnCount.value <= 0) {
    return 0;
  }
  return Math.ceil(props.cards.length / columnCount.value);
});

const groupedLayout = computed(() => {
  const cols = Math.max(columnCount.value, 1);
  const rowH = Math.max(rowHeight.value, 1);
  const headerH = GROUP_HEADER_HEIGHT;
  const blocks = [];
  let y = 0;
  let cardOffset = 0;
  for (const group of props.groups || []) {
    const cards = group.cards || [];
    blocks.push({
      type: "header",
      key: `h:${group.path || group.key}`,
      y,
      height: headerH,
      group,
    });
    y += headerH;
    const rows = cards.length ? Math.ceil(cards.length / cols) : 0;
    for (let row = 0; row < rows; row += 1) {
      const start = row * cols;
      const end = Math.min(cards.length, start + cols);
      blocks.push({
        type: "cards",
        key: `c:${group.path || group.key}:${start}`,
        y,
        height: rowH,
        group,
        start,
        end,
        globalStart: cardOffset + start,
        cards: cards.slice(start, end),
      });
      y += rowH;
    }
    cardOffset += cards.length;
  }
  return { blocks, totalHeight: y };
});

const totalHeight = computed(() => {
  if (isGrouped.value) {
    return groupedLayout.value.totalHeight;
  }
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

const groupedVisible = computed(() => {
  const { blocks } = groupedLayout.value;
  if (!blocks.length) {
    return { offsetY: 0, blocks: [] };
  }
  const overscan = overscanRows * Math.max(rowHeight.value, 1);
  const viewStart = Math.max(0, scrollTop.value - overscan);
  const viewEnd = scrollTop.value + viewportHeight.value + overscan;
  const start = firstBlockOverlapping(blocks, viewStart);
  const visible = [];
  for (let i = start; i < blocks.length; i += 1) {
    const block = blocks[i];
    if (block.y >= viewEnd) {
      break;
    }
    visible.push(block);
  }
  return {
    offsetY: visible[0]?.y || 0,
    blocks: visible,
  };
});

let lastMeasuredWidth = 0;
let measureRaf = 0;
let loadMorePending = false;

function firstBlockOverlapping(blocks, y) {
  let lo = 0;
  let hi = blocks.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (blocks[mid].y + blocks[mid].height <= y) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  return lo;
}

function groupMetaText(group) {
  if (group?.metaText) {
    return group.metaText;
  }
  const count = group?.cards?.length || 0;
  return `${count} ${count === 1 ? "card" : "cards"}`;
}

function reservedCaptionHeight() {
  let height = props.browseNames
    ? CAPTION_HEIGHT_BROWSE
    : props.showSetLabel
      ? CAPTION_HEIGHT_WITH_SET
      : CAPTION_HEIGHT_BASE;
  if (props.showUnownedBadge) {
    height += CAPTION_HEIGHT_WITH_BADGE;
  }
  return height * scaleFactor.value;
}

function captionMarginPx() {
  const margin = props.browseNames ? CAPTION_MARGIN_TOP_BROWSE : CAPTION_MARGIN_TOP;
  return margin * scaleFactor.value;
}

function colGapPx() {
  return (props.priceTileTint ? TINT_COL_GAP : BASE_COL_GAP) * scaleFactor.value;
}

function rowGapPx() {
  return (props.priceTileTint ? TINT_ROW_GAP : BASE_ROW_GAP) * scaleFactor.value;
}

function tilePadPx() {
  return (props.priceTileTint ? TINT_TILE_PAD : BASE_TILE_PAD) * scaleFactor.value;
}

/** Deterministic row stride from column width — must stay >= rendered tile height. */
function rowStrideForColumnWidth(columnWidth) {
  const pad = tilePadPx();
  const imageWidth = Math.max(1, columnWidth - pad * 2);
  const imageHeight = imageWidth * CARD_ASPECT_RATIO;
  const captionHeight = captionMarginPx() + reservedCaptionHeight();
  return imageHeight + pad * 2 + captionHeight + rowGapPx();
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

  const gap = colGapPx();
  const minColWidth = BASE_COL_WIDTH * scaleFactor.value;
  const usable = Math.max(minColWidth, width - GRID_PAD_X);
  const nextColumns = Math.max(1, Math.floor((usable + gap) / (minColWidth + gap)));
  const nextColWidth = (usable - gap * (nextColumns - 1)) / nextColumns;
  const nextRowHeight = rowStrideForColumnWidth(nextColWidth);

  columnCount.value = nextColumns;
  rowHeight.value = nextRowHeight;

  if (
    !isGrouped.value
    && prevColumns > 0
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
  if (!props.hasMore || loadMorePending) {
    return;
  }
  const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
  if (remaining <= props.loadMoreThreshold) {
    loadMorePending = true;
    emit("load-more");
  }
}

function yForCardIndex(index) {
  if (index < 0 || !columnCount.value) {
    return 0;
  }
  if (!isGrouped.value) {
    return Math.floor(index / columnCount.value) * rowHeight.value;
  }
  const cols = Math.max(columnCount.value, 1);
  const rowH = Math.max(rowHeight.value, 1);
  let remaining = index;
  let y = 0;
  for (const group of props.groups || []) {
    const count = group.cards?.length || 0;
    y += GROUP_HEADER_HEIGHT;
    if (remaining < count) {
      return y + Math.floor(remaining / cols) * rowH;
    }
    const rows = count ? Math.ceil(count / cols) : 0;
    y += rows * rowH;
    remaining -= count;
  }
  return y;
}

function scrollToIndex(index) {
  if (index < 0 || !columnCount.value) {
    return;
  }
  const root = rootRef.value;
  if (!root) {
    return;
  }
  root.scrollTop = Math.max(0, yForCardIndex(index) - rowHeight.value);
  scrollTop.value = root.scrollTop;
}

watch(
  () => [props.cards.length, props.hasMore, props.groups?.length],
  () => {
    loadMorePending = false;
    nextTick(() => scheduleMeasure({ force: true }));
  },
);

watch(
  () => [
    props.cardScale,
    props.showSetLabel,
    props.showUnownedBadge,
    props.browseNames,
    props.priceTileTint,
  ],
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
        v-if="isGrouped"
        class="collection-virtual-grid-window"
        :style="{ transform: `translateY(${groupedVisible.offsetY}px)` }"
      >
        <template v-for="block in groupedVisible.blocks" :key="block.key">
          <div
            v-if="block.type === 'header'"
            class="catalog-gallery-group-header"
            :style="{ height: `${block.height}px` }"
          >
            <ManaSymbols
              v-if="block.group.groupBy === 'color'"
              class="storage-set-group-pips"
              :colors="block.group.pips"
              :size="16"
            />
            <h3 class="storage-set-group-title">{{ block.group.label }}</h3>
            <ul
              v-if="block.group.valueBands?.length"
              class="catalog-gallery-group-bands"
            >
              <li
                v-for="band in block.group.valueBands"
                :key="band.key"
                class="catalog-gallery-group-band"
                :style="{ background: band.tint }"
                :title="`${band.label}: ${band.count}`"
              >
                <span class="catalog-gallery-group-band-label">{{ band.label }}</span>
                <span class="catalog-gallery-group-band-count">{{ band.count }}</span>
              </li>
            </ul>
            <span class="storage-set-group-meta">{{ groupMetaText(block.group) }}</span>
          </div>
          <div
            v-else
            class="catalog-virtual-card-row"
            :style="{ height: `${block.height}px` }"
          >
            <CollectionCardGrid
              :cards="block.cards"
              :columns="columnCount"
              :show-unowned-badge="showUnownedBadge"
              :show-set-label="showSetLabel"
              :set-label-for="setLabelFor"
              :card-scale="cardScale"
              :browse-names="browseNames"
              :selected-name="selectedName"
              :selectable="selectable"
              :selected-keys="selectedKeys"
              :focused-index="focusedIndex >= 0 ? focusedIndex - block.globalStart : -1"
              :start-index="block.globalStart"
              :price-strategy="priceStrategy"
              :show-favorites="showFavorites"
              :zoom-only="zoomOnly"
              :price-tile-tint="priceTileTint"
              @toggle-select="emit('toggle-select', $event)"
              @focus-index="emit('focus-index', $event)"
              @browse-name="emit('browse-name', $event)"
              @cycle-variant="emit('cycle-variant', $event)"
              @ownership-changed="emit('ownership-changed')"
              @favorite-changed="emit('favorite-changed', $event)"
            />
          </div>
        </template>
      </div>
      <div
        v-else
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
          :show-favorites="showFavorites"
          :zoom-only="zoomOnly"
          :price-tile-tint="priceTileTint"
          @toggle-select="emit('toggle-select', $event)"
          @focus-index="emit('focus-index', $event)"
          @browse-name="emit('browse-name', $event)"
          @cycle-variant="emit('cycle-variant', $event)"
          @ownership-changed="emit('ownership-changed')"
          @favorite-changed="emit('favorite-changed', $event)"
        />
      </div>
    </div>
  </div>
</template>
