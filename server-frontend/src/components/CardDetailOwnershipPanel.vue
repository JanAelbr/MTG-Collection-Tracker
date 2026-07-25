<script setup>
import "../styles/card-detail.css";
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { api, clearClientCache } from "../api";
import {
  adjustCardCopyCount,
  storageLocations,
} from "../composables/cardContextMenu";
import DeckAddControl from "./DeckAddControl.vue";
import DeckCardQtyControl from "./DeckCardQtyControl.vue";
import DeckOwnedToggle from "./DeckOwnedToggle.vue";
import StorageLocationIcon from "./StorageLocationIcon.vue";
import StorageLocationSelect from "./StorageLocationSelect.vue";
import { formatEuro, formatProfit } from "../utils/format";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  canManageFinish,
  finishLabel,
  normalizeFinish,
} from "../utils/finishes";

const props = defineProps({
  card: { type: Object, required: true },
  manageableFinishes: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  defaultDeckId: { type: String, default: "" },
});

const emit = defineEmits(["ownership-changed", "finish-selected", "deck-changed"]);

const activeTab = ref("summary");
const busy = ref(false);
const error = ref("");
const purchaseDrafts = ref({});
const selectNewestAfterReload = ref(false);
const pendingNewInstanceId = ref("");

const instances = computed(() => props.card?.ownedInstances || []);
const deckMemberships = computed(() => props.card?.deckMemberships || []);
const summaryRows = computed(() => props.card?.ownershipSummary || []);
const showSummaryTab = computed(() => instances.value.length > 1);
const showTabBar = computed(() => true);

const finishOptions = computed(() => {
  const finishes = props.manageableFinishes.length
    ? props.manageableFinishes
    : [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED];
  return finishes.map((finish) => ({
    value: normalizeFinish(finish),
    label: finishLabel(finish),
  }));
});

const activeInstance = computed(() => {
  if (activeTab.value === "summary" || activeTab.value === "empty") {
    return null;
  }
  return instances.value.find(
    (instance) => String(instance.instanceId) === String(activeTab.value),
  );
});

function isDeckInstance(instance) {
  const type = String(instance?.locationType || "").toLowerCase();
  const slug = String(instance?.locationSlug || "").toLowerCase();
  return type === "deck" || slug.startsWith("deck:");
}

function instanceFinishTitle(instance) {
  const sameFinish = instances.value.filter((row) => row.finish === instance.finish);
  let label = instance.finishLabel || finishLabel(instance.finish);
  if (sameFinish.length > 1) {
    label = `${label} #${instance.finishIndex}`;
  }
  if (isDeckInstance(instance) && instance.locationLabel) {
    return `${label} · ${instance.locationLabel}`;
  }
  return label;
}

function instanceFinishIndex(instance) {
  const sameFinish = instances.value.filter((row) => row.finish === instance.finish);
  return sameFinish.length > 1 ? instance.finishIndex : null;
}

function decksForInstance(instance) {
  if (!instance) {
    return [];
  }
  const finish = normalizeFinish(instance.finish);
  const memberships = deckMemberships.value.filter(
    (row) => normalizeFinish(row.finish) === finish,
  );
  if (!memberships.length) {
    return [];
  }

  const claimedSlugs = new Set(
    instances.value
      .filter((row) => row.instanceId !== instance.instanceId && isDeckInstance(row))
      .map((row) => String(row.locationSlug || "").toLowerCase())
      .filter(Boolean),
  );

  const finishInstances = instances.value
    .filter((row) => normalizeFinish(row.finish) === finish)
    .slice()
    .sort((left, right) => left.instanceId - right.instanceId);

  return memberships.filter((membership) => {
    const slug = String(membership.locationSlug || "").toLowerCase();
    if (String(instance.locationSlug || "").toLowerCase() === slug) {
      return true;
    }
    if (claimedSlugs.has(slug)) {
      return false;
    }
    const primary =
      finishInstances.find((row) => String(row.locationSlug || "").toLowerCase() === slug)
      || finishInstances[0];
    return primary && primary.instanceId === instance.instanceId;
  });
}

function deckCardForMembership(membership) {
  return {
    ...props.card,
    finish: membership.finish,
    qty: membership.qty,
    ownedQty: membership.ownedQty,
    section: membership.section,
  };
}

function deckRoute(membership) {
  return {
    name: "decks",
    query: { deck: String(membership.deckId) },
  };
}

function syncPurchaseDrafts() {
  const next = {};
  for (const instance of instances.value) {
    next[instance.instanceId] =
      instance.purchaseValue != null ? String(instance.purchaseValue) : "";
  }
  purchaseDrafts.value = next;
}

