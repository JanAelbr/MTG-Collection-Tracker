<script setup>
import { computed, ref, watch } from "vue";
import {
  adjustCardCopyCount,
  applyOptimisticCopyCount,
  changeCardOwnershipFinish,
  effectiveDeckOwnedQty,
  ensureStorageLocations,
  fetchCardCopyState,
  isEffectivelyOwned,
  normalizeCardMenuTarget,
  ownershipRevision,
  storageLocations,
  updateCardCopyFinish,
  updateCardCopyStorage,
} from "../composables/cardContextMenu";
import { fetchPricingSettings } from "../composables/pricingSettings";
import FinishToggleButton from "./FinishToggleButton.vue";
import StorageLocationSelect from "./StorageLocationSelect.vue";
import {
  cardFinish,
  cardSupportsNonfoilFoilToggle,
  FINISH_FOIL,
  FINISH_NONFOIL,
  normalizeFinish,
} from "../utils/finishes";

const MAX_COPIES = 99;

const props = defineProps({
  card: { type: Object, default: null },
  visible: { type: Boolean, default: true },
  variant: {
    type: String,
    default: "overlay",
    validator: (value) => value === "overlay" || value === "panel",
  },
});

const emit = defineEmits(["finish-changed", "ownership-changed", "menu-open-change"]);

const panelLoading = ref(false);
const panelError = ref("");
const copyState = ref(null);
const defaultStorageSlug = ref("");
let loadToken = 0;

const isInteractive = computed(() => Boolean(props.card && normalizeCardMenuTarget(props.card)));
const ownedCount = computed(() => {
  ownershipRevision.value;
  if (copyState.value?.ownedCount != null) {
    return copyState.value.ownedCount;
  }
  return effectiveDeckOwnedQty(props.card);
});
const maxCopies = computed(() => copyState.value?.maxCopies ?? MAX_COPIES);
const copies = computed(() => copyState.value?.copies ?? []);
const canAddCopy = computed(() => ownedCount.value < maxCopies.value);
const currentFinish = computed(() => cardFinish(props.card));
const canToggleNonfoilFoil = computed(() => cardSupportsNonfoilFoilToggle(props.card));

const displayCopyRows = computed(() => {
  if (copies.value.length) {
    return copies.value;
  }
  if (ownedCount.value <= 0) {
    return [];
  }
  return Array.from({ length: ownedCount.value }, (_, index) => ({
    instanceId: `pending-${index}`,
    locationSlug: defaultStorageSlug.value,
    finish: currentFinish.value,
  }));
});

const showOwnedFinishToggle = computed(
  () => canToggleNonfoilFoil.value && ownedCount.value <= 1,
);

function copyFinish(copy) {
  return normalizeFinish(copy?.finish ?? currentFinish.value);
}

function showCopyFinishToggle(copy) {
  return (
    canToggleNonfoilFoil.value
    && ownedCount.value > 1
    && typeof copy?.instanceId === "number"
    && [FINISH_NONFOIL, FINISH_FOIL].includes(copyFinish(copy))
  );
}

function storageLabel(slug) {
  return storageLocations.value.find((location) => location.slug === slug)?.label || slug;
}

function resolveDefaultStorageSlug(state, settings) {
  if (state?.copies?.length === 1) {
    return state.copies[0].locationSlug;
  }
  if (state?.locationSlug) {
    return state.locationSlug;
  }
  if (settings?.defaultStorageLocation) {
    return settings.defaultStorageLocation;
  }
  return storageLocations.value[0]?.slug || "storage:general";
}

async function ensureDefaultsForAdd() {
  if (defaultStorageSlug.value) {
    return;
  }
  const [, settings] = await Promise.all([
    ensureStorageLocations(),
    fetchPricingSettings(),
  ]);
  defaultStorageSlug.value = resolveDefaultStorageSlug(null, settings);
}

async function loadPanelState() {
  if (!isInteractive.value) {
    return;
  }
  const token = ++loadToken;
  panelError.value = "";
  try {
    const payload = await fetchCardCopyState(props.card);
    if (token !== loadToken || !payload) {
      return;
    }
    copyState.value = payload.state;
    defaultStorageSlug.value = resolveDefaultStorageSlug(payload.state, payload.settings);
  } catch (error) {
    if (token !== loadToken) {
      return;
    }
    panelError.value = error.message || "Could not load card details.";
  }
}

