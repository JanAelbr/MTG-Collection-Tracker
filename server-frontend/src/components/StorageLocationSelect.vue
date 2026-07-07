<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
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
});

const emit = defineEmits(["update:modelValue", "change"]);

const open = ref(false);
const rootRef = ref(null);

const groupedSections = computed(() => groupStorageLocations(props.locations));
const selectedLocation = computed(() =>
  findStorageLocation(props.locations, props.modelValue),
);

function toggleOpen() {
  if (props.disabled || !props.locations.length) {
    return;
  }
  open.value = !open.value;
}

function close() {
  open.value = false;
}

function selectLocation(slug) {
  if (slug !== props.modelValue) {
    emit("update:modelValue", slug);
    emit("change", slug);
  }
  close();
}

function onDocumentPointerDown(event) {
  if (!rootRef.value?.contains(event.target)) {
    close();
  }
}

function onKeydown(event) {
  if (event.key === "Escape") {
    close();
  }
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onKeydown);
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onKeydown);
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
      type="button"
      class="storage-location-picker-trigger"
      :disabled="disabled || !locations.length"
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

    <div
      v-if="open"
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
