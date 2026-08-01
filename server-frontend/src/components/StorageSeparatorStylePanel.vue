<script setup>
import { computed } from "vue";

import SeparatorColorControls from "./SeparatorColorControls.vue";
import SeparatorStyleSection from "./SeparatorStyleSection.vue";
import {
  DEFAULT_STORAGE_SEPARATOR_STYLE,
  normalizeStorageSeparatorStyle,
  STORAGE_FONT_OPTIONS,
  STORAGE_HEADER_ALIGNS,
  STORAGE_ICON_OFFSET_MAX_MM,
  STORAGE_ICON_OFFSET_MIN_MM,
  STORAGE_ICON_SCALES,
  STORAGE_META_FORMATS,
  STORAGE_NAME_SCALES,
  STORAGE_TAB_HEIGHT_MAX_MM,
  STORAGE_TAB_HEIGHT_MIN_MM,
} from "../utils/storageSeparatorStyle";

const model = defineModel({
  type: Object,
  required: true,
});

function patch(partial) {
  model.value = normalizeStorageSeparatorStyle({
    ...model.value,
    ...partial,
  });
}

function resetStyle() {
  model.value = { ...DEFAULT_STORAGE_SEPARATOR_STYLE };
}

const metaLabels = {
  yearCode: "Year - code",
  codeYear: "Code - year",
  year: "Year only",
  code: "Code only",
  none: "Hidden",
};

const scaleLabels = {
  sm: "Small",
  md: "Medium",
  lg: "Large",
};

const alignLabels = {
  left: "Left",
  center: "Center",
};

const layoutSummary = computed(() => {
  const bits = [`${model.value.tabHeightMm} mm`, alignLabels[model.value.headerAlign] || "Left"];
  return bits.join(" · ");
});

const iconSummary = computed(() => {
  if (!model.value.showIcon) {
    return "Hidden";
  }
  const size = scaleLabels[model.value.iconScale] || model.value.iconScale;
  const offset = Number(model.value.iconOffsetMm) || 0;
  return offset ? `${size} · ${offset} mm` : size;
});

const textSummary = computed(() => {
  const name = scaleLabels[model.value.nameScale] || model.value.nameScale;
  const meta = metaLabels[model.value.metaFormat] || model.value.metaFormat;
  return `${name} · ${meta}`;
});

const fontSummary = computed(
  () =>
    STORAGE_FONT_OPTIONS.find((option) => option.id === model.value.fontFamily)?.label
    || model.value.fontFamily,
);
</script>

<template>
  <section class="binder-style-panel" aria-label="Storage separator style">
    <div class="binder-style-panel-header">
      <h3 class="binder-style-panel-title">Header style</h3>
      <button type="button" class="btn btn-secondary btn-small" @click="resetStyle">
        Reset
      </button>
    </div>

    <SeparatorColorControls
      mode="storage"
      :colors="{
        tabColor: model.tabColor,
        nameColor: model.nameColor,
        metaColor: model.metaColor,
        borderColor: model.borderColor,
      }"
      @apply="patch"
    />

    <SeparatorStyleSection title="Layout" :summary="layoutSummary">
      <label class="binder-style-field binder-style-field--stack">
        <span>Top height ({{ model.tabHeightMm }} mm)</span>
        <input
          type="range"
          :min="STORAGE_TAB_HEIGHT_MIN_MM"
          :max="STORAGE_TAB_HEIGHT_MAX_MM"
          step="1"
          :value="model.tabHeightMm"
          @input="patch({ tabHeightMm: Number($event.target.value) })"
        />
      </label>
      <label class="binder-style-field">
        <span>Content align</span>
        <select
          :value="model.headerAlign"
          @change="patch({ headerAlign: $event.target.value })"
        >
          <option
            v-for="id in STORAGE_HEADER_ALIGNS"
            :key="id"
            :value="id"
          >
            {{ alignLabels[id] }}
          </option>
        </select>
      </label>
    </SeparatorStyleSection>

    <SeparatorStyleSection title="Icon" :summary="iconSummary">
      <label class="binder-style-check">
        <input
          type="checkbox"
          :checked="model.showIcon"
          @change="patch({ showIcon: $event.target.checked })"
        />
        <span>Show set icon</span>
      </label>
      <label class="binder-style-field">
        <span>Icon size</span>
        <select
          :value="model.iconScale"
          :disabled="!model.showIcon"
          @change="patch({ iconScale: $event.target.value })"
        >
          <option
            v-for="id in STORAGE_ICON_SCALES"
            :key="id"
            :value="id"
          >
            {{ scaleLabels[id] }}
          </option>
        </select>
      </label>
      <label class="binder-style-field binder-style-field--stack">
        <span>Icon offset ({{ model.iconOffsetMm }} mm)</span>
        <input
          type="range"
          :min="STORAGE_ICON_OFFSET_MIN_MM"
          :max="STORAGE_ICON_OFFSET_MAX_MM"
          step="0.5"
          :value="model.iconOffsetMm"
          :disabled="!model.showIcon"
          @input="patch({ iconOffsetMm: Number($event.target.value) })"
        />
      </label>
    </SeparatorStyleSection>

    <SeparatorStyleSection title="Text" :summary="textSummary">
      <label class="binder-style-field">
        <span>Name size</span>
        <select
          :value="model.nameScale"
          @change="patch({ nameScale: $event.target.value })"
        >
          <option
            v-for="id in STORAGE_NAME_SCALES"
            :key="id"
            :value="id"
          >
            {{ scaleLabels[id] }}
          </option>
        </select>
      </label>
      <label class="binder-style-field">
        <span>Meta line</span>
        <select
          :value="model.metaFormat"
          @change="patch({ metaFormat: $event.target.value })"
        >
          <option
            v-for="id in STORAGE_META_FORMATS"
            :key="id"
            :value="id"
          >
            {{ metaLabels[id] }}
          </option>
        </select>
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
            v-for="option in STORAGE_FONT_OPTIONS"
            :key="option.id"
            :value="option.id"
          >
            {{ option.label }}
          </option>
        </select>
      </label>
    </SeparatorStyleSection>
  </section>
</template>
