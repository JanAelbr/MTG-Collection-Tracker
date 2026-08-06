<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api, clearClientCache } from "../api";
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
import { confirmDialog } from "../composables/confirmDialog";
import { usePrintList } from "../composables/printList";
import { fetchPricingSettings } from "../composables/pricingSettings";
import ListForSaleModal from "./ListForSaleModal.vue";
import StorageLocationIcon from "./StorageLocationIcon.vue";
import DeckOwnedToggle from "./DeckOwnedToggle.vue";
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
import {
  findStorageLocation,
  groupStorageLocations,
} from "../utils/storageLocationGroups";

const MAX_COPIES = 99;
const STORAGE_INCLUDE_TYPES = ["storage", "binder"];

const props = defineProps({
  open: { type: Boolean, default: false },
  card: { type: Object, default: null },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  /** When set, show deck-list owned toggle and optional swap/remove. */
  deckId: { type: [String, Number], default: "" },
  showDeckSwap: { type: Boolean, default: false },
  showDeckRemove: { type: Boolean, default: false },
});

const emit = defineEmits([
  "close",
  "ownership-changed",
  "finish-changed",
  "deck-changed",
  "deck-swap",
  "deck-removed",
]);

const showDeckActions = computed(() => Boolean(props.deckId && props.card));
const deckRemoveBusy = ref(false);
const deckSectionBusy = ref(false);

const deckCardSection = computed(() => {
  const section = String(props.card?.section || "main").trim().toLowerCase();
  return section || "main";
});
const canMoveToCommandZone = computed(
  () => showDeckActions.value && deckCardSection.value === "main",
);
const canMoveToMainDeck = computed(
  () => showDeckActions.value && deckCardSection.value === "commander",
);

const router = useRouter();
const printList = usePrintList();
const menuRef = ref(null);
const submenuRef = ref(null);
const panelLoading = ref(false);
const panelError = ref("");
const defaultStorageSlug = ref("");
const saleModal = ref(null);
const finishStates = ref({});
const menuStyle = ref({ left: "0px", top: "0px" });
const openSubmenu = ref(null);
const submenuStyle = ref({});
let loadToken = 0;
let listenersBound = false;

const target = computed(() => normalizeCardMenuTarget(props.card));
const isInteractive = computed(() => Boolean(target.value));
const inPrintList = computed(() => printList.has(props.card));

const storageLocationSections = computed(() => {
  const allowed = new Set(STORAGE_INCLUDE_TYPES);
  const filtered = storageLocations.value.filter((location) => {
    if (allowed.has(String(location.locationType || "").toLowerCase())) {
      return true;
    }
    return location.slug === openSubmenu.value?.copy?.locationSlug;
  });
  return groupStorageLocations(filtered);
});

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

