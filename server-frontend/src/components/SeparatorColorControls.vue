<script setup>
import { computed, ref } from "vue";

import { SEPARATOR_COLOR_PRESETS } from "../utils/separatorColorPresets";

const props = defineProps({
  /** "binder" | "storage" */
  mode: {
    type: String,
    required: true,
    validator: (value) => value === "binder" || value === "storage",
  },
  colors: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["apply"]);

const colorsOpen = ref(false);
const customOpen = ref(false);

const binderFields = [
  { key: "inkColor", label: "Ink" },
  { key: "accentColor", label: "Accent" },
  { key: "baseColor", label: "Base" },
];

const storageFields = [
  { key: "tabColor", label: "Tab" },
  { key: "nameColor", label: "Name" },
  { key: "metaColor", label: "Meta" },
  { key: "borderColor", label: "Border" },
];

const fields = computed(() =>
  props.mode === "binder" ? binderFields : storageFields,
);

const previewSwatches = computed(() =>
  fields.value.map((field) => props.colors?.[field.key] || "#cccccc"),
);

const activePresetId = computed(() => {
  const presetKey = props.mode;
  return SEPARATOR_COLOR_PRESETS.find((preset) => {
    const colors = preset[presetKey];
    return fields.value.every(
      (field) =>
        String(colors[field.key] || "").toLowerCase()
        === String(props.colors?.[field.key] || "").toLowerCase(),
    );
  })?.id || "";
});

function applyPreset(preset) {
  emit("apply", { ...preset[props.mode] });
}

function onCustomColor(key, value) {
  emit("apply", { [key]: value });
}
</script>

<template>
  <div class="binder-style-group separator-color-section">
    <button
      type="button"
      class="binder-style-group-toggle"
      :aria-expanded="colorsOpen ? 'true' : 'false'"
      @click="colorsOpen = !colorsOpen"
    >
      <span class="binder-style-group-title">Colors</span>
      <span class="separator-color-preview" aria-hidden="true">
        <span
          v-for="(swatch, index) in previewSwatches"
          :key="index"
          class="separator-color-preview-swatch"
          :style="{ background: swatch }"
        />
      </span>
      <span class="binder-style-group-chevron">{{ colorsOpen ? "▾" : "▸" }}</span>
    </button>

    <div v-if="colorsOpen" class="separator-color-body">
      <div class="separator-color-presets" role="listbox" aria-label="Color presets">
        <button
          v-for="preset in SEPARATOR_COLOR_PRESETS"
          :key="preset.id"
          type="button"
          class="separator-color-preset"
          role="option"
          :aria-selected="activePresetId === preset.id ? 'true' : 'false'"
          :class="{ 'is-active': activePresetId === preset.id }"
          :title="preset.label"
          @click="applyPreset(preset)"
        >
          <span class="separator-color-preset-swatches" aria-hidden="true">
            <span
              v-for="(field, index) in fields"
              :key="field.key"
              class="separator-color-preset-chip"
              :class="{ 'separator-color-preset-chip--wide': index === 0 }"
              :style="{ background: preset[mode][field.key] }"
            />
          </span>
          <span class="separator-color-preset-label">{{ preset.label }}</span>
        </button>
      </div>

      <button
        type="button"
        class="separator-color-custom-toggle"
        :aria-expanded="customOpen ? 'true' : 'false'"
        @click="customOpen = !customOpen"
      >
        Custom colors
        <span>{{ customOpen ? "▾" : "▸" }}</span>
      </button>

      <div v-if="customOpen" class="separator-color-custom">
        <label
          v-for="field in fields"
          :key="field.key"
          class="binder-style-field"
        >
          <span>{{ field.label }}</span>
          <input
            type="color"
            :value="colors[field.key]"
            @input="onCustomColor(field.key, $event.target.value)"
          />
        </label>
      </div>
    </div>
  </div>
</template>
