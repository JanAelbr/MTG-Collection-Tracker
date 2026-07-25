<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { api } from "../api";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { cardDisplayName, cardFinish, normalizeFinish } from "../utils/finishes";
import { formatEuro } from "../utils/format";
import { priceStrategyDescription, valueForStrategy } from "../utils/priceStrategies";

const props = defineProps({
  open: { type: Boolean, default: false },
  card: { type: Object, default: null },
  instanceId: { type: [Number, String], default: null },
  listingId: { type: [Number, String], default: null },
  listingPrice: { type: [Number, String], default: null },
});

const emit = defineEmits(["close", "saved"]);

const { settings: pricingSettings } = usePricingSettings();
const busy = ref(false);
const loadingGuide = ref(false);
const error = ref("");
const priceInput = ref("");
const priceInputEl = ref(null);
const selectedStrategyId = ref("");
const guideValues = ref(null);

const isEdit = computed(() => props.listingId != null && props.listingId !== "");
const strategies = computed(() => pricingSettings.value?.priceStrategies || []);
const activeStrategyId = computed(
  () => pricingSettings.value?.priceStrategy || "trend",
);
const finish = computed(() => normalizeFinish(cardFinish(props.card)));
const title = computed(() => (isEdit.value ? "Update asking price" : "List for sale"));
const confirmLabel = computed(() => (isEdit.value ? "Save asking price" : "List for sale"));

const strategyCard = computed(() => {
  if (!props.card) {
    return null;
  }
  if (guideValues.value) {
    return { ...props.card, valuesByStrategy: guideValues.value };
  }
  if (props.card.valuesByStrategy) {
    return props.card;
  }
  return props.card;
});

const strategyRows = computed(() =>
  strategies.value.map((strategy) => ({
    id: strategy.id,
    label: strategy.label,
    description: priceStrategyDescription(strategy.id),
    value: valueForStrategy(strategyCard.value, strategy.id),
    isActive: strategy.id === (selectedStrategyId.value || activeStrategyId.value),
  })),
);

function parsePrice(raw) {
  if (raw === "" || raw == null) {
    return null;
  }
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) {
    return undefined;
  }
  return value;
}

function applyStrategy(strategyId) {
  selectedStrategyId.value = strategyId;
  const value = valueForStrategy(strategyCard.value, strategyId);
  if (value != null) {
    priceInput.value = String(value);
  }
}

function defaultSuggestedPrice() {
  if (props.listingPrice != null && props.listingPrice !== "") {
    return String(props.listingPrice);
  }
  const strategy = activeStrategyId.value;
  const fromGuide = valueForStrategy(strategyCard.value, strategy);
  if (fromGuide != null) {
    return String(fromGuide);
  }
  if (props.card?.currentValue != null) {
    return String(props.card.currentValue);
  }
  return "";
}

async function loadGuidePrices() {
  if (!props.card?.setCode || props.card?.collectorNumber == null) {
    guideValues.value = props.card?.valuesByStrategy || null;
    return;
  }
  loadingGuide.value = true;
  try {
    await fetchPricingSettings();
    const detail = await api.getCardDetail(
      props.card.setCode,
      props.card.collectorNumber,
      { finish: finish.value },
    );
    const finishPayload = detail?.finishes?.[String(finish.value)];
    const fromFinish = finishPayload?.guidePrices;
    if (fromFinish && typeof fromFinish === "object") {
      guideValues.value = { ...fromFinish };
      return;
    }
    const rows = detail?.guidePriceMatrix?.rows || [];
    const key = finish.value === 1 ? "foil" : finish.value === 2 ? "etched" : "nonfoil";
    const mapped = {};
    for (const row of rows) {
      mapped[row.strategyId] = row[key] ?? null;
    }
    guideValues.value = mapped;
  } catch {
    guideValues.value = props.card?.valuesByStrategy || null;
  } finally {
    loadingGuide.value = false;
  }
}

async function onConfirm() {
  const parsed = parsePrice(priceInput.value);
  if (parsed === undefined || parsed == null) {
    error.value = "Asking price must be zero or greater.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    let result;
    if (isEdit.value) {
      result = await api.updateSaleListed(props.listingId, { listingPrice: parsed });
    } else {
      if (props.instanceId == null || props.instanceId === "") {
        throw new Error("Missing copy to list.");
      }
      result = await api.createSaleListing({
        instanceId: Number(props.instanceId),
        listingPrice: parsed,
      });
    }
    emit("saved", result);
    emit("close");
  } catch (err) {
    error.value = err?.message || (isEdit.value
      ? "Could not update asking price."
      : "Could not list copy for sale.");
  } finally {
    busy.value = false;
  }
}

function onClose() {
  if (busy.value) {
    return;
  }
  emit("close");
}

function focusPriceInput() {
  nextTick(() => {
    const el = priceInputEl.value;
    if (!el) {
      return;
    }
    el.focus({ preventScroll: true });
    el.select();
  });
}

watch(
  () => [props.open, props.card?.setCode, props.card?.collectorNumber, props.listingId, props.listingPrice],
  async ([open]) => {
    if (!open) {
      return;
    }
    error.value = "";
    selectedStrategyId.value = activeStrategyId.value;
    await loadGuidePrices();
    priceInput.value = defaultSuggestedPrice();
    if (!isEdit.value && !priceInput.value && activeStrategyId.value) {
      applyStrategy(activeStrategyId.value);
    }
    focusPriceInput();
  },
);
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && card"
      class="sell-dialog-backdrop list-for-sale-modal-backdrop"
    >
      <div
        class="sell-dialog list-for-sale-modal"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
      >
        <h2>{{ title }}</h2>
        <p class="list-for-sale-modal-card">
          {{ cardDisplayName(card) }}
          <span v-if="card.setCode"> · {{ card.setLabel || card.setCode }} #{{ card.collectorNumber }}</span>
        </p>

        <div class="list-for-sale-strategies" role="group" aria-label="Price trends">
          <button
            v-for="row in strategyRows"
            :key="row.id"
            type="button"
            class="list-for-sale-strategy"
            :class="{ active: row.isActive }"
            :disabled="busy || loadingGuide || row.value == null"
            :title="row.description || row.label"
            @click="applyStrategy(row.id)"
          >
            <span class="list-for-sale-strategy-label">{{ row.label }}</span>
            <span class="list-for-sale-strategy-value">
              {{ row.value == null ? "—" : formatEuro(row.value) }}
            </span>
          </button>
        </div>

        <label class="sell-dialog-label">
          Asking price (€)
          <input
            ref="priceInputEl"
            v-model="priceInput"
            class="sell-price-input"
            type="number"
            min="0"
            step="0.01"
            inputmode="decimal"
            :disabled="busy"
            @keydown.enter.prevent="onConfirm"
          >
        </label>

        <p v-if="loadingGuide" class="sell-dialog-hint">Loading price trends…</p>
        <p v-else-if="error" class="list-for-sale-modal-error">{{ error }}</p>
        <p v-else class="sell-dialog-hint">
          Pick a trend to fill the asking price, then adjust if needed.
        </p>

        <div class="sell-dialog-actions">
          <button type="button" class="btn btn-secondary" :disabled="busy" @click="onClose">
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="busy || loadingGuide"
            @click="onConfirm"
          >
            {{ confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
