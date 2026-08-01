<script setup>
import SeparatorColorControls from "./SeparatorColorControls.vue";
import {
  DEFAULT_STORAGE_SEPARATOR_STYLE,
  normalizeStorageSeparatorStyle,
  STORAGE_FONT_OPTIONS,
  STORAGE_ICON_SCALES,
  STORAGE_META_FORMATS,
  STORAGE_NAME_SCALES,
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

    <div class="binder-style-group">
      <h4 class="binder-style-group-title">Header</h4>
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
            v-for="option in STORAGE_FONT_OPTIONS"
            :key="option.id"
            :value="option.id"
          >
            {{ option.label }}
          </option>
        </select>
      </label>
    </div>
  </section>
</template>
