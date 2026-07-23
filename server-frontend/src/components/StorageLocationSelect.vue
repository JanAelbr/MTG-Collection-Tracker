<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import StorageLocationIcon from "./StorageLocationIcon.vue";
import {
  findStorageLocation,
  groupStorageLocations,
} from "../utils/storageLocationGroups";

const props = defineProps({
  modelValue: { type: String, default: "" },
  locations: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  ariaLabel: { type: String, default: "Storage location" },
  /** Limit options to these location types (e.g. storage, binder). Empty = all. */
  includeTypes: { type: Array, default: () => [] },
  /** Render the menu in a body portal so it isn't clipped by card/overflow parents. */
  portalPanel: { type: Boolean, default: true },
});

const emit = defineEmits(["update:modelValue", "change", "open-change"]);

const open = ref(false);
const rootRef = ref(null);
const triggerRef = ref(null);
const menuRef = ref(null);
const menuStyle = ref({});

const filteredLocations = computed(() => {
  const allowed = new Set(
    (props.includeTypes || []).map((type) => String(type).toLowerCase()).filter(Boolean),
  );
  if (!allowed.size) {
    return props.locations;
  }
  return props.locations.filter((location) => {
    if (allowed.has(String(location.locationType || "").toLowerCase())) {
      return true;
    }
    // Keep the current value visible even if filtered out (e.g. legacy deck location).
    return location.slug === props.modelValue;
  });
});

const groupedSections = computed(() => groupStorageLocations(filteredLocations.value));
const selectedLocation = computed(() =>
  findStorageLocation(props.locations, props.modelValue),
);

function setOpen(next) {
  if (open.value === next) {
    return;
  }
  open.value = next;
  emit("open-change", next);
}

function updateMenuPosition() {
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
  const openUp = spaceBelow < 180 && spaceAbove > spaceBelow;
  const maxHeight = Math.min(280, Math.max(120, openUp ? spaceAbove : spaceBelow));

  if (openUp) {
    menuStyle.value = {
      top: "auto",
      bottom: `${window.innerHeight - rect.top + 4}px`,
      left: `${left}px`,
      width: `${panelWidth}px`,
      maxHeight: `${maxHeight}px`,
    };
  } else {
    menuStyle.value = {
      top: `${rect.bottom + 4}px`,
      bottom: "auto",
      left: `${left}px`,
      width: `${panelWidth}px`,
      maxHeight: `${maxHeight}px`,
    };
  }
}

async function openMenu() {
  if (props.disabled || !filteredLocations.value.length) {
    return;
  }
  setOpen(true);
  await nextTick();
  updateMenuPosition();
}

function close() {
  setOpen(false);
  menuStyle.value = {};
}

function toggleOpen() {
  if (open.value) {
    close();
    return;
  }
  openMenu();
}

function selectLocation(slug) {
  if (slug !== props.modelValue) {
    emit("update:modelValue", slug);
    emit("change", slug);
  }
  close();
}

function onDocumentPointerDown(event) {
  if (!open.value) {
    return;
  }
  const target = event.target;
  if (rootRef.value?.contains(target) || menuRef.value?.contains(target)) {
    return;
  }
  close();
}

function onKeydown(event) {
  if (event.key === "Escape" && open.value) {
    close();
  }
}

function onViewportChange() {
  updateMenuPosition();
}

watch(open, (isOpen) => {
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
});

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onKeydown);
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onKeydown);
  window.removeEventListener("resize", onViewportChange);
  window.removeEventListener("scroll", onViewportChange, true);
});
</script>

<template>
  <div
    ref="rootRef"
    class="storage-location-picker"
    :class="{
      'storage-location-picker--compact': compact,
      'storage-location-picker--open': open,
      'storage-location-picker--disabled': disabled,
    }"
    @click.stop
    @mousedown.stop
  >
    <button
      ref="triggerRef"
      type="button"
      class="storage-location-picker-trigger"
      :disabled="disabled || !filteredLocations.length"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggleOpen"
    >
      <StorageLocationIcon
        v-if="selectedLocation"
        :type="selectedLocation.locationType"
      />
      <span class="storage-location-picker-label">
        {{ selectedLocation?.label || "Select location" }}
      </span>
      <span class="storage-location-picker-chevron" aria-hidden="true">▾</span>
    </button>

    <Teleport v-if="portalPanel" to="body" :disabled="!open">
      <div
        v-if="open"
        ref="menuRef"
        class="storage-location-picker-menu is-portaled"
        :style="menuStyle"
        role="listbox"
        :aria-label="ariaLabel"
        @click.stop
        @mousedown.stop
      >
        <template v-for="(section, sectionIndex) in groupedSections" :key="section.type">
          <div
            v-if="sectionIndex > 0"
            class="storage-location-picker-divider"
            role="separator"
          />
          <div class="storage-location-picker-section">
            <div class="storage-location-picker-section-heading">
              <StorageLocationIcon :type="section.type" />
              <span>{{ section.label }}</span>
            </div>
            <button
              v-for="location in section.locations"
              :key="location.slug"
              type="button"
              class="storage-location-picker-option"
              :class="{ 'is-selected': location.slug === modelValue }"
              role="option"
              :aria-selected="location.slug === modelValue"
              @click="selectLocation(location.slug)"
            >
              <StorageLocationIcon :type="location.locationType" />
              <span class="storage-location-picker-option-label">{{ location.label }}</span>
            </button>
          </div>
        </template>
      </div>
    </Teleport>

    <div
      v-else-if="open"
      ref="menuRef"
      class="storage-location-picker-menu"
      role="listbox"
      :aria-label="ariaLabel"
    >
      <template v-for="(section, sectionIndex) in groupedSections" :key="section.type">
        <div
          v-if="sectionIndex > 0"
          class="storage-location-picker-divider"
          role="separator"
        />
        <div class="storage-location-picker-section">
          <div class="storage-location-picker-section-heading">
            <StorageLocationIcon :type="section.type" />
            <span>{{ section.label }}</span>
          </div>
          <button
            v-for="location in section.locations"
            :key="location.slug"
            type="button"
            class="storage-location-picker-option"
            :class="{ 'is-selected': location.slug === modelValue }"
            role="option"
            :aria-selected="location.slug === modelValue"
            @click="selectLocation(location.slug)"
          >
            <StorageLocationIcon :type="location.locationType" />
            <span class="storage-location-picker-option-label">{{ location.label }}</span>
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
