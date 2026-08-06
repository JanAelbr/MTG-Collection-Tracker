<script setup>
import "../styles/set-gallery.css";
import { computed } from "vue";
import SetGallery from "./SetGallery.vue";
import { formatSetCountLabel, setDisplayName, setShortName } from "../utils/format";

const props = defineProps({
  sets: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  family: { type: Boolean, default: false },
  label: { type: String, default: "Set" },
  layout: {
    type: String,
    default: "dropdown",
    validator: (value) => value === "dropdown" || value === "banner",
  },
  activeArtStyle: { type: String, default: "" },
});

const emit = defineEmits([
  "update:modelValue",
  "update:family",
  "sets-changed",
]);

const knownSetCodes = computed(() => {
  const codes = new Set();
  for (const set of props.sets) {
    if (!set?.setCode || set.setCode === "All") {
      continue;
    }
    codes.add(String(set.setCode).toUpperCase());
    for (const member of set.familyMembers || []) {
      if (member) {
        codes.add(String(member).toUpperCase());
      }
    }
  }
  return codes;
});

const activeSet = computed(() =>
  props.sets.find((set) => set.setCode === props.modelValue) || null,
);

const activeSetCountLabel = computed(() => {
  if (!activeSet.value) {
    return "";
  }
  if (props.family && activeSet.value.familyOwnedCount != null) {
    return `${activeSet.value.familyOwnedCount}/${activeSet.value.familyCatalogCount}`;
  }
  return formatSetCountLabel(activeSet.value);
});

const activeSetTitle = computed(() => {
  if (!activeSet.value) {
    return "";
  }
  const name = setDisplayName(activeSet.value);
  const familySuffix = props.family ? " family" : "";
  const counts = activeSetCountLabel.value;
  return counts ? `${name}${familySuffix} ${counts}` : `${name}${familySuffix}`;
});

function isKnownSet(setCode) {
  const normalized = String(setCode || "").trim().toUpperCase();
  return Boolean(normalized) && knownSetCodes.value.has(normalized);
}

function onSelect(setCode) {
  const normalized = String(setCode || "").trim().toUpperCase();
  if (!normalized) {
    return;
  }
  if (normalized === "ALL" || isKnownSet(normalized)) {
    emit("update:family", false);
    emit("update:modelValue", normalized === "ALL" ? "All" : normalized);
  }
}

function onSelectFamily(setCode) {
  emit("update:family", true);
  emit("update:modelValue", setCode);
}
</script>

<template>
  <div
    v-if="layout === 'banner'"
    class="set-gallery-wrap"
  >
    <div class="set-gallery-row">
      <SetGallery
        :sets="sets"
        :active-set-code="modelValue"
        :active-family="family"
        :active-art-style="activeArtStyle"
        @select="onSelect"
        @select-family="onSelectFamily"
        @sets-changed="emit('sets-changed', $event)"
      />
    </div>
  </div>

  <div
    v-else-if="layout === 'dropdown'"
    class="filter-sidebar-active-set"
  >
    <p
      v-if="activeSet"
      class="filter-sidebar-active-set-title"
      :title="activeSetTitle"
    >
      <span v-if="activeSet.favorite" class="filter-sidebar-active-set-favorite" aria-hidden="true">★</span>
      <span v-if="activeSet.setCode !== 'All'" class="filter-sidebar-active-set-code">
        {{ activeSet.setCode }}{{ family ? "+" : "" }}
      </span>
      <span class="filter-sidebar-active-set-name">
        {{ setShortName(activeSet) }}{{ family ? " family" : "" }}
      </span>
      <span v-if="activeSetCountLabel" class="filter-sidebar-active-set-count">
        {{ activeSetCountLabel }}
      </span>
    </p>
  </div>
</template>
