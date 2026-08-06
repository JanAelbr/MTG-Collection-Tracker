<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import SellListingsTable from "../components/SellListingsTable.vue";
import { confirmDialog } from "../composables/confirmDialog";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { cardMatchesSearchQuery } from "../utils/collectionFilters";
import { formatEuro } from "../utils/format";
import { valueForStrategy } from "../utils/priceStrategies";

const tab = ref("listed");
const loading = ref(true);
const error = ref("");
const listed = ref([]);
const sold = ref([]);
const listedTotals = ref({ totalAsking: 0, totalListings: 0 });
const soldTotals = ref({ totalSales: 0, totalListings: 0 });
const busyId = ref(null);

const sellDialog = ref(null);
const sellPriceInput = ref("");
const sellPriceInputEl = ref(null);

const searchQuery = ref("");
const groupBySet = ref(false);
const expandedSetCodes = ref(new Set());

const { settings: pricingSettings } = usePricingSettings();
const priceStrategies = computed(() => pricingSettings.value?.priceStrategies || []);
const activeStrategyId = computed(() => "trend");

const sortField = ref("name");
const sortDir = ref("asc");

const cards = computed(() => (tab.value === "listed" ? listed.value : sold.value));

function sellCardMatchesSearch(card, query) {
  if (cardMatchesSearchQuery(card, query)) {
    return true;
  }
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) {
    return true;
  }
  return (
    String(card?.setCode || "").toLowerCase().includes(needle)
    || String(card?.setLabel || "").toLowerCase().includes(needle)
    || String(card?.locationLabel || "").toLowerCase().includes(needle)
    || String(card?.locationSlug || "").toLowerCase().includes(needle)
  );
}

const filteredCards = computed(() =>
  cards.value.filter((card) => sellCardMatchesSearch(card, searchQuery.value)),
);

const sortedCards = computed(() => {
  const rows = [...filteredCards.value];
  const field = sortField.value;
  const ascending = sortDir.value === "asc";
  rows.sort((left, right) => {
    const cmp = compareSortValues(sortValue(left, field), sortValue(right, field));
    if (cmp !== 0) {
      return ascending ? cmp : -cmp;
    }
    return String(left.name || "").localeCompare(String(right.name || ""), undefined, {
      sensitivity: "base",
    });
  });
  return rows;
});

const setGroups = computed(() => {
  if (!groupBySet.value) {
    return [];
  }
  const buckets = new Map();
  for (const card of sortedCards.value) {
    const code = String(card?.setCode || "").trim().toUpperCase() || "—";
    if (!buckets.has(code)) {
      buckets.set(code, []);
    }
    buckets.get(code).push(card);
  }
  const groups = [...buckets.entries()].map(([setCode, groupCards]) => {
    let totalAsking = 0;
    let totalSales = 0;
    for (const card of groupCards) {
      totalAsking += Number(card.listingPrice || 0);
      totalSales += Number(card.salePrice || 0);
    }
    const setLabel = groupCards.find((card) => card.setLabel)?.setLabel || setCode;
    const familyRoot = groupCards.find((card) => card.familyRoot)?.familyRoot || setCode;
    return {
      setCode,
      setLabel,
      familyRoot,
      cards: groupCards,
      count: groupCards.length,
      totalAsking,
      totalSales,
    };
  });
  const ascending = sortDir.value === "asc";
  groups.sort((left, right) => {
    const cmp = left.setCode.localeCompare(right.setCode, undefined, { sensitivity: "base" });
    if (sortField.value === "set") {
      return ascending ? cmp : -cmp;
    }
    return cmp;
  });
  return groups;
});

const anySetGroupExpanded = computed(() =>
  setGroups.value.some((group) => expandedSetCodes.value.has(group.setCode)),
);

const hasActiveSearch = computed(() => Boolean(String(searchQuery.value || "").trim()));

