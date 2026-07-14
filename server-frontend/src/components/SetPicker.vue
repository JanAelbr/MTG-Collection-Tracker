<script setup>
import { computed, onMounted, ref, watch } from "vue";
import BrowseSelect from "./BrowseSelect.vue";
import SetGallery from "./SetGallery.vue";
import { api, clearClientCache } from "../api";
import { useAvailableManagerSets } from "../composables/availableSets";
import { usePricingSettings } from "../composables/pricingSettings";
import { formatSetFilterLabel, formatSetCountLabel, setDisplayName, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";

const props = defineProps({
  sets: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  label: { type: String, default: "Set" },
  layout: {
    type: String,
    default: "dropdown",
    validator: (value) => value === "dropdown" || value === "banner",
  },
  showFavorites: { type: Boolean, default: true },
  manageSets: { type: Boolean, default: true },
  showReloadCatalog: { type: Boolean, default: true },
  activeArtStyle: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "toggleFavorite", "sets-changed"]);

const { settings } = usePricingSettings();
const { setGalleryCollapsed } = useSetGalleryFilter();

const useBrowser = computed(() => settings.value?.setPickerMode === "browser");
const showFavoriteStars = computed(() => useBrowser.value && props.showFavorites);
const deletingSetCode = ref("");
const reloadingSetCode = ref("");
const addingSetCode = ref("");
const {
  availableSets,
  loadingAvailableSets,
  loadError: addSetError,
  fetchAvailableManagerSets,
  removeAvailableSet,
} = useAvailableManagerSets();

const browseOptions = computed(() =>
  props.sets.map((set) => ({
    value: set.setCode,
    label: formatSetFilterLabel(set) || set.setCode,
    iconSrc: resolveSetIconUri(set),
    searchText: [set.setCode, set.label, setDisplayName(set)].filter(Boolean).join(" "),
  })),
);

const trackedSetCodes = computed(
  () => new Set(props.sets.map((set) => set.setCode).filter((code) => code && code !== "All")),
);

const addSetOptions = computed(() =>
  availableSets.value
    .filter((set) => !trackedSetCodes.value.has(set.setCode))
    .map((set) => ({
      value: set.setCode,
      label: `${set.setCode} — ${set.name || set.setCode}`,
      iconSrc: set.iconUri || resolveSetIconUri(set),
      searchText: [set.setCode, set.name].filter(Boolean).join(" "),
    })),
);

const activeSet = computed(() =>
  props.sets.find((set) => set.setCode === props.modelValue) || null,
);

const activeSetTitle = computed(() => {
  if (!activeSet.value) {
    return "";
  }
  const name = setDisplayName(activeSet.value);
  const counts = formatSetCountLabel(activeSet.value);
  return counts ? `${name} ${counts}` : name;
});

function onSelect(setCode) {
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
    const sets = result.sets || (await api.listManagerSets()).sets || [];
    clearClientCache();
    emit("sets-changed", { ...result, sets });
    emit("toggleFavorite", set);
  } catch (error) {
    window.alert(error.message || "Could not update favourite set.");
  }
}

function selectFallbackSet(removedCode) {
  const remaining = props.sets.filter((set) => set.setCode !== removedCode);
  const next = remaining.find((set) => set.setCode !== "All") || remaining[0]?.setCode || "";
  if (next && next !== props.modelValue) {
    emit("update:modelValue", next);
  }
}

async function refreshSetsList(result) {
  clearClientCache();
  const payload = await api.listManagerSets();
  const sets = payload.sets || [];
  emit("sets-changed", { ...result, sets });
  return sets;
}

async function loadAvailableSets() {
  if (!props.manageSets || !useBrowser.value || props.layout !== "banner") {
    return;
  }
  await fetchAvailableManagerSets();
}