function ownedCountForFinishFallback(card, finish) {
  if (!card) {
    return 0;
  }
  const normalized = normalizeFinish(finish);
  const isSameFinish = cardFinish(card) === normalized;
  return effectiveDeckOwnedQty({
    ...cardWithFinish(card, normalized),
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

function copyLocation(copy) {
  return findStorageLocation(storageLocations.value, copy?.locationSlug) || {
    slug: copy?.locationSlug,
    label: copy?.label || copy?.locationSlug || "Storage",
    locationType: String(copy?.locationSlug || "").startsWith("deck:") ? "deck" : "storage",
  };
}

function copyMenuLabel(copy, index, total) {
  const location = copyLocation(copy);
  if (total <= 1) {
    return location.label;
  }
  return `Copy ${index + 1} · ${location.label}`;
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

function positionSubmenu(triggerEl) {
  const submenuEl = submenuRef.value;
  if (!triggerEl || !submenuEl) {
    return;
  }
  const pad = 8;
  const gap = 4;
  const triggerRect = triggerEl.getBoundingClientRect();
  const submenuWidth = submenuEl.offsetWidth || 220;
  const submenuHeight = submenuEl.offsetHeight || 240;
  let left = triggerRect.right + gap;
  if (left + submenuWidth + pad > window.innerWidth) {
    left = Math.max(pad, triggerRect.left - gap - submenuWidth);
  }
  let top = triggerRect.top;
  if (top + submenuHeight + pad > window.innerHeight) {
    top = Math.max(pad, window.innerHeight - submenuHeight - pad);
  }
  submenuStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
  };
}

function closeSubmenu() {
  openSubmenu.value = null;
  submenuStyle.value = {};
}

async function toggleSubmenu(finish, copy, event) {
  if (!copy || typeof copy.instanceId !== "number") {
    return;
  }
  const key = `${finish}|${copy.instanceId}`;
  if (openSubmenu.value?.key === key) {
    closeSubmenu();
    return;
  }
  openSubmenu.value = { key, finish, copy };
  await nextTick();
  positionSubmenu(event.currentTarget);
}

function close() {
  closeSubmenu();
  emit("close");
}

function onDocumentPointerDown(event) {
  if (saleModal.value) {
    return;
  }
  const targetEl = event.target;
  if (
    targetEl instanceof Element
    && targetEl.closest(
      ".card-context-menu-submenu, .list-for-sale-modal-backdrop, .sell-dialog, .confirm-modal-backdrop",
    )
  ) {
    return;
  }
  const menuEl = menuRef.value;
  if (menuEl && targetEl instanceof Node && menuEl.contains(targetEl)) {
    return;
  }
  close();
}

function onKeydown(event) {
  if (event.key === "Escape") {
    if (document.querySelector(".confirm-modal-backdrop")) {
      return;
    }
    if (saleModal.value) {
      closeSaleModal();
      return;
    }
    if (openSubmenu.value) {
      closeSubmenu();
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
      closeSubmenu();
      unbindListeners();
      return;
    }
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

function onDeckOwnedChanged(result) {
  emit("deck-changed", result);
  emit("ownership-changed");
}

function onDeckSwap() {
  emit("deck-swap", props.card);
  close();
}

async function onMoveDeckSection(toSection) {
  if (!props.deckId || !props.card || deckSectionBusy.value) {
    return;
  }
  const setCode = props.card.setCode;
  const collectorNumber = props.card.collectorNumber;
  if (!setCode || collectorNumber == null || String(collectorNumber).trim() === "") {
    return;
  }
  const fromSection = deckCardSection.value;
  if (fromSection === toSection) {
    return;
  }
  deckSectionBusy.value = true;
  panelError.value = "";
  try {
    const result = await api.moveDeckCardSection(props.deckId, {
      setCode,
      collectorNumber,
      finish: cardFinish(props.card),
      fromSection,
      toSection,
    });
    clearClientCache();
    emit("deck-changed", result);
    close();
  } catch (error) {
    panelError.value = error?.message || "Could not move card.";
  } finally {
    deckSectionBusy.value = false;
  }
}

async function onDeckRemove() {
  if (!props.deckId || !props.card || deckRemoveBusy.value) {
    return;
  }
  const setCode = props.card.setCode;
  const collectorNumber = props.card.collectorNumber;
  if (!setCode || collectorNumber == null || String(collectorNumber).trim() === "") {
    return;
  }
  const name = props.card.cardName || props.card.name || "this card";
  const ok = await confirmDialog({
    title: "Remove card",
    message: `Remove ${name} from this deck?`,
    confirmLabel: "Remove",
    danger: true,
  });
  if (!ok) {
    return;
  }
  const qty = Math.max(1, Number(props.card.qty) || 1);
  const section = String(props.card.section || "main").trim().toLowerCase() || "main";
  deckRemoveBusy.value = true;
  panelError.value = "";
  try {
    const result = await api.removeCardFromDeck(props.deckId, {
      setCode,
      collectorNumber,
      finish: cardFinish(props.card),
      section,
      qty,
    });
    clearClientCache();
    emit("deck-removed", result);
    emit("deck-changed", result);
    close();
  } catch (error) {
    panelError.value = error?.message || "Could not remove card from deck.";
  } finally {
    deckRemoveBusy.value = false;
  }
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
    if (openSubmenu.value?.copy?.instanceId === copy.instanceId) {
      const updatedCopy = state.copies?.find((item) => item.instanceId === copy.instanceId);
      if (updatedCopy) {
        openSubmenu.value = {
          ...openSubmenu.value,
          copy: updatedCopy,
        };
      }
    }
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
  closeSubmenu();
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

      <template v-if="showDeckActions">
        <div class="card-context-menu-divider" />
        <div class="card-context-menu-deck-owned" @click.stop>
          <DeckOwnedToggle
            :card="card"
            :deck-id="String(deckId)"
            show-label
            @changed="onDeckOwnedChanged"
          />
        </div>
        <button
          v-if="showDeckSwap"
          type="button"
          class="card-context-menu-item"
          role="menuitem"
          @click="onDeckSwap"
        >
          Swap with owned card…
        </button>
        <button
          v-if="canMoveToCommandZone"
          type="button"
          class="card-context-menu-item"
          role="menuitem"
          :disabled="deckSectionBusy || panelLoading"
          @click="onMoveDeckSection('commander')"
        >
          {{ deckSectionBusy ? "Moving…" : "Move to command zone" }}
        </button>
        <button
          v-if="canMoveToMainDeck"
          type="button"
          class="card-context-menu-item"
          role="menuitem"
          :disabled="deckSectionBusy || panelLoading"
          @click="onMoveDeckSection('main')"
        >
          {{ deckSectionBusy ? "Moving…" : "Move to main deck" }}
        </button>
        <button
          v-if="showDeckRemove"
          type="button"
          class="card-context-menu-item card-context-menu-item--danger"
          role="menuitem"
          :disabled="deckRemoveBusy || panelLoading"
          @click="onDeckRemove"
        >
          {{ deckRemoveBusy ? "Removing…" : "Remove from deck" }}
        </button>
      </template>

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

        <button
          v-for="(copy, index) in row.copies"
          :key="copy.instanceId"
          type="button"
          class="card-context-menu-item card-context-menu-submenu-trigger"
          :class="{ 'is-open': openSubmenu?.key === `${row.finish}|${copy.instanceId}` }"
          :disabled="panelLoading || typeof copy.instanceId !== 'number'"
          role="menuitem"
          :aria-haspopup="true"
          :aria-expanded="openSubmenu?.key === `${row.finish}|${copy.instanceId}` ? 'true' : 'false'"
          @click="toggleSubmenu(row.finish, copy, $event)"
        >
          <StorageLocationIcon :type="copyLocation(copy).locationType" />
          <span class="card-context-menu-submenu-label">{{ copyMenuLabel(copy, index, row.copies.length) }}</span>
          <span class="card-context-menu-submenu-chevron" aria-hidden="true">›</span>
        </button>
      </div>

      <p v-if="panelLoading" class="card-context-menu-status">Updating…</p>
      <p v-else-if="panelError" class="card-context-menu-status is-error">{{ panelError }}</p>
    </div>

    <div
      v-if="openSubmenu"
      ref="submenuRef"
      class="card-context-menu card-context-menu-submenu"
      role="menu"
      :style="submenuStyle"
      @click.stop
      @contextmenu.prevent
    >
      <template v-for="(section, sectionIndex) in storageLocationSections" :key="section.type">
        <div
          v-if="sectionIndex > 0"
          class="card-context-menu-divider"
        />
        <div class="card-context-menu-submenu-section">
          <div class="card-context-menu-submenu-heading">
            <StorageLocationIcon :type="section.type" />
            <span>{{ section.label }}</span>
          </div>
          <button
            v-for="location in section.locations"
            :key="location.slug"
            type="button"
            class="card-context-menu-item"
            :class="{ 'is-selected': location.slug === openSubmenu.copy.locationSlug }"
            role="menuitem"
            :disabled="panelLoading"
            @click="onCopyStorageSelect(openSubmenu.finish, openSubmenu.copy, location.slug)"
          >
            <StorageLocationIcon :type="location.locationType" />
            <span>{{ location.label }}</span>
          </button>
        </div>
      </template>

      <div class="card-context-menu-divider" />

      <button
        v-if="typeof openSubmenu.copy.instanceId === 'number'"
        type="button"
        class="card-context-menu-item card-context-menu-item--sale"
        role="menuitem"
        :disabled="panelLoading"
        @click="openSaleModal(openSubmenu.finish, openSubmenu.copy)"
      >
        <svg class="card-context-menu-item-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path
            d="M21.41 11.58l-9-9C12.05 2.22 11.55 2 11 2H4c-1.1 0-2 .9-2 2v7c0 .55.22 1.05.59 1.42l9 9c.36.36.86.58 1.41.58s1.05-.22 1.41-.59l7-7c.37-.36.59-.86.59-1.41 0-.55-.23-1.06-.59-1.42zM5.5 7C4.67 7 4 6.33 4 5.5S4.67 4 5.5 4 7 4.67 7 5.5 6.33 7 5.5 7z"
            fill="currentColor"
          />
        </svg>
        <span>{{ openSubmenu.copy.forSale ? "Update for sale" : "List for sale" }}</span>
      </button>
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
