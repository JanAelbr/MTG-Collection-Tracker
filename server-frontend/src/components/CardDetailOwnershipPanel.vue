<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import {
  adjustCardCopyCount,
  storageLocations,
} from "../composables/cardContextMenu";
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
});

const emit = defineEmits(["ownership-changed", "finish-selected"]);

const activeTab = ref("summary");
const busy = ref(false);
const error = ref("");
const purchaseDrafts = ref({});
const addFinish = ref(FINISH_NONFOIL);
const selectNewestAfterReload = ref(false);

const instances = computed(() => props.card?.ownedInstances || []);
const summaryRows = computed(() => props.card?.ownershipSummary || []);
const showSummaryTab = computed(() => instances.value.length > 1);
const showTabBar = computed(() => finishOptions.value.length > 0);

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
  if (activeTab.value === "summary" || activeTab.value === "add") {
    return null;
  }
  return instances.value.find(
    (instance) => String(instance.instanceId) === String(activeTab.value),
  );
});

function instanceTabLabel(instance) {
  const sameFinish = instances.value.filter((row) => row.finish === instance.finish);
  if (sameFinish.length > 1) {
    return `${instance.finishLabel} #${instance.finishIndex}`;
  }
  return instance.finishLabel;
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
  if (tabId === "add") {
    return true;
  }
  return instances.value.some((instance) => String(instance.instanceId) === String(tabId));
}

function syncDefaultTab() {
  if (selectNewestAfterReload.value) {
    selectNewestAfterReload.value = false;
    const newestId = newestInstanceId();
    if (newestId) {
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
    activeTab.value = "add";
    return;
  }

  if (instances.value.length === 1) {
    if (activeTab.value === "add") {
      return;
    }
    const soleId = String(instances.value[0].instanceId);
    if (activeTab.value !== soleId) {
      activeTab.value = soleId;
      emit("finish-selected", instances.value[0].finish);
    }
    return;
  }

  if (activeTab.value === "add") {
    return;
  }

  if (!tabExists(activeTab.value)) {
    activeTab.value = "summary";
  }
}

function selectTab(tabId) {
  activeTab.value = tabId;
  if (tabId === "add") {
    return;
  }
  if (tabId !== "summary") {
    const instance = instances.value.find(
      (row) => String(row.instanceId) === String(tabId),
    );
    if (instance) {
      emit("finish-selected", instance.finish);
    }
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
  busy.value = true;
  error.value = "";
  selectNewestAfterReload.value = true;
  try {
    await adjustCardCopyCount(
      {
        setCode: props.card.setCode,
        collectorNumber: props.card.collectorNumber,
        finish: addFinish.value,
      },
      1,
      storageLocations.value[0]?.slug,
    );
    clearClientCache();
    emit("ownership-changed");
  } catch (err) {
    selectNewestAfterReload.value = false;
    error.value = err.message || "Could not add owned copy.";
  } finally {
    busy.value = false;
  }
}

watch(
  finishOptions,
  (options) => {
    if (!options.length) {
      return;
    }
    if (!options.some((option) => option.value === addFinish.value)) {
      addFinish.value = options[0].value;
    }
  },
  { immediate: true },
);

watch(
  () => [props.card?.ownedInstances, props.card?.ownershipSummary],
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
        :class="{ active: activeTab === String(instance.instanceId) }"
        :aria-selected="activeTab === String(instance.instanceId)"
        @click="selectTab(String(instance.instanceId))"
        @keydown.enter.prevent="selectTab(String(instance.instanceId))"
      >
        <span class="card-detail-browser-tab-label">{{ instanceTabLabel(instance) }}</span>
        <button
          type="button"
          class="card-detail-browser-tab-delete"
          aria-label="Delete copy"
          title="Delete copy"
          :disabled="busy || loading"
          @click.stop="onRemoveInstance(instance)"
        >
          ×
        </button>
      </div>
      <button
        type="button"
        class="card-detail-browser-tab card-detail-browser-tab-add"
        :class="{ active: activeTab === 'add' }"
        aria-label="Add owned copy"
        title="Add owned copy"
        :disabled="busy || loading || !finishOptions.length"
        @click="selectTab('add')"
      >
        +
      </button>
    </div>

    <div class="card-detail-browser-panel">
      <div v-if="activeTab === 'add'" class="card-detail-instance-fields">
        <p class="card-detail-add-copy-lead">Add a new owned copy of this card.</p>
        <div class="card-detail-pricing-stat">
          <span class="card-detail-pricing-stat-label">Finish</span>
          <span class="card-detail-pricing-stat-value">
            <div class="button-group card-detail-finish-toggle" role="group" aria-label="Finish">
              <button
                v-for="option in finishOptions"
                :key="option.value"
                type="button"
                class="filter-button"
                :class="{ active: addFinish === option.value }"
                :disabled="busy || loading"
                @click="addFinish = option.value"
              >
                {{ option.label }}
              </button>
            </div>
          </span>
        </div>
        <button
          type="button"
          class="btn btn-secondary btn-small"
          :disabled="busy || loading || !finishOptions.length"
          @click="onAddCopy"
        >
          Add copy
        </button>
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

        <div class="card-detail-pricing-stat card-detail-pricing-stat-wide">
          <span class="card-detail-pricing-stat-label">Storage</span>
          <span class="card-detail-pricing-stat-value">
            <StorageLocationSelect
              class="card-detail-storage-picker"
              :model-value="activeInstance.locationSlug"
              :locations="storageLocations"
              :disabled="busy || loading || !storageLocations.length"
              aria-label="Storage location"
              @update:model-value="(slug) => onStorageSelect(activeInstance, slug)"
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
                placeholder="0.00"
                @blur="savePurchasePrice(activeInstance)"
                @keydown.enter="$event.target.blur()"
              />
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