const matchSummaryText = computed(() => {
  const shown = filteredCards.value.length;
  const total = cards.value.length;
  if (!total) {
    return "";
  }
  if (!hasActiveSearch.value || shown === total) {
    return `${total} listing${total === 1 ? "" : "s"}`;
  }
  return `${shown} of ${total} listing${total === 1 ? "" : "s"}`;
});

function defaultExpandedSetCodes(groups = setGroups.value) {
  if (groups.length === 1) {
    return new Set([groups[0].setCode]);
  }
  return new Set();
}

function applyDefaultSetGroupExpansion() {
  expandedSetCodes.value = defaultExpandedSetCodes();
}

function toggleSetGroup(setCode) {
  const next = new Set(expandedSetCodes.value);
  if (next.has(setCode)) {
    next.delete(setCode);
  } else {
    next.add(setCode);
  }
  expandedSetCodes.value = next;
}

function expandAllSetGroups() {
  expandedSetCodes.value = new Set(setGroups.value.map((group) => group.setCode));
}

function collapseAllSetGroups() {
  expandedSetCodes.value = new Set();
}

function toggleGroupBySet() {
  groupBySet.value = !groupBySet.value;
  if (groupBySet.value) {
    applyDefaultSetGroupExpansion();
  }
}

function setGroupMetaText(group) {
  if (tab.value === "listed") {
    return `${group.count} · ${formatEuro(group.totalAsking)}`;
  }
  return `${group.count} · ${formatEuro(group.totalSales)}`;
}

function strategyValue(card, strategyId) {
  return valueForStrategy(card, strategyId);
}

function askVsActiveDelta(card) {
  const ask = Number(card?.listingPrice);
  const market = strategyValue(card, activeStrategyId.value);
  if (!Number.isFinite(ask) || market == null || Number.isNaN(Number(market))) {
    return null;
  }
  const delta = ask - Number(market);
  if (delta === 0) {
    return 0;
  }
  return delta;
}

function askVsActiveDirection(card) {
  const delta = askVsActiveDelta(card);
  if (delta == null || delta === 0) {
    return null;
  }
  return delta > 0 ? "up" : "down";
}

function askVsActiveLabel(card) {
  const delta = askVsActiveDelta(card);
  if (delta == null || delta === 0) {
    return null;
  }
  return formatEuro(Math.abs(delta));
}

function askVsActiveTitle(card) {
  const direction = askVsActiveDirection(card);
  if (!direction) {
    return "";
  }
  const ask = Number(card.listingPrice);
  const market = Number(strategyValue(card, activeStrategyId.value));
  const delta = Math.abs(ask - market);
  const strategy = priceStrategies.value.find((row) => row.id === activeStrategyId.value);
  const label = strategy?.label || activeStrategyId.value;
  if (direction === "up") {
    return `Ask ${formatEuro(ask)} is ${formatEuro(delta)} above ${label} (${formatEuro(market)})`;
  }
  return `Ask ${formatEuro(ask)} is ${formatEuro(delta)} below ${label} (${formatEuro(market)})`;
}

function sortValue(card, field) {
  if (field.startsWith("strategy:")) {
    return strategyValue(card, field.slice("strategy:".length));
  }
  switch (field) {
    case "name":
      return card.name || "";
    case "set":
      return `${String(card.setCode || "").toUpperCase()}|${String(card.collectorNumber || "")}`;
    case "finish":
      return Number(card.finish ?? 0);
    case "listingPrice":
      return card.listingPrice;
    case "askDelta":
      return askVsActiveDelta(card);
    case "salePrice":
      return card.salePrice;
    case "location":
      return card.locationLabel || card.locationSlug || "";
    default:
      return card[field] ?? "";
  }
}