function newestInstanceId() {
  if (!instances.value.length) {
    return null;
  }
  return String(
    instances.value.reduce((latest, instance) =>
      instance.instanceId > latest.instanceId ? instance : latest,
    ).instanceId,
  );
}

function tabExists(tabId) {
  if (tabId === "summary") {
    return showSummaryTab.value;
  }
  if (tabId === "empty") {
    return !instances.value.length;
  }
  return instances.value.some((instance) => String(instance.instanceId) === String(tabId));
}

function syncDefaultTab() {
  if (pendingNewInstanceId.value) {
    const pendingId = pendingNewInstanceId.value;
    if (tabExists(pendingId)) {
      pendingNewInstanceId.value = "";
      selectNewestAfterReload.value = false;
      activeTab.value = pendingId;
      const instance = instances.value.find(
        (row) => String(row.instanceId) === pendingId,
      );
      if (instance) {
        emit("finish-selected", instance.finish);
      }
      return;
    }
    // Keep waiting for the reloaded card payload to include the new copy.
    return;
  }

  if (selectNewestAfterReload.value) {
    const newestId = newestInstanceId();
    if (newestId) {
      selectNewestAfterReload.value = false;
      activeTab.value = newestId;
      const instance = instances.value.find(
        (row) => String(row.instanceId) === newestId,
      );
      if (instance) {
        emit("finish-selected", instance.finish);
      }
      return;
    }
  }

  if (!instances.value.length) {
    activeTab.value = "empty";
    return;
  }

  if (instances.value.length === 1) {
    if (activeTab.value === "empty") {
      activeTab.value = String(instances.value[0].instanceId);
      emit("finish-selected", instances.value[0].finish);
      return;
    }
    const soleId = String(instances.value[0].instanceId);
    if (activeTab.value !== soleId && activeTab.value !== "summary") {
      activeTab.value = soleId;
      emit("finish-selected", instances.value[0].finish);
    }
    return;
  }

  if (activeTab.value === "empty") {
    activeTab.value = "summary";
    return;
  }

  if (!tabExists(activeTab.value)) {
    activeTab.value = "summary";
  }
}

function selectTab(tabId) {
  activeTab.value = tabId;
  if (tabId === "empty" || tabId === "summary") {
    return;
  }
  const instance = instances.value.find(
    (row) => String(row.instanceId) === String(tabId),
  );
  if (instance) {
    emit("finish-selected", instance.finish);
  }
}

function selectSummaryRow(finish) {
  const instance = instances.value.find((row) => row.finish === finish);
  if (instance) {
    selectTab(String(instance.instanceId));
  }
}

function finishChangeOptions(instance) {
  return finishOptions.value.filter((option) => {
    if (option.value === instance.finish) {
      return true;
    }
    return canManageFinish(props.card, option.value);
  });
}

function parsePurchaseInput(raw) {
  if (raw === "" || raw == null) {
    return null;
  }
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) {
    return undefined;
  }
  return value;
}

async function savePurchasePrice(instance) {
  const draft = purchaseDrafts.value[instance.instanceId];
  const parsed = parsePurchaseInput(draft);
  if (parsed === undefined) {
    syncPurchaseDrafts();
    return;
  }
  if (parsed == null) {
    syncPurchaseDrafts();
    return;
  }
  const current = instance.purchaseValue;
  if (current != null && Math.abs(parsed - current) < 0.0001) {
    return;
  }
  if (current == null && parsed === 0) {
    return;
  }

  busy.value = true;
  error.value = "";
  try {
    await api.updateCardInstance(instance.instanceId, { purchaseValue: parsed });
    clearClientCache();
    emit("ownership-changed");
  } catch (err) {
    error.value = err.message || "Could not save purchase price.";
    syncPurchaseDrafts();
  } finally {
    busy.value = false;
  }
}

async function onFinishSelect(instance, toFinish) {
  const normalized = normalizeFinish(toFinish);
  if (normalized === instance.finish) {
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await api.updateCardInstance(instance.instanceId, { finish: normalized });
    clearClientCache();
    emit("ownership-changed");
  } catch (err) {
    error.value = err.message || "Could not change finish.";
  } finally {
    busy.value = false;
  }
}

async function onStorageSelect(instance, locationSlug) {
  if (!locationSlug || locationSlug === instance.locationSlug) {
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await api.updateCardInstance(instance.instanceId, { locationSlug });
    clearClientCache();
    emit("ownership-changed");
  } catch (err) {
    error.value = err.message || "Could not update storage.";
  } finally {
    busy.value = false;
  }
}

