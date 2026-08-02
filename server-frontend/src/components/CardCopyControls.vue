<script setup>
import { computed, ref, watch } from "vue";
import {
  adjustCardCopyCount,
  applyOptimisticCopyCount,
  effectiveDeckOwnedQty,
  ensureStorageLocations,
  fetchCardCopyState,
  isEffectivelyOwned,
  normalizeCardMenuTarget,
  ownershipRevision,
  storageLocations,
} from "../composables/cardContextMenu";
import { fetchPricingSettings } from "../composables/pricingSettings";
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

const emit = defineEmits(["ownership-changed"]);

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
const canAddCopy = computed(() => ownedCount.value < maxCopies.value);

function resolveDefaultStorageSlug(state, settings) {
  if (settings?.defaultStorageLocation) {
    return settings.defaultStorageLocation;
  }
  return storageLocations.value[0]?.slug || "storage:general";
}

async function ensureDefaultsForAdd() {
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

async function onAdjust(delta) {
  if (!isInteractive.value || panelLoading.value) {
    return;
  }
  const previousCount = ownedCount.value;
  if (delta > 0 && previousCount >= maxCopies.value) {
    return;
  }
  if (delta > 0) {
    await ensureDefaultsForAdd();
  }
  const optimisticCount = Math.max(0, previousCount + delta);
  panelLoading.value = true;
  panelError.value = "";
  copyState.value = {
    ...(copyState.value || {}),
    ownedCount: optimisticCount,
  };
  applyOptimisticCopyCount(props.card, optimisticCount, previousCount);
  try {
    const state = await adjustCardCopyCount(
      props.card,
      delta,
      delta > 0 ? defaultStorageSlug.value : undefined,
    );
    copyState.value = state;
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
      </div>
    </div>

    <p v-if="panelLoading" class="card-interactive-status">Updating…</p>
    <p v-else-if="panelError" class="card-interactive-status error">{{ panelError }}</p>
  </div>
</template>
