<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import CardPreview from "./CardPreview.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import PriceStrategyValue from "./PriceStrategyValue.vue";
import { cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import { formatEuro } from "../utils/format";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  sortField: { type: String, default: "value" },
  sortDir: { type: String, default: "desc" },
  showRemove: { type: Boolean, default: true },
  lineTotal: { type: Function, required: true },
  setLabelFor: { type: Function, default: null },
  setIconFor: { type: Function, default: null },
});

const emit = defineEmits(["sort", "remove-one"]);

const ROW_HEIGHT = 48;
const OVERSCAN = 10;

const rootRef = ref(null);
const viewportHeight = ref(480);
const scrollTop = ref(0);

const columns = computed(() => {
  const cols = [
    { field: "set", label: "Set" },
    { field: "number", label: "#" },
    { field: "name", label: "Card" },
    { field: "artStyle", label: "Art Style" },
    { field: "finish", label: "Finish" },
    { field: "copies", label: "Copies" },
    { field: "value", label: "Total value" },
  ];
  if (props.showRemove) {
    cols.push({ field: "", label: "" });
  }
  return cols;
});

const colSpan = computed(() => columns.value.length);

const visibleRange = computed(() => {
  if (!props.cards.length) {
    return { start: 0, end: 0, padTop: 0, padBottom: 0 };
  }
  const start = Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight.value / ROW_HEIGHT) + OVERSCAN * 2;
  const end = Math.min(props.cards.length, start + visibleCount);
  return {
    start,
    end,
    padTop: start * ROW_HEIGHT,
    padBottom: Math.max(0, (props.cards.length - end) * ROW_HEIGHT),
  };
});

const visibleCards = computed(() =>
  props.cards.slice(visibleRange.value.start, visibleRange.value.end).map((card, index) => ({
    card,
    absoluteIndex: visibleRange.value.start + index,
  })),
);

function cardRoute(card) {
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function cardKey(card) {
  return `${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`;
}

function setLabel(card) {
  if (props.setLabelFor) {
    return props.setLabelFor(card.setCode) || card.setCode;
  }
  return card.setCode;
}

function setIcon(card) {
  if (props.setIconFor) {
    return props.setIconFor(card.setCode);
  }
  return null;
}

function sortIndicator(field) {
  if (!field || props.sortField !== field) {
    return "";
  }
  return props.sortDir === "asc" ? " ↑" : " ↓";
}

function onHeaderClick(field) {
  if (!field) {
    return;
  }
  emit("sort", field);
}

function onScroll(event) {
  scrollTop.value = event.target.scrollTop;
}

function measureLayout() {
  const root = rootRef.value;
  if (!root) {
    return;
  }
  viewportHeight.value = Math.max(200, root.clientHeight);
  scrollTop.value = root.scrollTop;
}

let resizeObserver = null;

watch(
  () => props.cards.length,
  () => {
    nextTick(measureLayout);
  },
);

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

defineExpose({ rootRef });
</script>

<template>
  <div ref="rootRef" class="storage-virtual-table" @scroll="onScroll">
    <table class="storage-table storage-table--virtual">
      <colgroup>
        <col class="storage-col-set">
        <col class="storage-col-number">
        <col class="storage-col-name">
        <col class="storage-col-art">
        <col class="storage-col-finish">
        <col class="storage-col-copies">
        <col class="storage-col-value">
        <col v-if="showRemove" class="storage-col-actions">
      </colgroup>
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.field || 'actions'"
            :class="{
              'is-sortable': Boolean(column.field),
              'is-sorted': column.field && sortField === column.field,
            }"
            scope="col"
          >
            <button
              v-if="column.field"
              type="button"
              class="storage-table-sort-btn"
              @click="onHeaderClick(column.field)"
            >
              {{ column.label }}{{ sortIndicator(column.field) }}
            </button>
            <span v-else class="visually-hidden">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="visibleRange.padTop" aria-hidden="true" class="storage-virtual-pad">
          <td :colspan="colSpan" :style="{ height: `${visibleRange.padTop}px`, padding: 0, border: 0 }" />
        </tr>
        <tr
          v-for="entry in visibleCards"
          :key="cardKey(entry.card)"
          :class="{ 'is-alt': entry.absoluteIndex % 2 === 1 }"
        >
          <td>
            <span class="storage-table-set-cell">
              <img
                v-if="setIcon(entry.card)"
                class="storage-table-set-icon"
                :src="setIcon(entry.card)"
                alt=""
                loading="lazy"
              >
              <CollectionSetLink
                :set-code="entry.card.setCode"
                :label="setLabel(entry.card)"
              />
            </span>
          </td>
          <td>{{ entry.card.collectorNumber }}</td>
          <td>
            <CardPreview
              :image-uri="entry.card.imageUri"
              :image-uri-back="entry.card.imageUriBack || ''"
            >
              <span class="storage-card-name-row">
                <RouterLink :to="cardRoute(entry.card)" class="reports-card-link">
                  {{ String(entry.card.collectorNumber).padStart(3, "0") }} · {{ entry.card.name || entry.card.cardName }}
                </RouterLink>
                <CardFinishBadge :card="entry.card" compact />
              </span>
            </CardPreview>
          </td>
          <td>{{ entry.card.artStyle || "—" }}</td>
          <td>{{ finishLabel(cardFinish(entry.card)) }}</td>
          <td>{{ entry.card.copyCount }}</td>
          <td>
            <PriceStrategyValue
              v-if="entry.card.copyCount <= 1"
              :card="entry.card"
              :value="lineTotal(entry.card)"
            />
            <span v-else>{{ formatEuro(lineTotal(entry.card)) }}</span>
            <span
              v-if="entry.card.copyCount > 1 && entry.card.currentValue != null"
              class="storage-unit-value"
            >
              <PriceStrategyValue :card="entry.card" tag="span" />
              <span class="storage-unit-value-suffix"> each</span>
            </span>
          </td>
          <td v-if="showRemove" class="storage-row-actions">
            <button
              type="button"
              class="btn btn-small"
              @click="emit('remove-one', entry.card)"
            >
              Remove one
            </button>
          </td>
        </tr>
        <tr v-if="visibleRange.padBottom" aria-hidden="true" class="storage-virtual-pad">
          <td :colspan="colSpan" :style="{ height: `${visibleRange.padBottom}px`, padding: 0, border: 0 }" />
        </tr>
      </tbody>
    </table>
  </div>
</template>
