import { ref } from "vue";

import { api, clearClientCache } from "../api";
import { hasSnapshotForDate, utcTodayDate } from "./storageBreakdownHistory";

export const startupPriceSyncStatus = ref("idle");
export const startupPriceSyncMessage = ref("");

let started = false;
let pollTimer = null;

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

export function shouldStartStartupPriceSync(status) {
  if (status?.status === "running") {
    return "poll";
  }
  if (status?.pricesOutdated) {
    return "start";
  }
  return "skip";
}

async function refreshStatus() {
  const status = await api.getPriceSyncStatus();
  if (status.status === "running") {
    startupPriceSyncStatus.value = "running";
    startupPriceSyncMessage.value = "Updating prices…";
    return status;
  }
  if (status.status === "failed") {
    startupPriceSyncStatus.value = "failed";
    startupPriceSyncMessage.value = status.error || status.message || "Price sync failed.";
    return status;
  }
  if (status.status === "completed") {
    startupPriceSyncStatus.value = "completed";
    startupPriceSyncMessage.value = "";
    return status;
  }
  startupPriceSyncStatus.value = status.status || "idle";
  startupPriceSyncMessage.value = "";
  return status;
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const status = await refreshStatus();
      if (status.status === "running") {
        return;
      }
      stopPolling();
      if (status.status === "completed") {
        clearClientCache();
        await saveDailySnapshotAfterPriceSync();
      }
    } catch {
      stopPolling();
      startupPriceSyncStatus.value = "failed";
      startupPriceSyncMessage.value = "Could not check price sync.";
    }
  }, 2000);
}

async function saveDailySnapshotAfterPriceSync() {
  try {
    await api.saveStorageBreakdownSnapshot();
  } catch {
    // Price sync already succeeded; snapshot retry is available on Stats.
  }
}

async function ensureTodaySnapshotIfMissing() {
  try {
    const payload = await api.listStorageBreakdownSnapshots();
    if (hasSnapshotForDate(payload?.snapshots || [], utcTodayDate())) {
      return;
    }
    await api.saveStorageBreakdownSnapshot();
  } catch {
    // Stats page can save manually if this misses.
  }
}

/**
 * Kick off a Cardmarket price sync once per app load when today's prices
 * are missing. After that sync (or when prices are already current), save
 * today's collection snapshot if it does not exist.
 */
export async function ensureStartupPriceSync() {
  if (started) {
    return;
  }
  started = true;
  try {
    const current = await api.getPriceSyncStatus();
    const action = shouldStartStartupPriceSync(current);
    if (action === "skip") {
      startupPriceSyncStatus.value = "skipped";
      startupPriceSyncMessage.value = "";
      await ensureTodaySnapshotIfMissing();
      return;
    }
    if (action === "start") {
      await api.triggerPriceSync();
    }
    startupPriceSyncStatus.value = "running";
    startupPriceSyncMessage.value = "Updating prices…";
    startPolling();
  } catch (error) {
    const message = String(error?.message || "");
    if (message.toLowerCase().includes("already running")) {
      startupPriceSyncStatus.value = "running";
      startupPriceSyncMessage.value = "Updating prices…";
      startPolling();
      return;
    }
    started = false;
    startupPriceSyncStatus.value = "failed";
    startupPriceSyncMessage.value = message || "Could not start price sync.";
  }
}