async function onRemoveInstance(instance) {
  if (isDeckInstance(instance)) {
    error.value = "Deck copies are managed from deck ownership. Unown the card in the deck first.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await api.deleteCardInstance(instance.instanceId);
    clearClientCache();
    emit("ownership-changed");
  } catch (err) {
    error.value = err.message || "Could not remove copy.";
  } finally {
    busy.value = false;
  }
}

async function onAddCopy() {
  const preferredFinish = finishOptions.value.some((option) => option.value === FINISH_NONFOIL)
    ? FINISH_NONFOIL
    : finishOptions.value[0]?.value;
  if (preferredFinish == null) {
    error.value = "No finish available to add.";
    return;
  }
  busy.value = true;
  error.value = "";
  const previousIds = new Set(
    instances.value.map((instance) => String(instance.instanceId)),
  );
  selectNewestAfterReload.value = true;
  try {
    const state = await adjustCardCopyCount(
      {
        setCode: props.card.setCode,
        collectorNumber: props.card.collectorNumber,
        finish: preferredFinish,
      },
      1,
    );
    const copies = state?.copies || [];
    const created = copies.find(
      (copy) => !previousIds.has(String(copy.instanceId)),
    );
    const fallback = copies.length
      ? copies.reduce((latest, copy) =>
          copy.instanceId > latest.instanceId ? copy : latest,
        )
      : null;
    const selected = created || fallback;
    if (selected) {
      pendingNewInstanceId.value = String(selected.instanceId);
    }
    clearClientCache();
    emit("ownership-changed");
  } catch (err) {
    selectNewestAfterReload.value = false;
    pendingNewInstanceId.value = "";
    error.value = err.message || "Could not add owned copy.";
  } finally {
    busy.value = false;
  }
}

function onDeckChanged(result) {
  emit("deck-changed", result);
  emit("ownership-changed");
}

watch(
  () => [props.card?.ownedInstances, props.card?.ownershipSummary, props.card?.deckMemberships],
  () => {
    syncPurchaseDrafts();
    syncDefaultTab();
  },
  { immediate: true, deep: true },
);

onMounted(async () => {
  if (!storageLocations.value.length) {
    const payload = await api.listStorageLocations();
    storageLocations.value = payload.locations || [];
  }
});
</script>

