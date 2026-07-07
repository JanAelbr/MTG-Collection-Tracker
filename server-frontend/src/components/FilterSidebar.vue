<script setup>
import { computed, onMounted, ref, watch } from "vue";
import {
  filterSidebarWidthPx,
  getFilterSidebarPrefs,
  storeFilterSidebarPrefs,
} from "../utils/filterStorage";

const collapsed = ref(false);
const wide = ref(false);

const sidebarStyle = computed(() => {
  if (collapsed.value) {
    return { "--filter-sidebar-width": "36px" };
  }
  return { "--filter-sidebar-width": `${filterSidebarWidthPx(wide.value)}px` };
});

const widthToggleLabel = computed(() => (wide.value ? "Narrow sidebar" : "Wider sidebar"));

onMounted(() => {
  const prefs = getFilterSidebarPrefs();
  collapsed.value = prefs.collapsed;
  wide.value = prefs.wide;
});

watch([collapsed, wide], () => {
  storeFilterSidebarPrefs({
    collapsed: collapsed.value,
    wide: wide.value,
  });
});

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
}

function toggleWidth() {
  wide.value = !wide.value;
}
</script>

<template>
  <aside
    class="filter-sidebar"
    :class="{
      'filter-sidebar--collapsed': collapsed,
      'filter-sidebar--wide': wide && !collapsed,
    }"
    :style="sidebarStyle"
    aria-label="Filters"
  >
    <div class="filter-sidebar-chrome">
      <button
        type="button"
        class="filter-sidebar-chrome-btn"
        :aria-label="collapsed ? 'Expand filters' : 'Collapse filters'"
        :title="collapsed ? 'Expand filters' : 'Collapse filters'"
        @click="toggleCollapsed"
      >
        {{ collapsed ? "»" : "«" }}
      </button>
      <button
        v-if="!collapsed"
        type="button"
        class="filter-sidebar-chrome-btn filter-sidebar-width-btn"
        :aria-label="widthToggleLabel"
        :title="widthToggleLabel"
        @click="toggleWidth"
      >
        {{ wide ? "↔" : "⇔" }}
      </button>
    </div>

    <div v-show="!collapsed" class="filter-sidebar-body">
      <slot />
    </div>
  </aside>
</template>
