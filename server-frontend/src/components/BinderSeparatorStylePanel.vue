<script setup>
import { computed } from "vue";

import SeparatorColorControls from "./SeparatorColorControls.vue";
import SeparatorStyleSection from "./SeparatorStyleSection.vue";
import {
  applyBinderBackgroundTheme,
  BINDER_BACKGROUND_THEMES,
  BINDER_BORDER_STYLES,
  BINDER_FONT_OPTIONS,
  BINDER_TITLE_SCALES,
  binderBackgroundTheme,
  DEFAULT_BINDER_SEPARATOR_STYLE,
  normalizeBinderSeparatorStyle,
} from "../utils/binderSeparatorStyle";

const model = defineModel({
  type: Object,
  required: true,
});

function patch(partial) {
  model.value = normalizeBinderSeparatorStyle({
    ...model.value,
    ...partial,
  });
}

function setBackgroundTheme(themeId) {
  model.value = applyBinderBackgroundTheme(model.value, themeId);
}

function resetStyle() {
  model.value = { ...DEFAULT_BINDER_SEPARATOR_STYLE };
}

const borderLabels = {
  ornate: "Ornate",
  simple: "Simple",
  none: "None",
};

const titleLabels = {
  sm: "Small",
  md: "Medium",
  lg: "Large",
};

const isParchmentTheme = computed(() => model.value.backgroundTheme === "parchment");
const hasTextureBackground = computed(() => model.value.backgroundTheme !== "none");

const backgroundSummary = computed(
  () => binderBackgroundTheme(model.value.backgroundTheme).label,
);

const effectsSummary = computed(() => {
  const bits = [];
  if (model.value.softVeil && hasTextureBackground.value) {
    bits.push("Veil");
  }
  if (isParchmentTheme.value && model.value.uniqueParchment) {
    bits.push("Unique crop");
  }
  return bits.join(" · ") || "Default";
});

const bordersSummary = computed(() => {
  const style = borderLabels[model.value.borderStyle] || model.value.borderStyle;
  const bits = [style];
  if (model.value.borderStyle === "ornate") {
    if (model.value.showCorners) {
      bits.push("corners");
    }
    if (model.value.showJewels) {
      bits.push("jewels");
    }
  }
  if (model.value.showOrnament) {
    bits.push("ornament");
  }
  return bits.join(" · ");
});

const fontSummary = computed(() => {
  const family =
    BINDER_FONT_OPTIONS.find((option) => option.id === model.value.fontFamily)?.label
    || model.value.fontFamily;
  const size = titleLabels[model.value.titleScale] || model.value.titleScale;
  return `${family} · ${size}`;
});
</script>

<template>
  <section class="binder-style-panel" aria-label="Binder separator style">
    <div class="binder-style-panel-header">
      <h3 class="binder-style-panel-title">Style</h3>
      <button type="button" class="btn btn-secondary btn-small" @click="resetStyle">
        Reset
      </button>
    </div>

    <SeparatorStyleSection title="Background" :summary="backgroundSummary">
      <div class="binder-bg-theme-grid" role="listbox" aria-label="Background theme">
        <button
          v-for="theme in BINDER_BACKGROUND_THEMES"
          :key="theme.id"
          type="button"
          class="binder-bg-theme-btn"
          :class="{ 'is-active': model.backgroundTheme === theme.id }"
          role="option"
          :aria-selected="model.backgroundTheme === theme.id ? 'true' : 'false'"
          :title="theme.description"
          @click="setBackgroundTheme(theme.id)"
        >
          <span
            class="binder-bg-theme-swatch"
            :class="`binder-bg-theme-swatch--${theme.id}`"
            aria-hidden="true"
          />
          <span class="binder-bg-theme-label">{{ theme.label }}</span>
        </button>
      </div>
    </SeparatorStyleSection>

    <SeparatorColorControls
      mode="binder"
      :colors="{
        inkColor: model.inkColor,
        accentColor: model.accentColor,
        baseColor: model.baseColor,
      }"
      @apply="patch"
    />

    <SeparatorStyleSection
      v-if="hasTextureBackground"
      title="Effects"
      :summary="effectsSummary"
    >
      <label v-if="isParchmentTheme" class="binder-style-field binder-style-field--stack">
        <span>Parchment opacity ({{ model.parchmentOpacity }}%)</span>
        <input
          type="range"
          min="0"
          max="100"
          :value="model.parchmentOpacity"
          @input="patch({ parchmentOpacity: Number($event.target.value) })"
        />
      </label>
      <label v-if="isParchmentTheme" class="binder-style-field binder-style-field--stack">
        <span>Parchment softness ({{ model.parchmentSoftness }}%)</span>
        <input
          type="range"
          min="0"
          max="100"
          :value="model.parchmentSoftness"
          @input="patch({ parchmentSoftness: Number($event.target.value) })"
        />
      </label>
      <label class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.softVeil"
          @change="patch({ softVeil: $event.target.checked })"
        />
        <span>Soft center veil</span>
      </label>
      <label v-if="isParchmentTheme" class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.uniqueParchment"
          @change="patch({ uniqueParchment: $event.target.checked })"
        />
        <span>Unique parchment crop</span>
      </label>
    </SeparatorStyleSection>

    <SeparatorStyleSection title="Borders" :summary="bordersSummary">
      <label class="binder-style-field">
        <span>Style</span>
        <select
          :value="model.borderStyle"
          @change="patch({ borderStyle: $event.target.value })"
        >
          <option
            v-for="id in BINDER_BORDER_STYLES"
            :key="id"
            :value="id"
          >
            {{ borderLabels[id] }}
          </option>
        </select>
      </label>
      <label class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.showCorners"
          :disabled="model.borderStyle !== 'ornate'"
          @change="patch({ showCorners: $event.target.checked })"
        />
        <span>Corner flourishes</span>
      </label>
      <label class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.showJewels"
          :disabled="model.borderStyle !== 'ornate'"
          @change="patch({ showJewels: $event.target.checked })"
        />
        <span>Jewels</span>
      </label>
      <label class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.showOrnament"
          @change="patch({ showOrnament: $event.target.checked })"
        />
        <span>Ornament dots</span>
      </label>
    </SeparatorStyleSection>

    <SeparatorStyleSection title="Font" :summary="fontSummary">
      <label class="binder-style-field">
        <span>Family</span>
        <select
          :value="model.fontFamily"
          @change="patch({ fontFamily: $event.target.value })"
        >
          <option
            v-for="option in BINDER_FONT_OPTIONS"
            :key="option.id"
            :value="option.id"
          >
            {{ option.label }}
          </option>
        </select>
      </label>
      <label class="binder-style-field">
        <span>Title size</span>
        <select
          :value="model.titleScale"
          @change="patch({ titleScale: $event.target.value })"
        >
          <option
            v-for="id in BINDER_TITLE_SCALES"
            :key="id"
            :value="id"
          >
            {{ titleLabels[id] }}
          </option>
        </select>
      </label>
      <label class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.artStyleUppercase"
          @change="patch({ artStyleUppercase: $event.target.checked })"
        />
        <span>Art style uppercase</span>
      </label>
    </SeparatorStyleSection>
  </section>
</template>
