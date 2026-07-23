<script setup>
import { computed, onMounted, ref, watch } from "vue";
import {
  applyOptimisticCopyCount,
  fetchCardCopyState,
  normalizeCardMenuTarget,
  ownershipRevision,
  setCardCopyAllocations,
  storageLocations,
} from "../composables/cardContextMenu";
import StorageLocationSelect from "./StorageLocationSelect.vue";

const MAX_COPIES = 99;

const props = defineProps({
  card: { type: Object, required: true },
});

const emit = defineEmits(["ownership-changed"]);

const busy = ref(false);
const error = ref("");
const copyState = ref(null);
const allocationRows = ref([]);
let rowKeyCounter = 0;

const target = computed(() => normalizeCardMenuTarget(props.card));
const canAdjust = computed(() => Boolean(target.value?.setCode && target.value?.collectorNumber));
const maxCopies = computed(() => copyState.value?.maxCopies ?? MAX_COPIES);

const totalCount = computed(() => {
  ownershipRevision.value;
  return allocationRows.value.reduce((sum, row) => sum + (Number(row.count) || 0), 0);
});

const assignableStorageLocations = computed(() =>
  storageLocations.value.filter(
    (location) =>
      location.locationType === "storage" || location.locationType === "binder",
  ),
);

const canAddStorageRow = computed(() => {
  if (!assignableStorageLocations.value.length) {
    return false;
  }
  const used = new Set(allocationRows.value.map((row) => row.locationSlug));
  return used.size < assignableStorageLocations.value.length;
});

function defaultStorageSlug(settings) {
  if (settings?.defaultStorageLocation) {
    return settings.defaultStorageLocation;
  }
  return assignableStorageLocations.value[0]?.slug || storageLocations.value[0]?.slug || "storage:general";
}

function nextUnusedStorageSlug(excludeIndex = -1) {
  const used = new Set(
    allocationRows.value
      .filter((_, index) => index !== excludeIndex)
      .map((row) => row.locationSlug),
  );
  const available = assignableStorageLocations.value.find((location) => !used.has(location.slug));
  return available?.slug || assignableStorageLocations.value[0]?.slug || "storage:general";
}

function createRow(locationSlug, count = 0) {
  return {
    key: `allocation-${rowKeyCounter += 1}`,
    locationSlug,
    count: Math.max(0, Number(count) || 0),
  };
}

function rowsFromState(state, settings) {
  const locations = state?.locations || [];
  if (locations.length) {
    return locations.map((location) => createRow(location.slug, location.count));
  }
  if ((state?.ownedCount ?? 0) > 0 && state?.copies?.length) {
    const grouped = new Map();
    for (const copy of state.copies) {
      grouped.set(copy.locationSlug, (grouped.get(copy.locationSlug) || 0) + 1);
    }
    return [...grouped.entries()].map(([slug, count]) => createRow(slug, count));
  }
  return [createRow(defaultStorageSlug(settings), 0)];
}

function availableLocations(rowIndex) {
  const used = new Set(
    allocationRows.value
      .filter((_, index) => index !== rowIndex)
      .map((row) => row.locationSlug),
  );
  return assignableStorageLocations.value.filter((location) => !used.has(location.slug));
}

function buildAllocationsPayload() {
  return allocationRows.value
    .filter((row) => row.count > 0)
    .map((row) => ({
      locationSlug: row.locationSlug,
      count: row.count,
    }));
}

async function loadState() {
  if (!canAdjust.value) {
    return;
  }
  error.value = "";
  try {
    const payload = await fetchCardCopyState(props.card);
    if (!payload) {
      return;
    }
    copyState.value = payload.state;
    allocationRows.value = rowsFromState(payload.state, payload.settings);
  } catch (err) {
    error.value = err.message || "Could not load owned copies.";
  }
}

async function persistAllocations(previousCount = totalCount.value) {
  if (!canAdjust.value || busy.value) {
    return;
  }
  busy.value = true;
  error.value = "";
  const nextCount = totalCount.value;
  applyOptimisticCopyCount(props.card, nextCount, previousCount);
  try {
    const state = await setCardCopyAllocations(props.card, buildAllocationsPayload());
    copyState.value = state;
    allocationRows.value = rowsFromState(state, null);
    emit("ownership-changed");
  } catch (err) {
    error.value = err.message || "Could not update storage.";
    await loadState();
  } finally {
    busy.value = false;
  }
}

