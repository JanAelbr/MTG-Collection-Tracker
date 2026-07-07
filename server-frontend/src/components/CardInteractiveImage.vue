<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  adjustCardCopyCount,
  applyOptimisticCopyCount,
  changeCardOwnershipFinish,
  effectiveDeckOwnedQty,
  fetchCardCopyState,
  isEffectivelyOwned,
  normalizeCardMenuTarget,
  ownershipRevision,
  storageLocations,
  updateCardCopyStorage,
} from "../composables/cardContextMenu";
import StorageLocationSelect from "./StorageLocationSelect.vue";
import {
  canManageFinish,
  cardFinish,
  cardRouteQuery,
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  finishLabel,
  normalizeFinish,
} from "../utils/finishes";

const MAX_COPIES = 99;

const props = defineProps({
  src: { type: String, default: "" },
  alt: { type: String, default: "" },
  card: { type: Object, default: null },
  imgClass: { type: [String, Array, Object], default: "" },
  loading: { type: String, default: "lazy" },
  showDetails: { type: Boolean, default: true },
});

const emit = defineEmits(["finish-changed", "ownership-changed"]);

const router = useRouter();
const isHovered = ref(false);
const panelLoading = ref(false);
const panelError = ref("");
const copyState = ref(null);
const defaultStorageSlug = ref("");
let leaveTimer = null;
let loadToken = 0;

const isInteractive = computed(() => Boolean(props.card && props.src && normalizeCardMenuTarget(props.card)));
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
const canClickToAdd = computed(() => isInteractive.value && ownedCount.value === 0 && canAddCopy.value);
const effectivelyOwned = computed(() => {
  ownershipRevision.value;
  return isEffectivelyOwned(props.card);
});
const availableFinishes = computed(() =>
  [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].filter((finish) => canManageFinish(props.card, finish)),
);
const currentFinish = computed(() => cardFinish(props.card));
const showFinishSelector = computed(
  () => effectivelyOwned.value && availableFinishes.value.length > 1,
);

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
    if (isHovered.value) {
      loadPanelState();
    }
  },
);

function clearLeaveTimer() {
  if (leaveTimer) {
    clearTimeout(leaveTimer);
    leaveTimer = null;
  }
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

function onPointerEnter() {
  if (!isInteractive.value) {
    return;
  }
  clearLeaveTimer();
  isHovered.value = true;
  if (!copyState.value && !panelLoading.value) {
    loadPanelState();
  }
}

function onPointerLeave() {
  clearLeaveTimer();
  leaveTimer = setTimeout(() => {
    isHovered.value = false;
    panelError.value = "";
  }, 120);
}

function onOverlayClick(event) {
  event.preventDefault();
  event.stopPropagation();
  if (canClickToAdd.value) {
    onAdjust(1);
  }
}

function onCardClick(event) {
  if (!canClickToAdd.value || panelLoading.value) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  onAdjust(1);
}

function stopNavigation(event) {
  event.preventDefault();
  event.stopPropagation();
}

function optimisticCopies(previousCount, nextCount) {
  const current = [...(copyState.value?.copies || [])];
  if (nextCount > previousCount) {
    const slug = defaultStorageSlug.value || storageLocations.value[0]?.slug || "storage:general";
    current.push({
      instanceId: `temp-${Date.now()}-${current.length}`,
      locationSlug: slug,
      label: storageLabel(slug),
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
  const optimisticCount = Math.max(0, previousCount + delta);
  panelLoading.value = true;
  panelError.value = "";
  copyState.value = {
    ...(copyState.value || {}),
    ownedCount: optimisticCount,
    copies: optimisticCopies(previousCount, optimisticCount),
  };
  applyOptimisticCopyCount(props.card, optimisticCount, previousCount);
  if (previousCount === 0 && optimisticCount >= 1) {
    clearLeaveTimer();
    isHovered.value = false;
  }
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

async function onFinishChange(event) {
  const toFinish = normalizeFinish(event.target.value);
  if (!isInteractive.value || panelLoading.value || toFinish === currentFinish.value) {
    return;
  }
  panelLoading.value = true;
  panelError.value = "";
  try {
    const state = await changeCardOwnershipFinish(props.card, toFinish);
    copyState.value = state;
    defaultStorageSlug.value = resolveDefaultStorageSlug(state, null);
    event.target.value = String(toFinish);
    emit("finish-changed", toFinish);
  } catch (error) {
    panelError.value = error.message || "Could not change finish.";
    event.target.value = String(currentFinish.value);
  } finally {
    panelLoading.value = false;
  }
}

function onViewDetails(event) {
  event.preventDefault();
  event.stopPropagation();
  const target = normalizeCardMenuTarget(props.card);
  if (!target) {
    return;
  }
  router.push({
    name: "card",
    params: { setCode: target.setCode, collectorNumber: target.collectorNumber },
    query: cardRouteQuery(target.finish),
  });
}
</script>

<template>
  <div
    v-if="src"
    class="card-interactive"
    :class="{
      'is-interactive': isInteractive,
      'is-hovered': isHovered,
      'is-owned': effectivelyOwned,
      'is-unowned': isInteractive && !effectivelyOwned,
      'is-clickable-add': canClickToAdd,
    }"
    @click="onCardClick"
    @mouseenter="onPointerEnter"
    @mouseleave="onPointerLeave"
  >
    <img
      :src="src"
      :alt="alt"
      :loading="loading"
      :class="['card-interactive-image', imgClass]"
    >

    <div
      v-if="isInteractive && isHovered"
      class="card-interactive-overlay"
      @click.stop="onOverlayClick"
      @mousedown.stop="stopNavigation"
      @mouseenter="onPointerEnter"
      @mouseleave="onPointerLeave"
    >
      <button
        v-if="showDetails"
        type="button"
        class="card-interactive-action card-interactive-details"
        @click="onViewDetails"
      >
        Details
      </button>

      <div
        v-if="showFinishSelector"
        class="card-interactive-finish"
        @click.stop
        @mousedown.stop
      >
        <span class="card-interactive-label">Finish</span>
        <select
          :value="currentFinish"
          :disabled="panelLoading"
          @change="onFinishChange"
          @click.stop
          @mousedown.stop
        >
          <option
            v-for="finish in availableFinishes"
            :key="finish"
            :value="finish"
          >
            {{ finishLabel(finish) }}
          </option>
        </select>
      </div>

      <div class="card-interactive-owned" @click.stop @mousedown.stop>
        <span class="card-interactive-label">Owned</span>
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

      <div
        v-if="copies.length"
        class="card-interactive-copies"
        @click.stop
        @mousedown.stop
      >
        <label
          v-for="(copy, index) in copies"
          :key="copy.instanceId"
          class="card-interactive-copy"
          @click.stop
          @mousedown.stop
        >
          <span class="card-interactive-label">Copy {{ index + 1 }}</span>
          <StorageLocationSelect
            :model-value="copy.locationSlug"
            :locations="storageLocations"
            :disabled="panelLoading || !storageLocations.length || typeof copy.instanceId !== 'number'"
            compact
            :aria-label="`Storage for copy ${index + 1}`"
            @update:model-value="(slug) => onCopyStorageSelect(copy, slug)"
          />
        </label>
      </div>

      <p v-if="panelLoading" class="card-interactive-status">Updating…</p>
      <p v-else-if="panelError" class="card-interactive-status error">{{ panelError }}</p>
    </div>
  </div>
</template>
