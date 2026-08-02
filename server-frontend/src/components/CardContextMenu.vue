<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  adjustCardCopyCount,
  applyListingResultToCard,
  applyOptimisticCopyCount,
  effectiveDeckOwnedQty,
  ensureStorageLocations,
  fetchCardCopyState,
  normalizeCardMenuTarget,
  ownershipRevision,
  storageLocations,
  updateCardCopyStorage,
} from "../composables/cardContextMenu";
import { usePrintList } from "../composables/printList";
import { fetchPricingSettings } from "../composables/pricingSettings";
import ListForSaleModal from "./ListForSaleModal.vue";
import StorageLocationSelect from "./StorageLocationSelect.vue";
import {
  canManageFinish,
  cardFinish,
  cardRouteQuery,
  cardSupportsNonfoilFoilToggle,
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  finishLabel,
  normalizeFinish,
} from "../utils/finishes";

const MAX_COPIES = 99;

const props = defineProps({
  open: { type: Boolean, default: false },
  card: { type: Object, default: null },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
});

const emit = defineEmits(["close", "ownership-changed", "finish-changed"]);

const router = useRouter();
const printList = usePrintList();
const menuRef = ref(null);
const panelLoading = ref(false);
const panelError = ref("");
const defaultStorageSlug = ref("");
const saleModal = ref(null);
const finishStates = ref({});
const menuStyle = ref({ left: "0px", top: "0px" });
let loadToken = 0;
let listenersBound = false;

const target = computed(() => normalizeCardMenuTarget(props.card));
const isInteractive = computed(() => Boolean(target.value));
const inPrintList = computed(() => printList.has(props.card));

const manageableFinishes = computed(() => {
  if (!props.card) {
    return [];
  }
  if (cardSupportsNonfoilFoilToggle(props.card)) {
    return [FINISH_NONFOIL, FINISH_FOIL];
  }
  const current = cardFinish(props.card);
  const finishes = [];
  for (const finish of [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED]) {
    if (canManageFinish(props.card, finish) || finish === current) {
      finishes.push(finish);
    }
  }
  if (!finishes.length) {
    finishes.push(current);
  }
  return [...new Set(finishes.map((value) => normalizeFinish(value)))];
});

const finishRows = computed(() => {
  ownershipRevision.value;
  return manageableFinishes.value.map((finish) => {
    const state = finishStates.value[finish];
    // Never fall back to another finish's top-level ownedQty on the gallery tile.
    const ownedCount = state?.ownedCount != null
      ? state.ownedCount
      : ownedCountForFinishFallback(props.card, finish);
    const maxCopies = state?.maxCopies ?? MAX_COPIES;
    const copies = state?.copies ?? [];
    return {
      finish,
      label: finishLabel(finish),
      ownedCount,
      maxCopies,
      canAdd: ownedCount < maxCopies,
      copies,
    };
  });
});

function cardWithFinish(card, finish) {
  if (!card) {
    return null;
  }
  const normalized = normalizeFinish(finish);
  return {
    ...card,
    finish: normalized,
    foil: normalized,
  };
}

/** Finish-scoped count when /manager/copies has not loaded yet. */
function ownedCountForFinishFallback(card, finish) {
  if (!card) {
    return 0;
  }
  const normalized = normalizeFinish(finish);
  const isSameFinish = cardFinish(card) === normalized;
  return effectiveDeckOwnedQty({
    ...cardWithFinish(card, normalized),
    // Drop tile-level ownership that belongs only to the clicked finish.
    ownedQty: isSameFinish ? card.ownedQty : undefined,
    owned: isSameFinish ? card.owned : undefined,
    purchaseValue: isSameFinish ? card.purchaseValue : undefined,
    locations: isSameFinish ? card.locations : undefined,
    qty: undefined,
  });
}

function resolveDefaultStorageSlug(state, settings) {
  if (settings?.defaultStorageLocation) {
    return settings.defaultStorageLocation;
  }
  return storageLocations.value[0]?.slug || "storage:general";
}

function storageLabel(slug) {
  return storageLocations.value.find((location) => location.slug === slug)?.label || slug;
}

function copyFinish(copy, fallback) {
  return normalizeFinish(copy?.finish ?? fallback);
}

async function ensureDefaultsForAdd() {
  const [, settings] = await Promise.all([
    ensureStorageLocations(),
    fetchPricingSettings(),
  ]);
  defaultStorageSlug.value = resolveDefaultStorageSlug(null, settings);
}

async function loadMenuState() {
  if (!isInteractive.value || !props.card) {
    return;
  }
  const token = ++loadToken;
  panelError.value = "";
  panelLoading.value = true;
  try {
    await ensureDefaultsForAdd();
    if (token !== loadToken) {
      return;
    }
    const payloads = await Promise.all(
      manageableFinishes.value.map(async (finish) => {
        const payload = await fetchCardCopyState(cardWithFinish(props.card, finish));
        return [finish, payload];
      }),
    );
    if (token !== loadToken) {
      return;
    }
    const next = {};
    let settings = null;
    let anyState = null;
    for (const [finish, payload] of payloads) {
      if (!payload) {
        continue;
      }
      next[finish] = payload.state;
      settings = payload.settings || settings;
      anyState = payload.state || anyState;
    }
    finishStates.value = next;
    defaultStorageSlug.value = resolveDefaultStorageSlug(anyState, settings);
  } catch (error) {
    if (token !== loadToken) {
      return;
    }
    panelError.value = error.message || "Could not load card details.";
  } finally {
    if (token === loadToken) {
      panelLoading.value = false;
    }
  }
}

