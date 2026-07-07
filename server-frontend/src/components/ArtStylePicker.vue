<script setup>
import { computed } from "vue";
import BrowseSelect from "./BrowseSelect.vue";
import { artStyleOptionValue, formatArtStyleDropdownLabel } from "../utils/format";

const props = defineProps({
  artStyles: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  layout: {
    type: String,
    default: "dropdown",
    validator: (value) => ["dropdown", "list"].includes(value),
  },
});

const emit = defineEmits(["update:modelValue"]);

const options = computed(() => [
  { value: "", label: "All art styles", searchText: "all art styles" },
  ...props.artStyles.map((style) => {
    const value = artStyleOptionValue(style);
    return {
      value,
      label: formatArtStyleDropdownLabel(style),
      searchText: value,
    };
  }),
]);

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
        <span class="art-style-list-label">{{ option.label }}</span>
      </button>
    </div>
    <BrowseSelect
      v-else
      :model-value="modelValue"
      :options="options"
      :disabled="disabled"
      filterable
      aria-label="Art style"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>
