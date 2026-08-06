<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { api, clearClientCache, ignoreAborted } from "../api";
import { confirmDialog } from "../composables/confirmDialog";

const meta = ref(null);
const catalogMessage = ref("");
const catalogPruning = ref(false);
const syncStatus = ref(null);
const syncMessage = ref("");
const syncRunning = ref(false);
let pollTimer = null;

async function refreshMeta() {
  const next = await ignoreAborted(api.getAppMeta());
  if (!next) {
    return;
  }
  meta.value = next;
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

async function pruneOrphanCatalogs() {
  catalogMessage.value = "";
  const ok = await confirmDialog({
    title: "Prune orphan catalogs",
    message:
      "Remove card catalogs for sets that are no longer tracked? Owned purchase CSVs and deck sets are kept.",
    confirmLabel: "Prune",
    danger: true,
  });
  if (!ok) {
    return;
  }
  catalogPruning.value = true;
  try {
    const result = await api.pruneOrphanCatalogs();
    clearClientCache();
    const count = result.removedSets?.length || 0;
    if (!count) {
      catalogMessage.value = "No orphan catalogs found.";
      return;
    }
    catalogMessage.value = `Removed catalogs for ${count} set(s): ${result.removedSets.join(", ")}.`;
  } catch (error) {
    catalogMessage.value = error.message || "Could not clear orphan catalogs.";
  } finally {
    catalogPruning.value = false;
  }
}

onMounted(async () => {
  await Promise.all([refreshMeta(), refreshSyncStatus()]);
  if (syncStatus.value?.status === "running") {
    startPolling();
  }
});

onUnmounted(stopPolling);
</script>

<template>
  <div class="home-page">
    <section class="home-panel">
      <h2>Sync</h2>
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

    <section class="home-panel">
      <h2>Catalog maintenance</h2>
      <p class="home-intro">
        Removing a set from the browser only unregisters it from tracked sets. Use this to clear leftover
        Scryfall catalogs for sets you no longer track.
      </p>
      <div class="home-sync-panel">
        <div class="home-sync-copy">
          <strong>Clear orphan catalogs</strong>
          <p>Deletes card data for sets that are not tracked or referenced by decks.</p>
          <p v-if="catalogMessage" class="home-sync-message">{{ catalogMessage }}</p>
        </div>
        <button
          type="button"
          class="btn btn-secondary"
          :disabled="catalogPruning"
          @click="pruneOrphanCatalogs"
        >
          {{ catalogPruning ? "Clearing…" : "Clear orphan catalogs" }}
        </button>
      </div>
    </section>
  </div>
</template>
