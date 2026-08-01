<script setup>
import SeparatorColorControls from "./SeparatorColorControls.vue";
import {
  BINDER_BORDER_STYLES,
  BINDER_FONT_OPTIONS,
  BINDER_TITLE_SCALES,
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
</script>

<template>
  <section class="binder-style-panel" aria-label="Binder separator style">
    <div class="binder-style-panel-header">
      <h3 class="binder-style-panel-title">Style</h3>
      <button type="button" class="btn btn-secondary btn-small" @click="resetStyle">
        Reset
      </button>
    </div>

    <SeparatorColorControls
      mode="binder"
      :colors="{
        inkColor: model.inkColor,
        accentColor: model.accentColor,
        baseColor: model.baseColor,
      }"
      @apply="patch"
    />

    <div class="binder-style-group">
      <h4 class="binder-style-group-title">Effects</h4>
      <label class="binder-style-field binder-style-field--stack">
        <span>Parchment opacity ({{ model.parchmentOpacity }}%)</span>
        <input
          type="range"
          min="0"
          max="100"
          :value="model.parchmentOpacity"
          @input="patch({ parchmentOpacity: Number($event.target.value) })"
        />
      </label>
      <label class="binder-style-field binder-style-field--stack">
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
      <label class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.uniqueParchment"
          @change="patch({ uniqueParchment: $event.target.checked })"
        />
        <span>Unique parchment crop</span>
      </label>
    </div>

    <div class="binder-style-group">
      <h4 class="binder-style-group-title">Borders</h4>
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
    </div>

    <div class="binder-style-group">
      <h4 class="binder-style-group-title">Font</h4>
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
    </div>
  </section>
</template>