watch(
  () => [
    props.card?.setCode,
    props.card?.set_code,
    props.card?.collectorNumber,
    props.card?.collector_number,
    props.card?.finish,
  ],
  () => {
    loadToken += 1;
    copyState.value = null;
    defaultStorageSlug.value = "";
    panelError.value = "";
    if (props.visible && isEffectivelyOwned(props.card)) {
      loadPanelState();
    }
  },
);

watch(
  () => props.visible,
  (visible) => {
    if (!visible || !isInteractive.value || copyState.value || panelLoading.value) {
      return;
    }
    if (isEffectivelyOwned(props.card)) {
      loadPanelState();
    }
  },
  { immediate: true },
);

function optimisticCopies(previousCount, nextCount) {
  const current = [...(copyState.value?.copies || [])];
  if (nextCount > previousCount) {
    const slug = defaultStorageSlug.value || storageLocations.value[0]?.slug || "storage:general";
    current.push({
      instanceId: `temp-${Date.now()}-${current.length}`,
      locationSlug: slug,
      label: storageLabel(slug),
      finish: currentFinish.value,
    });
    return current;
  }
  if (nextCount < previousCount && current.length) {
    return current.slice(0, -1);
  }
  return current;
}

async function onAdjust(delta) {
  if (!isInteractive.value || panelLoading.value) {
    return;
  }
  const previousCount = ownedCount.value;
  if (delta > 0 && previousCount >= maxCopies.value) {
    return;
  }
  if (delta > 0 && previousCount === 0 && !copyState.value) {
    await ensureDefaultsForAdd();
  }
  const optimisticCount = Math.max(0, previousCount + delta);
  panelLoading.value = true;
  panelError.value = "";
  copyState.value = {
    ...(copyState.value || {}),
    ownedCount: optimisticCount,
    copies: optimisticCopies(previousCount, optimisticCount),
  };
  applyOptimisticCopyCount(props.card, optimisticCount, previousCount);
  try {
    const state = await adjustCardCopyCount(
      props.card,
      delta,
      defaultStorageSlug.value,
    );
    copyState.value = state;
    defaultStorageSlug.value = resolveDefaultStorageSlug(state, null);
    emit("ownership-changed");
  } catch (error) {
    panelError.value = error.message || "Could not update owned count.";
    try {
      const payload = await fetchCardCopyState(props.card);
      if (payload) {
        copyState.value = payload.state;
        defaultStorageSlug.value = resolveDefaultStorageSlug(payload.state, payload.settings);
        applyOptimisticCopyCount(props.card, payload.state.ownedCount ?? 0, optimisticCount);
      }
    } catch {
      // Keep the error message visible.
    }
  } finally {
    panelLoading.value = false;
  }
}

async function onCopyStorageSelect(copy, slug) {
  if (!slug || panelLoading.value || typeof copy.instanceId !== "number") {
    return;
  }
  panelLoading.value = true;
  panelError.value = "";
  const previousSlug = copy.locationSlug;
  copyState.value = {
    ...(copyState.value || {}),
    copies: (copyState.value?.copies || []).map((item) => (
      item.instanceId === copy.instanceId
        ? { ...item, locationSlug: slug, label: storageLabel(slug) }
        : item
    )),
  };
  try {
    const state = await updateCardCopyStorage(props.card, copy.instanceId, slug);
    copyState.value = state;
    defaultStorageSlug.value = resolveDefaultStorageSlug(state, null);
    emit("ownership-changed");
  } catch (error) {
    panelError.value = error.message || "Could not assign storage.";
    copyState.value = {
      ...(copyState.value || {}),
      copies: (copyState.value?.copies || []).map((item) => (
        item.instanceId === copy.instanceId
          ? { ...item, locationSlug: previousSlug, label: storageLabel(previousSlug) }
          : item
      )),
    };
  } finally {
    panelLoading.value = false;
  }
}

function applyLocalFinish(next) {
  if (props.card) {
    props.card.finish = next;
    props.card.foil = next;
  }
  emit("finish-changed", next);
}

