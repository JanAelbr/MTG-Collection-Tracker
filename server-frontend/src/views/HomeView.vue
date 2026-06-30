<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { api, clearClientCache, ignoreAborted } from "../api";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";

const meta = ref(null);
const { settings: pricingSettings } = usePricingSettings();
const storageLocations = ref([]);
const settingsMessage = ref("");
const syncStatus = ref(null);
const syncMessage = ref("");
const syncRunning = ref(false);
let pollTimer = null;

const sections = [
  {
    to: "/collection/all",
    title: "Collection",
    description: "Top owned cards and full collection browser with live Cardmarket pricing.",
  },
  {
    to: "/stats",
    title: "Collection stats",
    description: "Portfolio value, ROI, and breakdown by set or art style.",
  },
  {
    to: "/storage",
    title: "Storage",
    description: "Browse binders, decks, and custom storage. Move or remove copies.",
  },
  {
    to: "/manager",
    title: "Set Manager",
    description: "Mark owned finishes, bulk-assign storage, and manage set CSVs.",
  },
  {
    to: "/decks",
    title: "Decks",
    description: "Deck value, ownership, ROI, and card browse with filters.",
  },
];

async function refreshMeta() {
  const next = await ignoreAborted(api.getAppMeta());
  if (!next) {
    return;
  }
  meta.value = next;
}

async function loadPricingSettings() {
  await fetchPricingSettings(true);
}

async function loadStorageLocations() {
  const payload = await api.listStorageLocations();
  storageLocations.value = payload.locations || [];
}

async function updatePriceStrategy(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ priceStrategy: event.target.value });
    settingsMessage.value = "Pricing settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save pricing settings.";
  }
}

async function updateCompareDate(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ compareDate: event.target.value || null });
    settingsMessage.value = "Pricing settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save pricing settings.";
  }
}

async function updatePageSize(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ pageSize: Number(event.target.value) });
    settingsMessage.value = "Display settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save display settings.";
  }
}

function setSortModeLabel(mode) {
  if (mode === "owned") {
    return "Most owned";
  }
  return "Alphabetical";
}

async function updateSetSortMode(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ setSortMode: event.target.value });
    settingsMessage.value = "Display settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save display settings.";
  }
}

function setPickerModeLabel(mode) {
  if (mode === "browser") {
    return "Set browser";
  }
  return "Dropdown";
}

async function updateSetPickerMode(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ setPickerMode: event.target.value });
    settingsMessage.value = "Display settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save display settings.";
  }
}

async function updateDefaultStorageLocation(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ defaultStorageLocation: event.target.value });
    settingsMessage.value = "Display settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save display settings.";
  }
}

async function refreshSyncStatus() {
  const status = await ignoreAborted(api.getPriceSyncStatus());
  if (!status) {
    return;
  }
  syncStatus.value = status;
  syncRunning.value = syncStatus.value.status === "running";
  if (syncStatus.value.lastPriceUpdate) {
    meta.value = {
      ...(meta.value || {}),
      lastPriceUpdate: syncStatus.value.lastPriceUpdate,
    };
  }
  if (syncStatus.value.status === "completed") {
    syncMessage.value = syncStatus.value.message || "Price sync completed.";
  } else if (syncStatus.value.status === "failed") {
    syncMessage.value = syncStatus.value.error || syncStatus.value.message || "Price sync failed.";
  } else if (syncStatus.value.status === "running") {
    syncMessage.value = "Updating Cardmarket prices and catalog data…";
  } else {
    syncMessage.value = "";
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    await refreshSyncStatus();
    if (syncStatus.value?.status !== "running") {
      stopPolling();
      if (syncStatus.value?.status === "completed") {
        clearClientCache();
      }
      await refreshMeta();
    }
  }, 2000);
}

async function triggerPriceSync() {
  syncMessage.value = "Starting price sync…";
  try {
    await api.triggerPriceSync();
    syncRunning.value = true;
    await refreshSyncStatus();
    startPolling();
  } catch (error) {
    syncMessage.value = error.message || "Could not start price sync.";
    syncRunning.value = false;
  }
}

onMounted(async () => {
  await Promise.all([refreshMeta(), loadPricingSettings(), loadStorageLocations(), refreshSyncStatus()]);
  if (syncStatus.value?.status === "running") {
    startPolling();
  }
});

onUnmounted(stopPolling);
</script>