async function onAdjustRow(index, delta) {
  const row = allocationRows.value[index];
  if (!row || busy.value) {
    return;
  }
  const previousCount = totalCount.value;
  if (delta > 0 && previousCount >= maxCopies.value) {
    return;
  }
  const nextRowCount = Math.max(0, row.count + delta);
  if (delta < 0 && row.count <= 0) {
    return;
  }
  allocationRows.value = allocationRows.value.map((item, itemIndex) =>
    itemIndex === index ? { ...item, count: nextRowCount } : item,
  );
  await persistAllocations(previousCount);
}

async function onStorageSelect(index, slug) {
  if (!slug || busy.value) {
    return;
  }
  allocationRows.value = allocationRows.value.map((item, itemIndex) =>
    itemIndex === index ? { ...item, locationSlug: slug } : item,
  );
  await persistAllocations();
}

async function addStorageRow() {
  if (!canAddStorageRow.value || busy.value) {
    return;
  }
  allocationRows.value = [
    ...allocationRows.value,
    createRow(nextUnusedStorageSlug(), 0),
  ];
}

async function removeStorageRow(index) {
  if (busy.value || allocationRows.value.length <= 1) {
    return;
  }
  const previousCount = totalCount.value;
  allocationRows.value = allocationRows.value.filter((_, itemIndex) => itemIndex !== index);
  await persistAllocations(previousCount);
}

const showPanel = computed(() => canAdjust.value);

onMounted(loadState);

watch(
  () => [
    props.card?.setCode,
    props.card?.collectorNumber,
    props.card?.finish,
  ],
  loadState,
);
</script>

<template>
  <div v-if="showPanel" class="card-owned-qty-tile">
    <div class="card-owned-qty-tile-row card-owned-qty-tile-row-head">
      <span class="card-owned-qty-tile-label">Owned</span>
      <span class="card-owned-qty-tile-total">{{ totalCount }}</span>
    </div>

    <div v-if="storageLocations.length" class="card-owned-qty-tile-allocations">
      <div
        v-for="(row, index) in allocationRows"
        :key="row.key"
        class="card-owned-qty-tile-allocation"
      >
        <StorageLocationSelect
          class="card-owned-qty-tile-storage-picker"
          :model-value="row.locationSlug"
          :locations="availableLocations(index)"
          :include-types="['storage', 'binder']"
          :disabled="busy"
          :aria-label="`Storage location ${index + 1}`"
          @update:model-value="(slug) => onStorageSelect(index, slug)"
        />

        <div class="card-interactive-stepper card-owned-qty-tile-stepper">
          <button
            type="button"
            class="card-interactive-step"
            :disabled="busy || row.count <= 0"
            :aria-label="`Remove one copy from ${index + 1}`"
            @click="onAdjustRow(index, -1)"
          >
            −
          </button>
          <span class="card-interactive-count">{{ row.count }}</span>
          <button
            type="button"
            class="card-interactive-step"
            :disabled="busy || totalCount >= maxCopies"
            :aria-label="`Add one copy to ${index + 1}`"
            @click="onAdjustRow(index, 1)"
          >
            +
          </button>
        </div>

        <button
          v-if="allocationRows.length > 1"
          type="button"
          class="card-owned-qty-tile-remove"
          :disabled="busy"
          aria-label="Remove storage row"
          title="Remove storage"
          @click="removeStorageRow(index)"
        >
          ×
        </button>
      </div>

      <button
        v-if="canAddStorageRow"
        type="button"
        class="btn btn-secondary btn-small card-owned-qty-tile-add"
        :disabled="busy"
        @click="addStorageRow"
      >
        Add storage
      </button>
    </div>

    <p v-if="busy" class="card-owned-qty-tile-status">Updating…</p>
    <p v-else-if="error" class="card-owned-qty-tile-status error">{{ error }}</p>
  </div>
</template>

