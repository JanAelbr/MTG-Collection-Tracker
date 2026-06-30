<script setup>
import { computed } from "vue";
import SetGallery from "./SetGallery.vue";
import { usePricingSettings } from "../composables/pricingSettings";
import { formatSetDropdownLabel } from "../utils/format";

const props = defineProps({
  sets: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  label: { type: String, default: "Set" },
  layout: {
    type: String,
    default: "dropdown",
    validator: (value) => value === "dropdown" || value === "banner",
  },
  showFavorites: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "toggleFavorite"]);

const { settings } = usePricingSettings();

const useBrowser = computed(() => settings.value?.setPickerMode === "browser");

function onSelect(setCode) {
  emit("update:modelValue", setCode);
}

function onChange(event) {
  emit("update:modelValue", event.target.value);
}

function onToggleFavorite(set) {
  emit("toggleFavorite", set);
}
</script>

<template>
  <div
    v-if="layout === 'banner' && useBrowser"
    class="set-gallery-wrap"
  >
    <SetGallery
      :sets="sets"
      :active-set-code="modelValue"
      :show-favorites="showFavorites"
      @select="onSelect"
      @toggle-favorite="onToggleFavorite"
    />
  </div>

  <label
    v-else-if="layout === 'dropdown' && !useBrowser"
    class="manager-filter set-picker-dropdown"
  >
    <span>{{ label }}</span>
    <select :value="modelValue" @change="onChange">
      <option v-for="set in sets" :key="set.setCode" :value="set.setCode">
        {{ formatSetDropdownLabel(set) }}
      </option>
    </select>
  </label>
</template>
