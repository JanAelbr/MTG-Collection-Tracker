<script setup>
defineOptions({ name: "FilterSidebarGroup" });

defineProps({
  title: { type: String, required: true },
  /** Short hint shown beside the title when collapsed. */
  summary: { type: String, default: "" },
  expanded: { type: Boolean, default: false },
});

defineEmits(["toggle"]);
</script>

<template>
  <section
    class="filter-sidebar-group"
    :class="{ 'is-expanded': expanded }"
  >
    <button
      type="button"
      class="filter-sidebar-group-toggle"
      :aria-expanded="expanded ? 'true' : 'false'"
      @click="$emit('toggle')"
    >
      <span class="filter-sidebar-group-title">{{ title }}</span>
      <span
        v-if="summary && !expanded"
        class="filter-sidebar-group-summary"
      >
        {{ summary }}
      </span>
      <span class="filter-sidebar-group-chevron" aria-hidden="true">
        {{ expanded ? "▾" : "▸" }}
      </span>
    </button>
    <div v-show="expanded" class="filter-sidebar-group-body">
      <slot />
    </div>
  </section>
</template>
