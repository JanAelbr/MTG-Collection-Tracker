<script setup>
import "../styles/set-gallery.css";
import { computed, onMounted, ref, watch } from "vue";
import SetGallery from "./SetGallery.vue";
import { api, clearClientCache } from "../api";
import { useAvailableManagerSets } from "../composables/availableSets";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";
import { formatSetCountLabel, setDisplayName, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";

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
  showFavorites: { type: Boolean, default: true },
  showReloadCatalog: { type: Boolean, default: true },
  activeArtStyle: { type: String, default: "" },
});

const emit = defineEmits([
  "update:modelValue",
  "update:family",
  "toggleFavorite",
  "sets-changed",
]);

const { setGalleryFilter } = useSetGalleryFilter();
const reloadingSetCode = ref("");
const addingSetCode = ref("");
const ensureError = ref("");
const {
  availableSets,
  loadingAvailableSets,
  fetchAvailableManagerSets,
  removeAvailableSet,
} = useAvailableManagerSets();

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

const searchSets = computed(() =>
  availableSets.value.map((set) => ({
    setCode: set.setCode,
    label: set.name || set.setCode,
    name: set.name || set.setCode,
    iconUri: set.iconUri || resolveSetIconUri(set),
    setType: set.setType,
    parentSetCode: set.parentSetCode,
    familyMembers: set.familyMembers || [set.setCode],
    familyRoot: set.setCode,
    isFamilyRoot: true,
    ownedCount: 0,
    catalogCount: 0,
  })),
);

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
    return;
  }
  ensureAndSelectSet(normalized);
}

function onSelectFamily(setCode) {
  emit("update:family", true);
  emit("update:modelValue", setCode);
}

function onFavoriteClick(set) {
  toggleFavorite(set);
}

async function toggleFavorite(set) {
  if (!set?.setCode || set.setCode === "All") {
    return;
  }
  try {
    const result = await api.toggleManagerSetFavorite(set.setCode);
    clearClientCache();
    emit("sets-changed", { ...result, catalogReloaded: true });
    emit("toggleFavorite", set);
  } catch (error) {
    window.alert(error.message || "Could not update favourite set.");
  }
}

async function loadSearchSets() {
  if (props.layout !== "banner") {
    return;
  }
  await fetchAvailableManagerSets();
}

async function ensureAndSelectSet(setCode) {
  const normalized = String(setCode || "").trim().toUpperCase();
  if (!normalized || addingSetCode.value) {
    return;
  }
  addingSetCode.value = normalized;
  ensureError.value = "";
  try {
    const result = await api.createManagerSet({ setCode: normalized });
    for (const code of result.addedSetCodes || result.familyMembers || [normalized]) {
      removeAvailableSet(code);
    }
    const root = result.setCode || normalized;
    const members = result.familyMembers || [root];
    clearClientCache();
    setGalleryFilter.value = "";
    emit("update:family", members.length > 1);
    emit("update:modelValue", root);
    emit("sets-changed", { ...result, catalogReloaded: true });
  } catch (error) {
    ensureError.value = error.message || "Could not load set family.";
    window.alert(ensureError.value);
  } finally {
    addingSetCode.value = "";
  }
}

async function reloadCatalog(set) {
  if (!set?.setCode || set.setCode === "All") {
    return;
  }
  if (reloadingSetCode.value === set.setCode) {
    return;
  }
  reloadingSetCode.value = set.setCode;
  try {
    const result = await api.reloadManagerSetCatalog(set.setCode);
    clearClientCache();
    emit("sets-changed", { ...result, catalogReloaded: true });
  } catch (error) {
    window.alert(error.message || "Could not reload catalog.");
  } finally {
    reloadingSetCode.value = "";
  }
}

watch(
  () => props.layout,
  () => {
    loadSearchSets();
  },
);

onMounted(() => {
  loadSearchSets();
});
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
        :show-favorites="showFavorites"
        :show-reload-catalog="showReloadCatalog"
        :reloading-set-code="reloadingSetCode"
        :search-sets="searchSets"
        :loading-search-sets="loadingAvailableSets"
        :adding-set-code="addingSetCode"
        @select="onSelect"
        @select-family="onSelectFamily"
        @toggle-favorite="onFavoriteClick"
        @reload-catalog="reloadCatalog"
      />
    </div>
    <p v-if="ensureError" class="collection-sync-message error set-gallery-add-error">
      {{ ensureError }}
    </p>
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
