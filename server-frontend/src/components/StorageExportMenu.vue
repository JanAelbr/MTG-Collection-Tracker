<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";

import {
  STORAGE_EXPORT_FORMATS,
  defaultExportBasename,
  runStorageExport,
} from "../utils/storageExport";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  isGrouped: { type: Boolean, default: false },
  locationLabels: { type: String, default: "storage" },
  disabled: { type: Boolean, default: false },
});

const open = ref(false);
const root = ref(null);
const activeIndex = ref(0);
const error = ref("");

const formats = STORAGE_EXPORT_FORMATS;
const hasCards = computed(() => (props.cards || []).some((card) => (Number(card.copyCount) || 0) > 0));

function close() {
  open.value = false;
  error.value = "";
}

function toggle() {
  if (props.disabled || !hasCards.value) {
    return;
  }
  open.value = !open.value;
  if (open.value) {
    activeIndex.value = 0;
  }
}

function exportFormat(formatId) {
  try {
    runStorageExport({
      formatId,
      cards: props.cards,
      groups: props.groups,
      isGrouped: props.isGrouped,
      basename: defaultExportBasename(props.locationLabels),
    });
    close();
  } catch (err) {
    error.value = err?.message || "Export failed";
  }
}

function onDocumentClick(event) {
  if (!open.value || root.value?.contains(event.target)) {
    return;
  }
  close();
}

function onKeydown(event) {
  if (!open.value) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle();
    }
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    close();
    return;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    activeIndex.value = (activeIndex.value + 1) % formats.length;
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    activeIndex.value = (activeIndex.value - 1 + formats.length) % formats.length;
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    exportFormat(formats[activeIndex.value].id);
  }
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener("click", onDocumentClick);
  } else {
    document.removeEventListener("click", onDocumentClick);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocumentClick);
});
</script>

<template>
  <div ref="root" class="storage-export-wrap" :class="{ 'is-open': open }">
    <button
      type="button"
      class="storage-export-trigger"
      :disabled="disabled || !hasCards"
      :aria-expanded="open"
      aria-haspopup="menu"
      title="Export cards"
      @click="toggle"
      @keydown="onKeydown"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          fill="currentColor"
          d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 2 5 5h-5V4zM8 13h8v2H8v-2zm0 4h8v2H8v-2z"
        />
      </svg>
      <span class="visually-hidden">Export cards</span>
    </button>
    <div
      v-if="open"
      class="card-context-menu storage-export-menu"
      role="menu"
      @keydown="onKeydown"
      @click.stop
      @pointerdown.stop
    >
      <p class="storage-export-menu-heading">Export visible cards</p>
      <button
        v-for="(format, index) in formats"
        :key="format.id"
        type="button"
        class="card-context-menu-item"
        role="menuitem"
        :class="{ 'is-selected': index === activeIndex }"
        @mouseenter="activeIndex = index"
        @click="exportFormat(format.id)"
      >
        {{ format.label }}
      </button>
      <p v-if="error" class="storage-export-menu-error">{{ error }}</p>
    </div>
  </div>
</template>