function positionMenu() {
  const el = menuRef.value;
  if (!el) {
    return;
  }
  const pad = 8;
  const width = el.offsetWidth || 280;
  const height = el.offsetHeight || 320;
  const maxLeft = Math.max(pad, window.innerWidth - width - pad);
  const maxTop = Math.max(pad, window.innerHeight - height - pad);
  const left = Math.min(Math.max(pad, props.x), maxLeft);
  const top = Math.min(Math.max(pad, props.y), maxTop);
  menuStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
  };
}

function close() {
  emit("close");
}

function onDocumentPointerDown(event) {
  if (saleModal.value) {
    return;
  }
  const el = menuRef.value;
  const targetEl = event.target;
  if (
    targetEl instanceof Element
    && targetEl.closest(".storage-location-picker-menu, .list-for-sale-modal-backdrop, .sell-dialog")
  ) {
    return;
  }
  if (el && targetEl instanceof Node && el.contains(targetEl)) {
    return;
  }
  close();
}

function onKeydown(event) {
  if (event.key === "Escape") {
    if (saleModal.value) {
      closeSaleModal();
      return;
    }
    close();
  }
}

function onScroll() {
  if (!saleModal.value) {
    close();
  }
}

function bindListeners() {
  if (listenersBound) {
    return;
  }
  document.addEventListener("pointerdown", onDocumentPointerDown, true);
  window.addEventListener("keydown", onKeydown);
  window.addEventListener("scroll", onScroll, true);
  window.addEventListener("resize", positionMenu);
  listenersBound = true;
}

function unbindListeners() {
  if (!listenersBound) {
    return;
  }
  document.removeEventListener("pointerdown", onDocumentPointerDown, true);
  window.removeEventListener("keydown", onKeydown);
  window.removeEventListener("scroll", onScroll, true);
  window.removeEventListener("resize", positionMenu);
  listenersBound = false;
}

watch(
  () => [props.open, props.card, props.x, props.y],
  async ([open]) => {
    if (!open) {
      loadToken += 1;
      finishStates.value = {};
      panelError.value = "";
      saleModal.value = null;
      unbindListeners();
      return;
    }
    // Defer so the opening right-click does not immediately close the menu.
    await nextTick();
    if (!props.open) {
      return;
    }
    bindListeners();
    await loadMenuState();
    await nextTick();
    positionMenu();
  },
  { immediate: true },
);

onUnmounted(() => {
  unbindListeners();
});

function onViewDetails() {
  if (!target.value) {
    return;
  }
  router.push({
    name: "card",
    params: {
      setCode: target.value.setCode,
      collectorNumber: target.value.collectorNumber,
    },
    query: cardRouteQuery(cardFinish(props.card)),
  });
  close();
}

function togglePrintList() {
  printList.toggle(props.card);
}

async function onAdjustFinish(finish, delta) {
  if (!isInteractive.value || panelLoading.value) {
    return;
  }
  const cardForFinish = cardWithFinish(props.card, finish);
  const row = finishRows.value.find((entry) => entry.finish === finish);
  const previousCount = row?.ownedCount ?? 0;
  if (delta > 0 && previousCount >= (row?.maxCopies ?? MAX_COPIES)) {
    return;
  }
  if (delta > 0) {
    await ensureDefaultsForAdd();
  }
  const optimisticCount = Math.max(0, previousCount + delta);
  panelLoading.value = true;
  panelError.value = "";
  finishStates.value = {
    ...finishStates.value,
    [finish]: {
      ...(finishStates.value[finish] || {}),
      ownedCount: optimisticCount,
    },
  };
  applyOptimisticCopyCount(cardForFinish, optimisticCount, previousCount);
  try {
    const state = await adjustCardCopyCount(
      cardForFinish,
      delta,
      delta > 0 ? defaultStorageSlug.value : undefined,
    );
    finishStates.value = {
      ...finishStates.value,
      [finish]: state,
    };
    if (cardFinish(props.card) === finish) {
      applyOptimisticCopyCount(props.card, state.ownedCount ?? optimisticCount, previousCount);
    }
    emit("ownership-changed");
  } catch (error) {
    panelError.value = error.message || "Could not update owned count.";
    try {
      const payload = await fetchCardCopyState(cardForFinish);
      if (payload) {
        finishStates.value = {
          ...finishStates.value,
          [finish]: payload.state,
        };
        defaultStorageSlug.value = resolveDefaultStorageSlug(payload.state, payload.settings);
        applyOptimisticCopyCount(cardForFinish, payload.state.ownedCount ?? 0, optimisticCount);
      }
    } catch {
      // Keep the error message visible.
    }
  } finally {
    panelLoading.value = false;
  }
}