<template>
  <div class="home-page">
    <section class="home-panel">
      <h2>Settings</h2>
      <p v-if="meta?.lastPriceUpdate" class="home-meta">
        Last price snapshot: <strong>{{ meta.lastPriceUpdate }}</strong>
      </p>
      <p class="home-intro">
        Sync Cardmarket prices and refresh the Scryfall catalog for your tracked sets.
        Price data powers the collection views, stats, and deck valuations.
      </p>

      <div class="home-sync-panel">
        <div class="home-sync-copy">
          <strong>Price sync</strong>
          <p>Fetch Cardmarket prices and refresh the Scryfall catalog for your tracked sets.</p>
          <p v-if="syncMessage" class="home-sync-message" :class="{ error: syncStatus?.status === 'failed' }">
            {{ syncMessage }}
          </p>
        </div>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="syncRunning"
          @click="triggerPriceSync"
        >
          {{ syncRunning ? "Syncing prices…" : "Sync prices now" }}
        </button>
      </div>
    </section>

    <section v-if="pricingSettings" class="home-panel">
      <h2>Pricing &amp; display</h2>
      <p class="home-intro">
        Price strategy and compare date apply across Collection, Stats, Storage, Decks, and card detail pages.
        Rows per page applies to Collection and Set Manager lists.
      </p>
      <div class="home-pricing-panel">
        <label class="manager-filter">
          <span>Price strategy</span>
          <select :value="pricingSettings.priceStrategy" @change="updatePriceStrategy">
            <option
              v-for="strategy in pricingSettings.priceStrategies"
              :key="strategy.id"
              :value="strategy.id"
            >
              {{ strategy.label }}
            </option>
          </select>
        </label>
        <label v-if="pricingSettings.compareDates?.length" class="manager-filter">
          <span>Compare date</span>
          <select :value="pricingSettings.compareDate || ''" @change="updateCompareDate">
            <option
              v-for="date in pricingSettings.compareDates"
              :key="date"
              :value="date"
            >
              {{ date }}
            </option>
          </select>
        </label>
        <label class="manager-filter">
          <span>Rows per page</span>
          <select :value="pricingSettings.pageSize" @change="updatePageSize">
            <option
              v-for="size in pricingSettings.pageSizeOptions"
              :key="size"
              :value="size"
            >
              {{ size }}
            </option>
          </select>
        </label>
        <label class="manager-filter">
          <span>Set picker</span>
          <select
            :value="pricingSettings.setPickerMode ?? 'dropdown'"
            @change="updateSetPickerMode"
          >
            <option
              v-for="mode in (pricingSettings.setPickerModeOptions ?? ['dropdown', 'browser'])"
              :key="mode"
              :value="mode"
            >
              {{ setPickerModeLabel(mode) }}
            </option>
          </select>
        </label>
        <label class="manager-filter">
          <span>Set dropdown order</span>
          <select
            :value="pricingSettings.setSortMode ?? 'alphabetical'"
            @change="updateSetSortMode"
          >
            <option
              v-for="mode in (pricingSettings.setSortModeOptions ?? ['alphabetical', 'owned'])"
              :key="mode"
              :value="mode"
            >
              {{ setSortModeLabel(mode) }}
            </option>
          </select>
        </label>
        <label v-if="storageLocations.length" class="manager-filter">
          <span>Default storage</span>
          <select
            :value="pricingSettings.defaultStorageLocation ?? 'storage:general'"
            @change="updateDefaultStorageLocation"
          >
            <option
              v-for="location in storageLocations"
              :key="location.slug"
              :value="location.slug"
            >
              {{ location.label }}
            </option>
          </select>
        </label>
      </div>
      <p v-if="settingsMessage" class="home-sync-message">{{ settingsMessage }}</p>
    </section>

    <section class="home-panel">
      <h2>Quick links</h2>
      <div class="home-links">
        <RouterLink v-for="item in sections" :key="item.to" :to="item.to" class="home-link-card">
          <strong>{{ item.title }}</strong>
          <span>{{ item.description }}</span>
        </RouterLink>
      </div>
    </section>

    <section v-if="meta?.legacyReportsAvailable" class="home-panel home-panel-muted">
      <h2>Legacy index</h2>
      <p>
        A static HTML index is still available for bookmark compatibility.
        Regenerate it with
        <code>python scripts/update_prices_report.py --static-reports</code>.
      </p>
      <a :href="meta.legacyReportsPath" class="btn btn-secondary" target="_blank" rel="noopener">
        Open legacy index
      </a>
    </section>
  </div>
</template>