async function onOwnedFinishToggle() {
  if (!isInteractive.value || panelLoading.value || !canToggleNonfoilFoil.value) {
    return;
  }
  const current = currentFinish.value;
  const next = current === FINISH_FOIL ? FINISH_NONFOIL : FINISH_FOIL;
  if (current === next) {
    return;
  }
  if (ownedCount.value <= 0) {
    applyLocalFinish(next);
    return;
  }
  panelLoading.value = true;
  panelError.value = "";
  try {
    const state = await changeCardOwnershipFinish(props.card, next);
    if (state) {
      copyState.value = state;
      defaultStorageSlug.value = resolveDefaultStorageSlug(state, null);
    }
    applyLocalFinish(next);
    emit("ownership-changed");
  } catch (error) {
    panelError.value = error.message || "Could not change finish.";
  } finally {
    panelLoading.value = false;
  }
}

async function onCopyFinishToggle(copy) {
  if (!isInteractive.value || panelLoading.value) {
    return;
  }
  const current = copyFinish(copy);
  const next = current === FINISH_FOIL ? FINISH_NONFOIL : FINISH_FOIL;
  if (current === next) {
    return;
  }
  if (typeof copy.instanceId !== "number") {
    if (ownedCount.value <= 0) {
      applyLocalFinish(next);
      return;
    }
    await onOwnedFinishToggle();
    return;
  }
  panelLoading.value = true;
  panelError.value = "";
  try {
    const state = await updateCardCopyFinish(props.card, copy.instanceId, next);
    copyState.value = state;
    defaultStorageSlug.value = resolveDefaultStorageSlug(state, null);
    applyLocalFinish(next);
    emit("ownership-changed");
  } catch (error) {
    panelError.value = error.message || "Could not change finish.";
    try {
      const payload = await fetchCardCopyState(props.card);
      if (payload) {
        copyState.value = payload.state;
        defaultStorageSlug.value = resolveDefaultStorageSlug(payload.state, payload.settings);
      }
    } catch {
      // Keep the error message visible.
    }
  } finally {
    panelLoading.value = false;
  }
}

async function addCopy() {
  await onAdjust(1);
}

defineExpose({ addCopy });
</script>

<template>
  <div
    v-if="isInteractive"
    class="card-copy-controls"
    :class="`card-copy-controls--${variant}`"
    @click.stop
    @mousedown.stop
  >
    <div class="card-interactive-owned card-copy-controls-owned">
      <span class="card-interactive-label">Owned</span>
      <div class="card-copy-controls-owned-row">
        <div class="card-interactive-stepper">
          <button
            type="button"
            class="card-interactive-step"
            :disabled="panelLoading || ownedCount <= 0"
            aria-label="Remove one owned copy"
            @click.stop="onAdjust(-1)"
          >
            −
          </button>
          <span class="card-interactive-count">{{ ownedCount }}</span>
          <button
            type="button"
            class="card-interactive-step"
            :disabled="panelLoading || !canAddCopy"
            :aria-label="canAddCopy ? 'Add one owned copy' : `Maximum ${maxCopies} copies`"
            @click.stop="onAdjust(1)"
          >
            +
          </button>
        </div>
        <FinishToggleButton
          v-if="showOwnedFinishToggle"
          :finish="currentFinish"
          :disabled="panelLoading"
          @toggle="onOwnedFinishToggle"
        />
      </div>
    </div>

    <div v-if="displayCopyRows.length" class="card-interactive-copies">
      <div
        v-for="(copy, index) in displayCopyRows"
        :key="copy.instanceId"
        class="card-interactive-copy"
      >
        <span class="card-interactive-label">Copy {{ index + 1 }}</span>
        <div class="card-interactive-copy-controls">
          <FinishToggleButton
            v-if="showCopyFinishToggle(copy)"
            :finish="copyFinish(copy)"
            :disabled="panelLoading"
            @toggle="onCopyFinishToggle(copy)"
          />
          <StorageLocationSelect
            :model-value="copy.locationSlug"
            :locations="storageLocations"
            :include-types="['storage', 'binder']"
            :disabled="panelLoading || !storageLocations.length || typeof copy.instanceId !== 'number'"
            compact
            :aria-label="`Storage for copy ${index + 1}`"
            @update:model-value="(slug) => onCopyStorageSelect(copy, slug)"
            @open-change="emit('menu-open-change', $event)"
          />
        </div>
      </div>
    </div>

    <p v-if="panelLoading" class="card-interactive-status">Updating…</p>
    <p v-else-if="panelError" class="card-interactive-status error">{{ panelError }}</p>
  </div>
</template>