async function onCopyStorageSelect(finish, copy, slug) {
  if (!slug || panelLoading.value || typeof copy.instanceId !== "number") {
    return;
  }
  const cardForFinish = cardWithFinish(props.card, finish);
  panelLoading.value = true;
  panelError.value = "";
  const previousSlug = copy.locationSlug;
  const currentState = finishStates.value[finish];
  finishStates.value = {
    ...finishStates.value,
    [finish]: {
      ...(currentState || {}),
      copies: (currentState?.copies || []).map((item) => (
        item.instanceId === copy.instanceId
          ? { ...item, locationSlug: slug, label: storageLabel(slug) }
          : item
      )),
    },
  };
  try {
    const state = await updateCardCopyStorage(cardForFinish, copy.instanceId, slug);
    finishStates.value = {
      ...finishStates.value,
      [finish]: state,
    };
    emit("ownership-changed");
  } catch (error) {
    panelError.value = error.message || "Could not assign storage.";
    finishStates.value = {
      ...finishStates.value,
      [finish]: {
        ...(currentState || {}),
        copies: (currentState?.copies || []).map((item) => (
          item.instanceId === copy.instanceId
            ? { ...item, locationSlug: previousSlug, label: storageLabel(previousSlug) }
            : item
        )),
      },
    };
  } finally {
    panelLoading.value = false;
  }
}

function openSaleModal(finish, copy) {
  if (!isInteractive.value || panelLoading.value || typeof copy.instanceId !== "number") {
    return;
  }
  saleModal.value = {
    card: cardWithFinish(props.card, copyFinish(copy, finish)),
    instanceId: copy.instanceId,
    listingId: copy.listingId ?? null,
    listingPrice: copy.listingPrice ?? null,
  };
}

function closeSaleModal() {
  saleModal.value = null;
}

async function onSaleModalSaved(result) {
  applyListingResultToCard(props.card, result);
  emit("ownership-changed");
  try {
    await loadMenuState();
  } catch (error) {
    panelError.value = error.message || "Could not refresh copy details.";
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && isInteractive"
      ref="menuRef"
      class="card-context-menu"
      role="menu"
      :style="menuStyle"
      @click.stop
      @contextmenu.prevent
    >
      <button
        type="button"
        class="card-context-menu-item"
        role="menuitem"
        @click="onViewDetails"
      >
        Details
      </button>

      <button
        type="button"
        class="card-context-menu-item"
        role="menuitem"
        @click="togglePrintList"
      >
        {{ inPrintList ? "Remove from print list" : "Add to print list" }}
      </button>

      <div class="card-context-menu-divider" />

      <div
        v-for="row in finishRows"
        :key="row.finish"
        class="card-context-menu-finish"
      >
        <div class="card-context-menu-finish-header">
          <span class="card-context-menu-finish-label">{{ row.label }}</span>
          <div class="card-interactive-stepper card-context-menu-stepper">
            <button
              type="button"
              class="card-interactive-step"
              :disabled="panelLoading || row.ownedCount <= 0"
              :aria-label="`Remove one ${row.label} copy`"
              @click="onAdjustFinish(row.finish, -1)"
            >
              −
            </button>
            <span class="card-interactive-count">{{ row.ownedCount }}</span>
            <button
              type="button"
              class="card-interactive-step"
              :disabled="panelLoading || !row.canAdd"
              :aria-label="row.canAdd ? `Add one ${row.label} copy` : `Maximum ${row.maxCopies} copies`"
              @click="onAdjustFinish(row.finish, 1)"
            >
              +
            </button>
          </div>
        </div>

        <div
          v-for="(copy, index) in row.copies"
          :key="copy.instanceId"
          class="card-context-menu-copy"
        >
          <StorageLocationSelect
            :model-value="copy.locationSlug"
            :locations="storageLocations"
            :include-types="['storage', 'binder']"
            :disabled="panelLoading || !storageLocations.length || typeof copy.instanceId !== 'number'"
            compact
            :aria-label="`${row.label} storage for copy ${index + 1}`"
            @update:model-value="(slug) => onCopyStorageSelect(row.finish, copy, slug)"
          />
          <button
            v-if="typeof copy.instanceId === 'number'"
            type="button"
            class="btn btn-small card-interactive-sell-btn"
            :disabled="panelLoading"
            :title="copy.forSale ? 'Update asking price' : 'List this copy for sale'"
            @click="openSaleModal(row.finish, copy)"
          >
            {{ copy.forSale ? "For sale" : "Sell" }}
          </button>
        </div>
      </div>

      <p v-if="panelLoading" class="card-context-menu-status">Updating…</p>
      <p v-else-if="panelError" class="card-context-menu-status is-error">{{ panelError }}</p>
    </div>

    <ListForSaleModal
      :open="Boolean(saleModal)"
      :card="saleModal?.card || null"
      :instance-id="saleModal?.instanceId ?? null"
      :listing-id="saleModal?.listingId ?? null"
      :listing-price="saleModal?.listingPrice ?? null"
      @close="closeSaleModal"
      @saved="onSaleModalSaved"
    />
  </Teleport>
</template>
