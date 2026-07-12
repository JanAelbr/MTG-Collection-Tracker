<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api";
import LoadingIndicator from "./LoadingIndicator.vue";
import StorageLocationIcon from "./StorageLocationIcon.vue";
import { EXCLUDE_CATEGORY_OPTIONS } from "../utils/deckPower";
import { STORAGE_LOCATION_SECTIONS } from "../utils/storageLocationGroups";

const props = defineProps({
  locationSlugs: { type: Array, default: () => [] },
  includeDeckStorage: { type: Boolean, default: false },
  landCount: { type: Number, default: 38 },
  budgetCap: { type: [Number, String, null], default: null },
  excludeCategories: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "update:locationSlugs",
  "update:includeDeckStorage",
  "update:landCount",
  "update:budgetCap",
  "update:excludeCategories",
]);

const locations = ref([]);
const poolPreview = ref(null);
const loading = ref(true);
const previewLoading = ref(false);

const selectableLocations = computed(() =>
  locations.value.filter((location) => {
    if (props.includeDeckStorage) {
      return true;
    }
    return !String(location.slug || "").startsWith("deck:");
  }),
);

const sectionedLocations = computed(() =>
  STORAGE_LOCATION_SECTIONS.map((section) => ({
    ...section,
    locations: selectableLocations.value.filter(
      (location) => location.locationType === section.type,
    ),
  })).filter((section) => section.locations.length),
);

function toggleLocation(slug) {
  const current = new Set(props.locationSlugs);
  if (current.has(slug)) {
    current.delete(slug);
  } else {
    current.add(slug);
  }
  emit("update:locationSlugs", [...current]);
}

function toggleExcludeCategory(category) {
  const current = new Set(props.excludeCategories);
  if (current.has(category)) {
    current.delete(category);
  } else {
    current.add(category);
  }
  emit("update:excludeCategories", [...current]);
}

async function loadLocations() {
  loading.value = true;
  try {
    const payload = await api.listStorageLocations();
    locations.value = payload.locations || payload || [];
    if (!props.locationSlugs.length) {
      const defaults = locations.value
        .filter((location) => !String(location.slug).startsWith("deck:"))
        .map((location) => location.slug);
      emit("update:locationSlugs", defaults);
    }
  } finally {
    loading.value = false;
  }
}

async function refreshPreview() {
  if (!props.locationSlugs.length) {
    poolPreview.value = null;
    return;
  }
  previewLoading.value = true;
  try {
    poolPreview.value = await api.previewBuilderPool({
      locationSlugs: props.locationSlugs,
      includeDeckStorage: props.includeDeckStorage,
    });
  } finally {
    previewLoading.value = false;
  }
}

onMounted(loadLocations);

watch(
  () => [props.locationSlugs, props.includeDeckStorage],
  () => {
    refreshPreview();
  },
  { deep: true },
);
</script>

<template>
  <section class="deck-builder-step">
    <header class="deck-builder-step-head">
      <h3>Generation options</h3>
      <p>Select where to pull owned cards from and tune the build.</p>
    </header>

    <div v-if="loading" class="deck-builder-loading">
      <LoadingIndicator label="Loading storage…" />
    </div>

    <template v-else>
      <div class="deck-builder-option-block">
        <h4>Storage locations</h4>
        <label class="deck-builder-checkbox">
          <input
            type="checkbox"
            :checked="includeDeckStorage"
            @change="emit('update:includeDeckStorage', $event.target.checked)"
          />
          Include cards allocated to other decks
        </label>

        <div
          v-for="section in sectionedLocations"
          :key="section.type"
          class="deck-builder-location-section"
        >
          <h5>{{ section.label }}</h5>
          <div class="deck-builder-location-list">
            <label
              v-for="location in section.locations"
              :key="location.slug"
              class="deck-builder-location-item"
            >
              <input
                type="checkbox"
                :checked="locationSlugs.includes(location.slug)"
                @change="toggleLocation(location.slug)"
              />
              <StorageLocationIcon :location-type="location.locationType" />
              <span>{{ location.label }}</span>
              <span class="deck-builder-location-count">{{ location.cardCount || 0 }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="deck-builder-option-grid">
        <label class="deck-builder-field">
          <span>Land count</span>
          <input
            type="number"
            min="20"
            max="45"
            :value="landCount"
            @input="emit('update:landCount', Number($event.target.value) || 38)"
          />
        </label>

        <label class="deck-builder-field">
          <span>Budget cap for suggestions (€)</span>
          <input
            type="number"
            min="0"
            step="1"
            :value="budgetCap ?? ''"
            placeholder="No limit"
            @input="emit('update:budgetCap', $event.target.value === '' ? null : Number($event.target.value))"
          />
        </label>
      </div>

      <div class="deck-builder-option-block">
        <h4>Exclude categories</h4>
        <div class="deck-builder-chip-group">
          <button
            v-for="option in EXCLUDE_CATEGORY_OPTIONS"
            :key="option.id"
            type="button"
            class="filter-button"
            :class="{ active: excludeCategories.includes(option.id) }"
            @click="toggleExcludeCategory(option.id)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div v-if="previewLoading" class="deck-builder-preview-hint">
        <LoadingIndicator label="Previewing pool…" />
      </div>
      <p v-else-if="poolPreview" class="deck-builder-preview-hint">
        Pool: {{ poolPreview.cardCount }} prints,
        {{ poolPreview.uniqueNames }} unique cards,
        {{ poolPreview.commanderCandidates }} commander candidates.
      </p>
    </template>
  </section>
</template>
