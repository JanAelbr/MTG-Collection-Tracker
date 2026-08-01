<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  title: { type: String, required: true },
  /** Short value shown beside the title when collapsed. */
  summary: { type: String, default: "" },
  defaultOpen: { type: Boolean, default: false },
});

const open = ref(props.defaultOpen);

watch(
  () => props.defaultOpen,
  (next) => {
    if (next) {
      open.value = true;
    }
  },
);

function toggle() {
  open.value = !open.value;
}
</script>

<template>
  <div
    class="binder-style-group"
    :class="{ 'binder-style-group--open': open }"
  >
    <button
      type="button"
      class="binder-style-group-toggle"
      :aria-expanded="open ? 'true' : 'false'"
      @click="toggle"
    >
      <span class="binder-style-group-title">{{ title }}</span>
      <span
        v-if="summary && !open"
        class="binder-style-group-summary"
      >
        {{ summary }}
      </span>
      <span class="binder-style-group-chevron" aria-hidden="true">
        {{ open ? "▾" : "▸" }}
      </span>
    </button>
    <div v-show="open" class="binder-style-group-body">
      <slot />
    </div>
  </div>
</template>
