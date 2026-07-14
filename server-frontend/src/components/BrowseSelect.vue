<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  filterable: { type: Boolean, default: false },
  showIcons: { type: Boolean, default: false },
  optionalIcons: { type: Boolean, default: false },
  placeholder: { type: String, default: "Select…" },
  ariaLabel: { type: String, default: "Select option" },
  hideArrows: { type: Boolean, default: false },
  emptyIconLabel: { type: String, default: "" },
  portalPanel: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const open = ref(false);
const filter = ref("");
const mainRef = ref(null);
const triggerRef = ref(null);
const panelRef = ref(null);
const filterRef = ref(null);
const panelStyle = ref({});

const optionValues = computed(() => props.options.map((option) => option.value));

const activeIndex = computed(() => optionValues.value.indexOf(props.modelValue));

const activeOption = computed(() => {
  if (activeIndex.value < 0) {
    return null;
  }
  return props.options[activeIndex.value];
});

const activeLabel = computed(() => activeOption.value?.label || props.placeholder);

const filteredOptions = computed(() => {
  const query = filter.value.trim().toLowerCase();
  if (!query) {
    return props.options;
  }
  return props.options.filter((option) => {
    const haystack = [
      option.label,
      option.value,
      option.searchText,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
});

const filterBlocksSelection = computed(
  () => Boolean(filter.value.trim()) && filteredOptions.value.length === 0,
);

const canGoPrev = computed(() => !props.disabled && !filterBlocksSelection.value && activeIndex.value > 0);

const canGoNext = computed(
  () => !props.disabled
    && !filterBlocksSelection.value
    && activeIndex.value >= 0
    && activeIndex.value < optionValues.value.length - 1,
);

function select(value) {
  emit("update:modelValue", value);
  closePanel();
}

function goPrev() {
  if (!canGoPrev.value) {
    return;
  }
  emit("update:modelValue", optionValues.value[activeIndex.value - 1]);
}

function goNext() {
  if (!canGoNext.value) {
    return;
  }
  emit("update:modelValue", optionValues.value[activeIndex.value + 1]);
}

function closePanel() {
  open.value = false;
  filter.value = "";
  panelStyle.value = {};
}

function updatePanelPosition() {
  if (!props.portalPanel || !open.value || !triggerRef.value) {
    return;
  }
  const rect = triggerRef.value.getBoundingClientRect();
  const panelWidth = Math.min(320, Math.max(rect.width, 220), window.innerWidth - 16);
  let left = rect.left;
  if (left + panelWidth + 8 > window.innerWidth) {
    left = Math.max(8, window.innerWidth - panelWidth - 8);
  }
  panelStyle.value = {
    top: `${rect.bottom + 4}px`,
    left: `${left}px`,
    width: `${panelWidth}px`,
  };
}

async function openPanel() {
  if (props.disabled) {
    return;
  }
  open.value = true;
  await nextTick();
  updatePanelPosition();
  filterRef.value?.focus();
}

function togglePanel() {
  if (open.value) {
    closePanel();
    return;
  }
  openPanel();
}

function onDocumentClick(event) {
  if (!open.value) {
    return;
  }
  const target = event.target;
  if (mainRef.value?.contains(target) || panelRef.value?.contains(target)) {
    return;
  }
  closePanel();
}

function onViewportChange() {
  updatePanelPosition();
}

function onDocumentKeydown(event) {
  if (event.key === "Escape" && open.value) {
    closePanel();
  }
}

watch(
  () => open.value,
  (isOpen) => {
    if (!props.portalPanel) {
      return;
    }
    if (isOpen) {
      window.addEventListener("resize", onViewportChange);
      window.addEventListener("scroll", onViewportChange, true);
      return;
    }
    window.removeEventListener("resize", onViewportChange);
    window.removeEventListener("scroll", onViewportChange, true);
  },
);

watch(
  () => props.modelValue,
  () => {
    if (props.disabled) {
      closePanel();
    }
  },
);

onMounted(() => {
  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", onDocumentKeydown);
});

onUnmounted(() => {
  document.removeEventListener("click", onDocumentClick);
  document.removeEventListener("keydown", onDocumentKeydown);
  window.removeEventListener("resize", onViewportChange);
  window.removeEventListener("scroll", onViewportChange, true);
});
</script>

<template>
  <div class="browse-select" :class="{ 'is-disabled': disabled, 'is-open': open, 'hide-arrows': hideArrows }">
    <button
      v-if="!hideArrows"
      type="button"
      class="browse-select-arrow"
      :disabled="!canGoPrev"
      aria-label="Previous option"
      @click="goPrev"
    >
      ‹
    </button>

    <div ref="mainRef" class="browse-select-main">
      <button
        ref="triggerRef"
        type="button"
        class="browse-select-trigger"
        :disabled="disabled"
        :aria-label="ariaLabel"
        :aria-expanded="open ? 'true' : 'false'"
        aria-haspopup="listbox"
        @click="togglePanel"
      >
        <span
          v-if="showIcons && (!optionalIcons || activeOption?.iconSrc || emptyIconLabel)"
          class="browse-select-icon-wrap"
          aria-hidden="true"
        >
          <img
            v-if="activeOption?.iconSrc"
            :src="activeOption.iconSrc"
            alt=""
            class="browse-select-icon"
          >
          <span v-else class="browse-select-icon browse-select-icon-placeholder">
            {{ emptyIconLabel || (activeOption?.value === "All" || !activeOption?.iconSrc ? "All" : "?") }}
          </span>
        </span>
        <span class="browse-select-label">{{ activeLabel }}</span>
        <span class="browse-select-chevron" aria-hidden="true">▾</span>
      </button>

      <Teleport v-if="portalPanel" to="body" :disabled="!open">
        <div
          v-if="open"
          ref="panelRef"
          class="browse-select-panel is-portaled"
          :style="panelStyle"
          role="presentation"
        >
          <input
            v-if="filterable"
            ref="filterRef"
            v-model="filter"
            type="search"
            class="browse-select-filter"
            placeholder="Filter…"
            aria-label="Filter options"
            @click.stop
          >
          <ul class="browse-select-list" role="listbox" :aria-label="ariaLabel">
            <li
              v-for="option in filteredOptions"
              :key="option.value || '__empty__'"
              class="browse-select-option"
              role="option"
              :aria-selected="option.value === modelValue ? 'true' : 'false'"
              :class="{ active: option.value === modelValue }"
              @click="select(option.value)"
            >
              <span
                v-if="showIcons && (!optionalIcons || option.iconSrc)"
                class="browse-select-icon-wrap"
                aria-hidden="true"
              >
                <img
                  v-if="option.iconSrc"
                  :src="option.iconSrc"
                  alt=""
                  class="browse-select-icon"
                >
                <span v-else-if="!optionalIcons" class="browse-select-icon browse-select-icon-placeholder">
                  {{ option.value === "All" || !option.iconSrc ? "All" : "?" }}
                </span>
              </span>
              <span class="browse-select-option-label">{{ option.label }}</span>
            </li>
            <li v-if="!filteredOptions.length" class="browse-select-empty">
              No matches
            </li>
          </ul>
        </div>
      </Teleport>

      <div v-else-if="open" class="browse-select-panel" role="presentation">
        <input
          v-if="filterable"
          ref="filterRef"
          v-model="filter"
          type="search"
          class="browse-select-filter"
          placeholder="Filter…"
          aria-label="Filter options"
          @click.stop
        >
        <ul class="browse-select-list" role="listbox" :aria-label="ariaLabel">
          <li
            v-for="option in filteredOptions"
            :key="option.value || '__empty__'"
            class="browse-select-option"
            role="option"
            :aria-selected="option.value === modelValue ? 'true' : 'false'"
            :class="{ active: option.value === modelValue }"
            @click="select(option.value)"
          >
            <span
              v-if="showIcons && (!optionalIcons || option.iconSrc)"
              class="browse-select-icon-wrap"
              aria-hidden="true"
            >
              <img
                v-if="option.iconSrc"
                :src="option.iconSrc"
                alt=""
                class="browse-select-icon"
              >
              <span v-else-if="!optionalIcons" class="browse-select-icon browse-select-icon-placeholder">
                {{ option.value === "All" || !option.iconSrc ? "All" : "?" }}
              </span>
            </span>
            <span class="browse-select-option-label">{{ option.label }}</span>
          </li>
          <li v-if="!filteredOptions.length" class="browse-select-empty">
            No matches
          </li>
        </ul>
      </div>
    </div>

    <button
      v-if="!hideArrows"
      type="button"
      class="browse-select-arrow"
      :disabled="!canGoNext"
      aria-label="Next option"
      @click="goNext"
    >
      ›
    </button>
  </div>
</template>
