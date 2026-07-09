<script setup>
import { computed } from "vue";
import BrowseSelect from "./BrowseSelect.vue";
import {
  artStyleCompletionRarity,
  artStyleOptionValue,
  formatArtStyleDropdownLabel,
} from "../utils/format";
import { mtgVectorsSetIconUri } from "../utils/mtgVectors";

const props = defineProps({
  artStyles: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  setCode: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  layout: {
    type: String,
    default: "dropdown",
    validator: (value) => ["dropdown", "list"].includes(value),
  },
});

const emit = defineEmits(["update:modelValue"]);

function artStyleIconSrc(style) {
  if (!props.setCode || typeof style === "string" || !style) {
    return null;
  }
  const rarity = artStyleCompletionRarity(style);
  if (!rarity) {
    return null;
  }
  return mtgVectorsSetIconUri(props.setCode, rarity);
}

const options = computed(() => [
  { value: "", label: "All art styles", searchText: "all art styles" },
  ...props.artStyles.map((style) => {
    const value = artStyleOptionValue(style);
    return {
      value,
      label: formatArtStyleDropdownLabel(style),
      searchText: value,
      iconSrc: artStyleIconSrc(style),
    };
  }),
]);

const hasCompletionIcons = computed(() => options.value.some((option) => option.iconSrc));

function selectValue(value) {
  if (props.disabled) {
    return;
  }
  emit("update:modelValue", value);
}
</script>

<template>
  <div class="art-style-picker" :class="{ 'art-style-picker--list': layout === 'list' }">
    <div
      v-if="layout === 'list'"
      class="art-style-list"
      role="listbox"
      aria-label="Art style"
    >
      <button
        v-for="option in options"
        :key="option.value || 'all'"
        type="button"
        class="art-style-list-item"
        :class="{ active: modelValue === option.value }"
        role="option"
        :aria-selected="modelValue === option.value"
        :disabled="disabled"
        :title="option.label"
        @click="selectValue(option.value)"
      >
        <span
          v-if="option.iconSrc"
          class="art-style-list-icon-wrap"
          aria-hidden="true"
        >
          <img
            :src="option.iconSrc"
            alt=""
            class="art-style-list-icon"
            loading="lazy"
          >
        </span>
        <span class="art-style-list-label">{{ option.label }}</span>
      </button>
    </div>
    <BrowseSelect
      v-else
      :model-value="modelValue"
      :options="options"
      :disabled="disabled"
      :show-icons="hasCompletionIcons"
      optional-icons
      filterable
      aria-label="Art style"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>
