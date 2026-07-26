<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import StorageLocationIcon from "./StorageLocationIcon.vue";

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  filterable: { type: Boolean, default: false },
  placeholder: { type: String, default: "Select…" },
  ariaLabel: { type: String, default: "Select options" },
  portalPanel: { type: Boolean, default: false },
  /** Max selected labels shown before falling back to "N selected". */
  maxSummaryLabels: { type: Number, default: 2 },
});

const emit = defineEmits(["update:modelValue"]);

const open = ref(false);
const filter = ref("");
const mainRef = ref(null);
const triggerRef = ref(null);
const panelRef = ref(null);
const filterRef = ref(null);
const panelStyle = ref({});

const selectedSet = computed(() => new Set(props.modelValue.map((value) => String(value))));

const selectedOptions = computed(() =>
  props.options.filter((option) => selectedSet.value.has(String(option.value))),
);

const summaryLabel = computed(() => {
  const selected = selectedOptions.value;
  if (!selected.length) {
    return props.placeholder;
  }
  if (selected.length <= props.maxSummaryLabels) {
    return selected.map((option) => option.label).join(", ");
  }
  return `${selected.length} selected`;
});

const groupedOptions = computed(() => {
  const query = filter.value.trim().toLowerCase();
  const matched = !query
    ? props.options
    : props.options.filter((option) => {
      const haystack = [option.label, option.value, option.searchText, option.group]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });

  const groups = [];
  const indexByGroup = new Map();
  for (const option of matched) {
    const group = option.group || "";
    if (!indexByGroup.has(group)) {
      indexByGroup.set(group, groups.length);
      groups.push({ group, options: [] });
    }
    groups[indexByGroup.get(group)].options.push(option);
  }
  return groups;
});

const hasVisibleOptions = computed(() =>
  groupedOptions.value.some((entry) => entry.options.length),
);

function isSelected(value) {
  return selectedSet.value.has(String(value));
}

function toggle(value) {
  const key = String(value);
  const next = props.modelValue.map((item) => String(item));
  const index = next.indexOf(key);
  if (index >= 0) {
    next.splice(index, 1);
  } else {
    next.push(key);
  }
  emit("update:modelValue", next);
}

function clearAll() {
  if (!props.modelValue.length) {
    return;
  }
  emit("update:modelValue", []);
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
  const spaceBelow = window.innerHeight - rect.bottom - 8;
  const spaceAbove = rect.top - 8;
  const openUp = spaceBelow < 220 && spaceAbove > spaceBelow;
  const maxHeight = Math.min(320, Math.max(140, openUp ? spaceAbove : spaceBelow));
  if (openUp) {
    panelStyle.value = {
      top: "auto",
      bottom: `${window.innerHeight - rect.top + 4}px`,
      left: `${left}px`,
      width: `${panelWidth}px`,
      maxHeight: `${maxHeight}px`,
    };
    return;
  }
  panelStyle.value = {
    top: `${rect.bottom + 4}px`,
    left: `${left}px`,
    width: `${panelWidth}px`,
    maxHeight: `${maxHeight}px`,
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
  <div class="browse-select multi-browse-select" :class="{ 'is-disabled': disabled, 'is-open': open, 'hide-arrows': true }">
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
        <span class="browse-select-label">{{ summaryLabel }}</span>
        <span
          v-if="modelValue.length"
          class="multi-browse-select-count"
          aria-hidden="true"
        >{{ modelValue.length }}</span>
        <span class="browse-select-chevron" aria-hidden="true">▾</span>
      </button>

      <Teleport v-if="portalPanel" to="body" :disabled="!open">
        <div
          v-if="open"
          ref="panelRef"
          class="browse-select-panel multi-browse-select-panel is-portaled"
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
          <div v-if="modelValue.length" class="multi-browse-select-actions">
            <button type="button" class="multi-browse-select-clear" @click="clearAll">
              Clear all
            </button>
          </div>
          <ul class="browse-select-list" role="listbox" :aria-label="ariaLabel" aria-multiselectable="true">
            <template v-for="entry in groupedOptions" :key="entry.group || '__ungrouped__'">
              <li v-if="entry.group" class="multi-browse-select-group" role="presentation">
                {{ entry.group }}
              </li>
              <li
                v-for="option in entry.options"
                :key="option.value"
                class="browse-select-option multi-browse-select-option"
                role="option"
                :aria-selected="isSelected(option.value) ? 'true' : 'false'"
                :class="{ active: isSelected(option.value) }"
                @click="toggle(option.value)"
              >
                <span class="multi-browse-select-check" aria-hidden="true">
                  {{ isSelected(option.value) ? "✓" : "" }}
                </span>
                <StorageLocationIcon
                  v-if="option.locationType"
                  :location-type="option.locationType"
                />
                <span class="browse-select-option-label">{{ option.label }}</span>
              </li>
            </template>
            <li v-if="!hasVisibleOptions" class="browse-select-empty">
              No matches
            </li>
          </ul>
        </div>
      </Teleport>

      <div
        v-else-if="open"
        ref="panelRef"
        class="browse-select-panel multi-browse-select-panel"
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
        <div v-if="modelValue.length" class="multi-browse-select-actions">
          <button type="button" class="multi-browse-select-clear" @click="clearAll">
            Clear all
          </button>
        </div>
        <ul class="browse-select-list" role="listbox" :aria-label="ariaLabel" aria-multiselectable="true">
          <template v-for="entry in groupedOptions" :key="entry.group || '__ungrouped__'">
            <li v-if="entry.group" class="multi-browse-select-group" role="presentation">
              {{ entry.group }}
            </li>
            <li
              v-for="option in entry.options"
              :key="option.value"
              class="browse-select-option multi-browse-select-option"
              role="option"
              :aria-selected="isSelected(option.value) ? 'true' : 'false'"
              :class="{ active: isSelected(option.value) }"
              @click="toggle(option.value)"
            >
              <span class="multi-browse-select-check" aria-hidden="true">
                {{ isSelected(option.value) ? "✓" : "" }}
              </span>
              <StorageLocationIcon
                v-if="option.locationType"
                :location-type="option.locationType"
              />
              <span class="browse-select-option-label">{{ option.label }}</span>
            </li>
          </template>
          <li v-if="!hasVisibleOptions" class="browse-select-empty">
            No matches
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