<template>
  <div class="card-detail-ownership-panel card-owned-qty-tile">
    <div class="card-owned-qty-tile-row card-owned-qty-tile-row-head">
      <span class="card-owned-qty-tile-label">Owned copies</span>
      <span v-if="instances.length" class="card-owned-qty-tile-total">{{ instances.length }}</span>
    </div>

    <div v-if="showTabBar" class="card-detail-browser-tabs">
      <button
        v-if="showSummaryTab"
        type="button"
        class="card-detail-browser-tab"
        :class="{ active: activeTab === 'summary' }"
        @click="selectTab('summary')"
      >
        Summary
      </button>
      <div
        v-for="instance in instances"
        :key="instance.instanceId"
        role="tab"
        tabindex="0"
        class="card-detail-browser-tab card-detail-browser-tab-instance"
        :class="{
          active: activeTab === String(instance.instanceId),
          'is-foil': normalizeFinish(instance.finish) === FINISH_FOIL,
          'is-etched': normalizeFinish(instance.finish) === FINISH_ETCHED,
        }"
        :aria-selected="activeTab === String(instance.instanceId)"
        :aria-label="instanceFinishTitle(instance)"
        :title="instanceFinishTitle(instance)"
        @click="selectTab(String(instance.instanceId))"
        @keydown.enter.prevent="selectTab(String(instance.instanceId))"
      >
        <svg
          v-if="normalizeFinish(instance.finish) === FINISH_FOIL"
          class="card-detail-browser-tab-finish-icon"
          viewBox="0 0 16 16"
          aria-hidden="true"
        >
          <path
            d="M8 1.2 9.7 5.9 14.6 6.1 10.7 9.1 12.1 14 8 11.4 3.9 14 5.3 9.1 1.4 6.1 6.3 5.9Z"
            fill="currentColor"
          />
        </svg>
        <svg
          v-else-if="normalizeFinish(instance.finish) === FINISH_ETCHED"
          class="card-detail-browser-tab-finish-icon"
          viewBox="0 0 16 16"
          aria-hidden="true"
        >
          <path
            d="M8 1.5 14 8 8 14.5 2 8Z"
            fill="currentColor"
          />
        </svg>
        <svg
          v-else
          class="card-detail-browser-tab-finish-icon"
          viewBox="0 0 16 16"
          aria-hidden="true"
        >
          <rect
            x="3.25"
            y="2.25"
            width="9.5"
            height="11.5"
            rx="1.35"
            fill="currentColor"
          />
          <rect
            x="5.1"
            y="5"
            width="5.8"
            height="1.1"
            rx="0.35"
            fill="#fff"
            opacity="0.42"
          />
          <rect
            x="5.1"
            y="7.1"
            width="4.2"
            height="1.1"
            rx="0.35"
            fill="#fff"
            opacity="0.42"
          />
        </svg>
        <span
          v-if="instanceFinishIndex(instance)"
          class="card-detail-browser-tab-finish-index"
        >{{ instanceFinishIndex(instance) }}</span>
        <button
          type="button"
          class="card-detail-browser-tab-delete"
          aria-label="Delete copy"
          title="Delete copy"
          :disabled="busy || loading || isDeckInstance(instance)"
          @click.stop="onRemoveInstance(instance)"
        >
          ×
        </button>
      </div>
      <button
        type="button"
        class="card-detail-browser-tab card-detail-browser-tab-add"
        aria-label="Add non-foil copy to default storage"
        title="Add non-foil copy to default storage"
        :disabled="busy || loading || !finishOptions.length"
        @click="onAddCopy"
      >
        +
      </button>
    </div>

    <div class="card-detail-browser-panel">
      <div v-if="activeTab === 'empty'" class="card-detail-instance-fields">
        <p class="card-detail-add-copy-lead">
          No owned copies yet. Click + to add a non-foil copy to default storage.
        </p>
        <div
          v-if="deckMemberships.length"
          class="card-detail-instance-decks card-detail-summary-decks"
        >
          <p class="card-detail-instance-decks-label">In decks</p>
          <div
            v-for="membership in deckMemberships"
            :key="membership.deckCardId"
            class="card-detail-instance-deck-controls"
          >
            <div class="card-detail-instance-deck-head">
              <RouterLink
                class="card-detail-instance-deck-link"
                :to="deckRoute(membership)"
              >
                {{ membership.deckName }}
              </RouterLink>
              <DeckOwnedToggle
                :card="deckCardForMembership(membership)"
                :deck-id="String(membership.deckId)"
                compact
                @changed="onDeckChanged"
              />
            </div>
            <DeckCardQtyControl
              :card="deckCardForMembership(membership)"
              :deck-id="String(membership.deckId)"
              :deck-name="membership.deckName"
              compact
              inline
              @changed="onDeckChanged"
              @removed="onDeckChanged"
            />
          </div>
        </div>

        <DeckAddControl
          class="card-detail-storage-deck-add"
          :card="{ ...card, finish: FINISH_NONFOIL }"
          :default-deck-id="defaultDeckId"
          compact
          @added="onDeckChanged"
        />
      </div>

      <div v-else-if="activeTab === 'summary'" class="card-detail-summary-table-wrap">
        <table class="card-detail-summary-table">
          <thead>
            <tr>
              <th>Finish</th>
              <th>Copies</th>
              <th>Avg paid</th>
              <th>Current</th>
              <th>Gain / loss</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in summaryRows"
              :key="row.finish"
              class="card-detail-summary-row"
              @click="selectSummaryRow(row.finish)"
            >
              <td>{{ row.label }}</td>
              <td>{{ row.count }}</td>
              <td>{{ formatEuro(row.avgPurchase) }}</td>
              <td>{{ formatEuro(row.currentValue) }}</td>
              <td
                :class="{
                  'reports-gain': row.gainLoss != null && row.gainLoss >= 0,
                  'reports-loss': row.gainLoss != null && row.gainLoss < 0,
                }"
              >
                {{ formatProfit(row.gainLoss) }}
              </td>
            </tr>
          </tbody>
        </table>
        <div
          v-if="deckMemberships.length"
          class="card-detail-instance-decks card-detail-summary-decks"
        >
          <p class="card-detail-instance-decks-label">In decks</p>
          <ul class="card-detail-instance-decks-list">
            <li
              v-for="membership in deckMemberships"
              :key="membership.deckCardId"
              class="card-detail-instance-deck-row"
            >
              <RouterLink
                class="card-detail-instance-deck-link"
                :to="deckRoute(membership)"
              >
                {{ membership.deckName }}
              </RouterLink>
              <span class="card-detail-instance-deck-meta">
                {{ finishLabel(membership.finish) }} · {{ membership.qty }}
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div v-else-if="activeInstance" class="card-detail-instance-fields">
        <div class="card-detail-pricing-stat">
          <span class="card-detail-pricing-stat-label">Finish</span>
          <span class="card-detail-pricing-stat-value">
            <div
              class="button-group card-detail-finish-toggle"
              role="group"
              :aria-label="`Finish for copy ${activeInstance.finishIndex}`"
            >
              <button
                v-for="option in finishChangeOptions(activeInstance)"
                :key="option.value"
                type="button"
                class="filter-button"
                :class="{ active: activeInstance.finish === option.value }"
                :disabled="busy || loading"
                @click="onFinishSelect(activeInstance, option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </span>
        </div>

        <div class="card-detail-pricing-stat card-detail-pricing-stat-wide card-detail-storage-block">
          <span class="card-detail-pricing-stat-label">Storage</span>
          <span class="card-detail-pricing-stat-value card-detail-storage-controls">
            <div
              v-if="isDeckInstance(activeInstance)"
              class="card-detail-deck-storage-readonly"
            >
              <StorageLocationIcon type="deck" />
              <span>{{ activeInstance.locationLabel || "Deck storage" }}</span>
            </div>
            <StorageLocationSelect
              v-else
              class="card-detail-storage-picker"
              :model-value="activeInstance.locationSlug"
              :locations="storageLocations"
              :include-types="['storage', 'binder']"
              :disabled="busy || loading || !storageLocations.length"
              aria-label="Storage location"
              @update:model-value="(slug) => onStorageSelect(activeInstance, slug)"
            />

            <p
              v-if="isDeckInstance(activeInstance)"
              class="card-detail-deck-storage-hint"
            >
              Storage follows deck ownership. Unown in the deck to return this copy to a binder or storage.
            </p>

            <div
              v-if="decksForInstance(activeInstance).length"
              class="card-detail-instance-decks"
            >
              <div
                v-for="membership in decksForInstance(activeInstance)"
                :key="membership.deckCardId"
                class="card-detail-instance-deck-controls"
              >
                <div class="card-detail-instance-deck-head">
                  <RouterLink
                    class="card-detail-instance-deck-link"
                    :to="deckRoute(membership)"
                  >
                    {{ membership.deckName }}
                  </RouterLink>
                  <DeckOwnedToggle
                    :card="deckCardForMembership(membership)"
                    :deck-id="String(membership.deckId)"
                    compact
                    @changed="onDeckChanged"
                  />
                </div>
                <DeckCardQtyControl
                  :card="deckCardForMembership(membership)"
                  :deck-id="String(membership.deckId)"
                  :deck-name="membership.deckName"
                  compact
                  inline
                  @changed="onDeckChanged"
                  @removed="onDeckChanged"
                />
              </div>
            </div>

            <DeckAddControl
              class="card-detail-storage-deck-add"
              :card="{ ...card, finish: activeInstance.finish }"
              :default-deck-id="defaultDeckId"
              compact
              @added="onDeckChanged"
            />
          </span>
        </div>

        <div class="card-detail-pricing-stat">
          <span class="card-detail-pricing-stat-label">Current value</span>
          <span class="card-detail-pricing-stat-value">{{ formatEuro(activeInstance.currentValue) }}</span>
        </div>

        <div class="card-detail-pricing-stat">
          <span class="card-detail-pricing-stat-label">Purchase</span>
          <span class="card-detail-pricing-stat-value">
            <label class="card-detail-purchase-field">
              <span class="card-detail-purchase-currency">€</span>
              <input
                v-model="purchaseDrafts[activeInstance.instanceId]"
                type="number"
                min="0"
                step="0.01"
                inputmode="decimal"
                class="card-detail-purchase-input"
                :disabled="busy || loading"
                placeholder=""
                @blur="savePurchasePrice(activeInstance)"
                @keydown.enter="$event.target.blur()"
              >
            </label>
          </span>
        </div>

        <div class="card-detail-pricing-stat">
          <span class="card-detail-pricing-stat-label">Gain / loss</span>
          <span
            class="card-detail-pricing-stat-value"
            :class="{
              'reports-gain': activeInstance.profitLoss != null && activeInstance.profitLoss >= 0,
              'reports-loss': activeInstance.profitLoss != null && activeInstance.profitLoss < 0,
            }"
          >
            {{ formatProfit(activeInstance.profitLoss) }}
          </span>
        </div>
      </div>
    </div>

    <p v-if="busy" class="card-owned-qty-tile-status">Updating…</p>
    <p v-else-if="error" class="card-owned-qty-tile-status error">{{ error }}</p>
  </div>
</template>
