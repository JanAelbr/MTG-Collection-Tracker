<script setup>
import { computed, reactive, ref } from "vue";
import BrowseSelect from "./BrowseSelect.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import SetGallery from "./SetGallery.vue";
import { api, clearClientCache } from "../api";
import { usePricingSettings } from "../composables/pricingSettings";
import { formatSetDropdownLabel, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";

const props = defineProps({
  sets: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  label: { type: String, default: "Set" },
  layout: {
    type: String,
    default: "dropdown",
    validator: (value) => value === "dropdown" || value === "banner",
  },
  showFavorites: { type: Boolean, default: false },
  manageSets: { type: Boolean, default: true },
});

const emit = defineEmits(["update:modelValue", "toggleFavorite", "sets-changed"]);

const { settings } = usePricingSettings();

const useBrowser = computed(() => settings.value?.setPickerMode === "browser");
const deletingSetCode = ref("");
const addSetEditor = reactive({
  open: false,
  setCode: "",
  saving: false,
  error: "",
});

const browseOptions = computed(() =>
  props.sets.map((set) => ({
    value: set.setCode,
    label: formatSetDropdownLabel(set) || set.setCode,
    iconSrc: resolveSetIconUri(set),
    searchText: [set.setCode, set.label, setShortName(set)].filter(Boolean).join(" "),
  })),
);

function onSelect(setCode) {
  emit("update:modelValue", setCode);
}

function onToggleFavorite(set) {
  emit("toggleFavorite", set);
}

function openAddSetEditor() {
  addSetEditor.open = true;
  addSetEditor.setCode = "";
  addSetEditor.error = "";
}

function closeAddSetEditor() {
  if (addSetEditor.saving) {
    return;
  }
  addSetEditor.open = false;
  addSetEditor.error = "";
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

async function saveAddSet() {
  const setCode = addSetEditor.setCode.trim().toUpperCase();
  if (!setCode || addSetEditor.saving) {
    return;
  }
  addSetEditor.saving = true;
  addSetEditor.error = "";
  try {
    const result = await api.createManagerSet({ setCode });
    await refreshSetsList(result);
    emit("update:modelValue", result.setCode);
    addSetEditor.open = false;
  } catch (error) {
    addSetEditor.error = error.message || "Could not add set.";
  } finally {
    addSetEditor.saving = false;
  }
}

async function removeSet(set) {
  if (!set?.setCode || deletingSetCode.value) {
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
  } catch (error) {
    window.alert(error.message || "Could not remove set.");
  } finally {
    deletingSetCode.value = "";
  }
}
</script>

<template>
  <div
    v-if="layout === 'banner' && useBrowser"
    class="set-gallery-wrap"
  >
    <SetGallery
      :sets="sets"
      :active-set-code="modelValue"
      :show-favorites="showFavorites"
      :manage-sets="manageSets"
      :deleting-set-code="deletingSetCode"
      @select="onSelect"
      @toggle-favorite="onToggleFavorite"
      @add-set="openAddSetEditor"
      @remove-set="removeSet"
    />
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

  <div v-if="addSetEditor.open" class="modal-backdrop" @click.self="closeAddSetEditor">
    <form class="modal-card" @submit.prevent="saveAddSet">
      <h3>Add set</h3>
      <p v-if="addSetEditor.saving" class="set-picker-add-status">
        <LoadingIndicator
          compact
          label="Creating set and fetching catalog from Scryfall…"
        />
      </p>
      <template v-else>
        <p class="manager-help">
          Creates <code>data/{set}.csv</code> and imports the full print catalog from Scryfall.
        </p>
        <label>
          <span>Set code</span>
          <input
            v-model="addSetEditor.setCode"
            type="text"
            maxlength="16"
            placeholder="e.g. MH3"
            required
          />
        </label>
        <p v-if="addSetEditor.error" class="collection-sync-message error">
          {{ addSetEditor.error }}
        </p>
      </template>
      <div class="modal-actions">
        <button
          type="button"
          class="btn btn-secondary"
          :disabled="addSetEditor.saving"
          @click="closeAddSetEditor"
        >
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" :disabled="addSetEditor.saving">
          Create
        </button>
      </div>
    </form>
  </div>
</template>