async function addSet(setCode) {
  const normalized = String(setCode || "").trim().toUpperCase();
  if (!normalized || addingSetCode.value) {
    return;
  }
  addingSetCode.value = normalized;
  addSetError.value = "";
  try {
    const result = await api.createManagerSet({ setCode: normalized });
    await refreshSetsList(result);
    removeAvailableSet(normalized);
    emit("update:modelValue", result.setCode);
  } catch (error) {
    addSetError.value = error.message || "Could not add set.";
    window.alert(addSetError.value);
  } finally {
    addingSetCode.value = "";
  }
}

async function removeSet(set) {
  if (!set?.setCode) {
    return;
  }
  if (deletingSetCode.value === set.setCode) {
    return;
  }
  if (!window.confirm(`Remove set ${set.setCode}? The card catalog stays in the database.`)) {
    return;
  }
  deletingSetCode.value = set.setCode;
  try {
    const result = await api.deleteManagerSet(set.setCode);
    await refreshSetsList(result);
    if (props.modelValue === set.setCode) {
      selectFallbackSet(set.setCode);
    }
    await loadAvailableSets();
  } catch (error) {
    window.alert(error.message || "Could not remove set.");
  } finally {
    deletingSetCode.value = "";
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
  () => [useBrowser.value, props.manageSets, props.layout],
  () => {
    loadAvailableSets();
  },
);

onMounted(() => {
  loadAvailableSets();
});
</script>

<template>
  <div
    v-if="layout === 'banner' && useBrowser"
    class="set-gallery-wrap"
    :class="{ 'set-gallery-wrap--collapsed': setGalleryCollapsed }"
  >
    <div class="set-gallery-row">
      <SetGallery
        :sets="sets"
        :active-set-code="modelValue"
        :active-art-style="activeArtStyle"
        :show-favorites="showFavoriteStars"
        :manage-sets="manageSets"
        :show-reload-catalog="showReloadCatalog"
        :deleting-set-code="deletingSetCode"
        :reloading-set-code="reloadingSetCode"
        :available-set-options="addSetOptions"
        :loading-available-sets="loadingAvailableSets"
        :adding-set-code="addingSetCode"
        :collapsed="setGalleryCollapsed"
        @select="onSelect"
        @toggle-favorite="onFavoriteClick"
        @add-set="addSet"
        @remove-set="removeSet"
        @reload-catalog="reloadCatalog"
      />
      <button
        type="button"
        class="set-gallery-collapse-btn"
        :aria-label="setGalleryCollapsed ? 'Show set labels' : 'Show icons only'"
        :title="setGalleryCollapsed ? 'Show set labels' : 'Show icons only'"
        :aria-pressed="setGalleryCollapsed ? 'true' : 'false'"
        @click="setGalleryCollapsed = !setGalleryCollapsed"
      >
        {{ setGalleryCollapsed ? "▾" : "▴" }}
      </button>
    </div>
    <p v-if="addSetError" class="collection-sync-message error set-gallery-add-error">
      {{ addSetError }}
    </p>
  </div>

  <div
    v-else-if="layout === 'dropdown' && useBrowser"
    class="filter-sidebar-active-set"
  >
    <p
      v-if="activeSet"
      class="filter-sidebar-active-set-title"
      :title="activeSetTitle"
    >
      <span v-if="activeSet.favorite" class="filter-sidebar-active-set-favorite" aria-hidden="true">★</span>
      <span v-if="activeSet.setCode !== 'All'" class="filter-sidebar-active-set-code">{{ activeSet.setCode }}</span>
      <span class="filter-sidebar-active-set-name">{{ setShortName(activeSet) }}</span>
      <span v-if="formatSetCountLabel(activeSet)" class="filter-sidebar-active-set-count">
        {{ formatSetCountLabel(activeSet) }}
      </span>
    </p>
  </div>

  <label
    v-else-if="layout === 'dropdown' && !useBrowser"
    class="manager-filter set-picker-dropdown"
  >
    <span v-if="label">{{ label }}</span>
    <BrowseSelect
      :model-value="modelValue"
      :options="browseOptions"
      filterable
      show-icons
      :aria-label="label || 'Set'"
      @update:model-value="onSelect"
    />
  </label>
</template>
