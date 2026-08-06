<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { api, clearClientCache, ignoreAborted } from "../api";
import { fetchPricingSettings } from "../composables/pricingSettings";

const meta = ref(null);
const syncStatus = ref(null);
const syncMessage = ref("");
const syncRunning = ref(false);
const backupExporting = ref(false);
const backupImporting = ref(false);
const backupFile = ref(null);
const backupPreview = ref(null);
const backupMode = ref("replace");
const backupConfirmReplace = ref(false);
const backupMessage = ref("");
const backupError = ref("");
const importComplete = ref(null);
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

async function syncCatalogsAndPrices() {
  const sets = importComplete.value?.setsNeedingCatalog || [];
  backupError.value = "";
  try {
    if (sets.length) {
      syncMessage.value = `Importing Scryfall catalogs for ${sets.length} set${sets.length === 1 ? "" : "s"}…`;
      const catalogResult = await api.syncBackupCatalogs(sets);
      if (catalogResult.errors?.length) {
        const failed = catalogResult.errors.map((item) => item.setCode).join(", ");
        backupError.value = `Catalog sync failed for: ${failed}.`;
      }
      syncMessage.value = catalogResult.message || "Catalog sync finished.";
      clearClientCache();
    }
    await triggerPriceSync();
  } catch (error) {
    syncMessage.value = error.message || "Could not sync catalogs and prices.";
  }
}

async function exportCollectionBackup() {
  backupError.value = "";
  backupMessage.value = "";
  backupExporting.value = true;
  try {
    await api.exportCollectionBackup();
    backupMessage.value = "Collection backup downloaded.";
  } catch (error) {
    backupError.value = error.message || "Could not export collection backup.";
  } finally {
    backupExporting.value = false;
  }
}

async function onBackupFileSelected(event) {
  const file = event.target.files?.[0];
  backupFile.value = file || null;
  backupPreview.value = null;
  backupError.value = "";
  backupMessage.value = "";
  importComplete.value = null;
  backupConfirmReplace.value = false;
  if (!file) {
    return;
  }
  try {
    backupPreview.value = await api.previewCollectionBackup(file);
  } catch (error) {
    backupError.value = error.message || "Could not read backup file.";
    backupFile.value = null;
    event.target.value = "";
  }
}

const canImportBackup = computed(() =>
  Boolean(
    backupFile.value
    && backupPreview.value
    && (backupMode.value === "merge" || backupConfirmReplace.value),
  ),
);

async function importCollectionBackup() {
  if (!backupFile.value || !canImportBackup.value) {
    return;
  }
  backupImporting.value = true;
  backupError.value = "";
  backupMessage.value = "";
  try {
    const result = await api.importCollectionBackup(backupFile.value, backupMode.value);
    importComplete.value = result;
    backupMessage.value = result.message || "Collection restored.";
    backupPreview.value = null;
    backupFile.value = null;
    backupConfirmReplace.value = false;
    await Promise.all([refreshMeta(), fetchPricingSettings(true)]);
  } catch (error) {
    backupError.value = error.message || "Could not import collection backup.";
  } finally {
    backupImporting.value = false;
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
      <h2>Backup &amp; restore</h2>
      <p class="home-intro">
        Export owned cards, decks, storage assignments, and display settings.
        Card catalog rows and prices are not included — sync those after restoring on a new machine.
        <strong>Before upgrading the app</strong>, export a backup here so you can restore if anything goes wrong.
      </p>

      <div class="home-sync-panel">
        <div class="home-sync-copy">
          <strong>Export collection</strong>
          <p>Downloads a <code>.mtgbackup.zip</code> file you can restore later.</p>
        </div>
        <button
          type="button"
          class="btn btn-secondary"
          :disabled="backupExporting"
          @click="exportCollectionBackup"
        >
          {{ backupExporting ? "Exporting…" : "Export collection" }}
        </button>
      </div>

      <div class="home-backup-import">
        <strong>Restore from backup</strong>
        <label class="home-backup-file">
          <span>Backup file</span>
          <input type="file" accept=".zip,.mtgbackup.zip" @change="onBackupFileSelected" />
        </label>

        <div v-if="backupPreview" class="home-backup-preview">
          <p v-if="backupPreview.exportedAt">
            Exported <strong>{{ backupPreview.exportedAt }}</strong>
          </p>
          <ul>
            <li>{{ backupPreview.summary.purchases }} owned print{{ backupPreview.summary.purchases === 1 ? "" : "s" }}</li>
            <li>{{ backupPreview.summary.decks }} deck{{ backupPreview.summary.decks === 1 ? "" : "s" }} ({{ backupPreview.summary.deckCards }} slots)</li>
            <li>{{ backupPreview.summary.cardInstances }} stored cop{{ backupPreview.summary.cardInstances === 1 ? "y" : "ies" }}</li>
            <li>{{ backupPreview.summary.storageLocations }} storage location{{ backupPreview.summary.storageLocations === 1 ? "" : "s" }}</li>
            <li v-if="backupPreview.summary.artStyleSets">
              Art styles for {{ backupPreview.summary.artStyleSets }} set{{ backupPreview.summary.artStyleSets === 1 ? "" : "s" }}
            </li>
            <li v-if="backupPreview.summary.setsReferenced?.length">
              Sets referenced: {{ backupPreview.summary.setsReferenced.join(", ") }}
            </li>
          </ul>
        </div>

        <div class="home-backup-mode">
          <span class="home-backup-mode-label">Import mode</span>
          <div class="home-backup-mode-options">
            <label
              class="home-backup-mode-option"
              :class="{ 'is-selected': backupMode === 'replace' }"
            >
              <input v-model="backupMode" type="radio" value="replace" />
              <span class="home-backup-mode-option-body">
                <strong>Replace</strong>
                <span>Overwrite purchases, decks, storage, art styles, and settings from the backup</span>
              </span>
            </label>
            <label
              class="home-backup-mode-option"
              :class="{ 'is-selected': backupMode === 'merge' }"
            >
              <input v-model="backupMode" type="radio" value="merge" />
              <span class="home-backup-mode-option-body">
                <strong>Merge</strong>
                <span>Combine backup data with what is already here — skips anything that already matches</span>
              </span>
            </label>
          </div>
        </div>

        <label v-if="backupMode === 'replace'" class="home-backup-confirm">
          <input v-model="backupConfirmReplace" type="checkbox" />
          <span>I understand this will replace my current collection data</span>
        </label>

        <button
          type="button"
          class="btn btn-primary"
          :disabled="!canImportBackup || backupImporting"
          @click="importCollectionBackup"
        >
          {{ backupImporting ? "Restoring…" : "Restore collection" }}
        </button>
      </div>

      <div v-if="importComplete" class="home-backup-next-steps">
        <strong>Restore complete</strong>
        <p>{{ importComplete.message }}</p>
        <p v-if="importComplete.setsNeedingCatalog?.length">
          Catalog sync will fetch Scryfall data for:
          {{ importComplete.setsNeedingCatalog.join(", ") }}.
        </p>
        <p v-if="syncMessage" class="home-sync-message" :class="{ error: syncStatus?.status === 'failed' }">
          {{ syncMessage }}
        </p>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="syncRunning"
          @click="syncCatalogsAndPrices"
        >
          {{ syncRunning ? "Syncing…" : "Sync catalog & prices now" }}
        </button>
      </div>

      <p v-if="backupMessage" class="home-sync-message">{{ backupMessage }}</p>
      <p v-if="backupError" class="home-sync-message error">{{ backupError }}</p>
    </section>
  </div>
</template>