function compareSortValues(left, right) {
  const leftEmpty = left == null || left === "" || Number.isNaN(left);
  const rightEmpty = right == null || right === "" || Number.isNaN(right);
  if (leftEmpty && rightEmpty) {
    return 0;
  }
  if (leftEmpty) {
    return 1;
  }
  if (rightEmpty) {
    return -1;
  }
  if (typeof left === "number" && typeof right === "number") {
    return left - right;
  }
  return String(left).localeCompare(String(right), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function defaultSortDir(field) {
  if (
    field === "listingPrice"
    || field === "askDelta"
    || field === "salePrice"
    || field.startsWith("strategy:")
  ) {
    return "desc";
  }
  return "asc";
}

function toggleSort(field) {
  if (!field) {
    return;
  }
  if (sortField.value === field) {
    sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
    return;
  }
  sortField.value = field;
  sortDir.value = defaultSortDir(field);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [listedPayload, soldPayload] = await Promise.all([
      api.getSalesListed(),
      api.getSalesSold(),
      fetchPricingSettings(),
    ]);
    listed.value = listedPayload.cards || [];
    listedTotals.value = {
      totalAsking: listedPayload.totalAsking || 0,
      totalListings: listedPayload.totalListings || 0,
    };
    sold.value = soldPayload.cards || [];
    soldTotals.value = {
      totalSales: soldPayload.totalSales || 0,
      totalListings: soldPayload.totalListings || 0,
    };
  } catch (err) {
    error.value = err?.message || "Failed to load sales";
  } finally {
    loading.value = false;
  }
}

async function saveListedPrice(card, event) {
  const raw = event?.target?.value;
  const next = Number(raw);
  if (!Number.isFinite(next) || next < 0 || next === card.listingPrice) {
    if (event?.target) {
      event.target.value = String(card.listingPrice ?? "");
    }
    return;
  }
  busyId.value = card.listingId;
  try {
    const updated = await api.updateSaleListed(card.listingId, { listingPrice: next });
    listed.value = listed.value.map((item) => (
      item.listingId === updated.listingId
        ? { ...item, ...updated, valuesByStrategy: updated.valuesByStrategy || item.valuesByStrategy }
        : item
    ));
    listedTotals.value.totalAsking = listed.value.reduce(
      (sum, item) => sum + Number(item.listingPrice || 0),
      0,
    );
  } catch (err) {
    error.value = err?.message || "Failed to update asking price";
    if (event?.target) {
      event.target.value = String(card.listingPrice ?? "");
    }
  } finally {
    busyId.value = null;
  }
}

async function saveSoldPrice(card, event) {
  const raw = event?.target?.value;
  const next = Number(raw);
  if (!Number.isFinite(next) || next < 0 || next === card.salePrice) {
    if (event?.target) {
      event.target.value = String(card.salePrice ?? "");
    }
    return;
  }
  busyId.value = card.listingId;
  try {
    const updated = await api.updateSaleSold(card.listingId, { salePrice: next });
    sold.value = sold.value.map((item) => (
      item.listingId === updated.listingId ? updated : item
    ));
    soldTotals.value.totalSales = sold.value.reduce(
      (sum, item) => sum + Number(item.salePrice || 0),
      0,
    );
  } catch (err) {
    error.value = err?.message || "Failed to update sale price";
    if (event?.target) {
      event.target.value = String(card.salePrice ?? "");
    }
  } finally {
    busyId.value = null;
  }
}

async function onUnlist(card) {
  const ok = await confirmDialog({
    title: "Unlist card",
    message: `Unlist ${card.name}? The copy stays in your collection.`,
    confirmLabel: "Unlist",
    danger: true,
  });
  if (!ok) {
    return;
  }
  busyId.value = card.listingId;
  try {
    await api.unlistSaleListing(card.listingId);
    listed.value = listed.value.filter((item) => item.listingId !== card.listingId);
    listedTotals.value.totalListings = listed.value.length;
    listedTotals.value.totalAsking = listed.value.reduce(
      (sum, item) => sum + Number(item.listingPrice || 0),
      0,
    );
  } catch (err) {
    error.value = err?.message || "Failed to unlist";
  } finally {
    busyId.value = null;
  }
}

function openSellDialog(card) {
  sellDialog.value = card;
  sellPriceInput.value = String(card.listingPrice ?? "");
  nextTick(() => {
    const el = sellPriceInputEl.value;
    if (!el) {
      return;
    }
    el.focus({ preventScroll: true });
    el.select();
  });
}

function closeSellDialog() {
  sellDialog.value = null;
  sellPriceInput.value = "";
}

async function confirmSell() {
  const card = sellDialog.value;
  if (!card) {
    return;
  }
  const salePrice = Number(sellPriceInput.value);
  if (!Number.isFinite(salePrice) || salePrice < 0) {
    error.value = "Sale price must be zero or greater";
    return;
  }
  busyId.value = card.listingId;
  try {
    const updated = await api.sellSaleListing(card.listingId, { salePrice });
    listed.value = listed.value.filter((item) => item.listingId !== card.listingId);
    listedTotals.value.totalListings = listed.value.length;
    listedTotals.value.totalAsking = listed.value.reduce(
      (sum, item) => sum + Number(item.listingPrice || 0),
      0,
    );
    sold.value = [updated, ...sold.value];
    soldTotals.value.totalListings = sold.value.length;
    soldTotals.value.totalSales = sold.value.reduce(
      (sum, item) => sum + Number(item.salePrice || 0),
      0,
    );
    closeSellDialog();
    tab.value = "sold";
  } catch (err) {
    error.value = err?.message || "Failed to mark sold";
  } finally {
    busyId.value = null;
  }
}

async function onDeleteSold(card) {
  const ok = await confirmDialog({
    title: "Remove sold listing",
    message: `Remove ${card.name} from the sold archive?`,
    confirmLabel: "Remove",
    danger: true,
  });
  if (!ok) {
    return;
  }
  busyId.value = card.listingId;
  try {
    await api.deleteSaleSold(card.listingId);
    sold.value = sold.value.filter((item) => item.listingId !== card.listingId);
    soldTotals.value.totalListings = sold.value.length;
    soldTotals.value.totalSales = sold.value.reduce(
      (sum, item) => sum + Number(item.salePrice || 0),
      0,
    );
  } catch (err) {
    error.value = err?.message || "Failed to delete sold row";
  } finally {
    busyId.value = null;
  }
}

watch(tab, () => {
  error.value = "";
  if (tab.value === "listed" && ["salePrice", "purchaseValue", "profitLoss"].includes(sortField.value)) {
    sortField.value = "listingPrice";
    sortDir.value = "desc";
  } else if (
    tab.value === "sold"
    && (sortField.value === "listingPrice"
      || sortField.value === "askDelta"
      || sortField.value === "purchaseValue"
      || sortField.value === "profitLoss"
      || sortField.value.startsWith("strategy:"))
  ) {
    sortField.value = "salePrice";
    sortDir.value = "desc";
  }
  if (groupBySet.value) {
    applyDefaultSetGroupExpansion();
  }
});

watch(
  () => setGroups.value.map((group) => group.setCode).join("|"),
  (next, prev) => {
    if (!groupBySet.value || next === prev) {
      return;
    }
    applyDefaultSetGroupExpansion();
  },
);

onMounted(load);
</script>

<template>
  <div class="reports-page collection-page sell-page">
    <header class="sell-page-header">
      <div>
        <h1>Sell</h1>
        <p class="sell-page-subtitle">
          List owned copies for sale, then archive them when they sell.
        </p>
      </div>
      <div class="sell-page-tabs" role="tablist">
        <button
          type="button"
          class="btn"
          :class="tab === 'listed' ? 'btn-primary' : 'btn-secondary'"
          role="tab"
          :aria-selected="tab === 'listed'"
          @click="tab = 'listed'"
        >
          For sale ({{ listedTotals.totalListings }})
        </button>
        <button
          type="button"
          class="btn"
          :class="tab === 'sold' ? 'btn-primary' : 'btn-secondary'"
          role="tab"
          :aria-selected="tab === 'sold'"
          @click="tab = 'sold'"
        >
          Sold ({{ soldTotals.totalListings }})
        </button>
      </div>
    </header>

    <p v-if="tab === 'listed'" class="sell-page-stats">
      Asking total: <strong>{{ formatEuro(listedTotals.totalAsking) }}</strong>
    </p>
    <p v-else class="sell-page-stats">
      Sales total: <strong>{{ formatEuro(soldTotals.totalSales) }}</strong>
    </p>

    <div v-if="!loading && cards.length" class="sell-page-toolbar">
      <label class="sell-toolbar-search">
        <span class="visually-hidden">Search listings</span>
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Search name, #, set…"
          autocomplete="off"
        >
      </label>
      <p v-if="matchSummaryText" class="sell-toolbar-summary">{{ matchSummaryText }}</p>
      <div class="sell-toolbar-end">
        <button
          type="button"
          class="filter-button"
          :class="{ active: groupBySet }"
          :aria-pressed="groupBySet"
          @click="toggleGroupBySet"
        >
          Group by set
        </button>
        <button
          v-if="groupBySet && setGroups.length"
          type="button"
          class="btn btn-secondary btn-small"
          @click="anySetGroupExpanded ? collapseAllSetGroups() : expandAllSetGroups()"
        >
          {{ anySetGroupExpanded ? "Collapse all" : "Expand all" }}
        </button>
      </div>
    </div>

    <p v-if="error" class="sell-page-error">{{ error }}</p>
    <LoadingIndicator v-if="loading" label="Loading sales…" />

    <div v-else-if="!cards.length" class="sell-page-empty table-panel">
      <p v-if="tab === 'listed'">
        Nothing listed yet. List a copy from Storage or a card’s copy controls.
      </p>
      <p v-else>No sold archive entries yet.</p>
      <RouterLink v-if="tab === 'listed'" class="btn btn-secondary" to="/storage">
        Open storage
      </RouterLink>
    </div>

    <div v-else-if="!sortedCards.length" class="sell-page-empty table-panel">
      <p>No listings match “{{ searchQuery.trim() }}”.</p>
    </div>

    <div v-else class="table-panel sell-table-wrap" :class="{ 'is-grouped': groupBySet }">
      <SellListingsTable
        :tab="tab"
        :cards="sortedCards"
        :groups="setGroups"
        :group-by-set="groupBySet"
        :expanded-set-codes="expandedSetCodes"
        :price-strategies="priceStrategies"
        :active-strategy-id="activeStrategyId"
        :busy-id="busyId"
        :sort-field="sortField"
        :sort-dir="sortDir"
        :strategy-value="strategyValue"
        :ask-vs-active-direction="askVsActiveDirection"
        :ask-vs-active-label="askVsActiveLabel"
        :ask-vs-active-title="askVsActiveTitle"
        :set-group-meta-text="setGroupMetaText"
        @toggle-sort="toggleSort"
        @toggle-set-group="toggleSetGroup"
        @save-listed-price="saveListedPrice"
        @save-sold-price="saveSoldPrice"
        @open-sell="openSellDialog"
        @unlist="onUnlist"
        @delete-sold="onDeleteSold"
      />
    </div>

    <Teleport to="body">
      <div v-if="sellDialog" class="sell-dialog-backdrop">
        <div class="sell-dialog" role="dialog" aria-modal="true" aria-label="Mark sold">
          <h2>Mark sold</h2>
          <p>{{ sellDialog.name }} · {{ sellDialog.setLabel || sellDialog.setCode }} #{{ sellDialog.collectorNumber }}</p>
          <label class="sell-dialog-label">
            Sale price (€)
            <input
              ref="sellPriceInputEl"
              v-model="sellPriceInput"
              class="sell-price-input"
              type="number"
              min="0"
              step="0.01"
            >
          </label>
          <p class="sell-dialog-hint">
            This removes the owned copy from your collection and adds it to the sold archive.
          </p>
          <div class="sell-dialog-actions">
            <button type="button" class="btn btn-secondary" @click="closeSellDialog">Cancel</button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="busyId === sellDialog.listingId"
              @click="confirmSell"
            >
              Confirm sale
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
