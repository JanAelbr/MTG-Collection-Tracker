<script setup>
import { computed } from "vue";
import BrowseSelect from "./BrowseSelect.vue";
import { artStyleOptionValue, formatArtStyleDropdownLabel } from "../utils/format";

const props = defineProps({
  artStyles: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
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
</script>

<template>
  <BrowseSelect
    :model-value="modelValue"
    :options="options"
    :disabled="disabled"
    filterable
    aria-label="Art style"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>
