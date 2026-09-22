import { ref } from "vue";

import { api, clearClientCache } from "../api";
import { hasSnapshotForDate, utcTodayDate } from "./storageBreakdownHistory";

export const startupPriceSyncStatus = ref("idle");
export const startupPriceSyncMessage = ref("");
export const lastPriceSyncOutcome = ref(null);

let openChangesOnHome = null;

export function bindHomeChangesNavigation(handler) {
  openChangesOnHome = handler;
  return () => {
    if (openChangesOnHome === handler) {
      openChangesOnHome = null;
    }
  };
}

let started = false;
let pollTimer = null;

export function emptyPriceSyncMovers() {
  return {
    absolute: { risers: [], fallers: [] },
    relative: { risers: [], fallers: [] },
  };
}

export function normalizePriceSyncMovers(raw) {
  if (!raw || typeof raw !== "object") {
    return emptyPriceSyncMovers();
  }
  if (raw.absolute || raw.relative) {
    return {
      absolute: {
        risers: raw.absolute?.risers || [],
        fallers: raw.absolute?.fallers || [],
      },
      relative: {
        risers: raw.relative?.risers || [],
        fallers: raw.relative?.fallers || [],
      },
    };
  }
  const pair = { risers: raw.risers || [], fallers: raw.fallers || [] };
  return { absolute: pair, relative: pair };
}

export function priceSyncHasMovers(status) {
  if ((status?.cards || []).length) {
    return true;
  }
  const movers = normalizePriceSyncMovers(status?.movers);
  return Boolean(
    movers.absolute.risers.length
    || movers.absolute.fallers.length
    || movers.relative.risers.length
    || movers.relative.fallers.length
  );
}

export function recordCompletedPriceSync(status) {
  if (!status || status.status !== "completed") {
    return;
  }
  const movers = normalizePriceSyncMovers(status.movers || status.lastSync?.movers);
  const cards = status.cards || status.lastSync?.cards || [];
  lastPriceSyncOutcome.value = {
    pricesUnchanged: Boolean(status.pricesUnchanged),
    message: status.message || (
      status.pricesUnchanged
        ? "Prices unchanged since last sync."
        : "Price sync completed."
    ),
    movers,
    cards,
    syncedAt: status.finishedAt || status.lastSync?.syncedAt || "",
  };
  if (!lastPriceSyncOutcome.value.pricesUnchanged && priceSyncHasMovers(lastPriceSyncOutcome.value)) {
    openChangesOnHome?.();
  }
}

export function showStoredPriceSyncMovers(status) {
  const stored = status?.lastSync || status;
  if (!stored) {
    return;
  }
  lastPriceSyncOutcome.value = {
    pricesUnchanged: false,
    message: stored.message || "Last price sync",
    movers: normalizePriceSyncMovers(stored.movers),
    cards: stored.cards || status?.cards || [],
    syncedAt: stored.syncedAt || "",
  };
}

export function formatPriceSyncRunningMessage(status, fallback = "Updating prices…") {
  const percent = Number.isFinite(Number(status?.progress))
    ? Math.max(0, Math.min(100, Math.round(Number(status.progress))))
    : null;
  const processed = Number(status?.processed) || 0;
  const total = Number(status?.total) || 0;
  let suffix = "";
  if (percent != null) {
    suffix = ` (${percent}%`;
    if (total > 0) {
      suffix += ` · ${processed}/${total}`;
    }
    suffix += ")";
  }
  const detail = String(status?.message || "").trim();
  const base = detail && !/^price sync (started|completed)$/i.test(detail)
    ? detail
    : fallback;
  return `${base}${suffix}`;
}

export const PRICE_SYNC_POLL_MS = 1000;

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
    startupPriceSyncMessage.value = formatPriceSyncRunningMessage(status);
    return status;
  }
  if (status.status === "failed") {
    startupPriceSyncStatus.value = "failed";
    startupPriceSyncMessage.value = status.error || status.message || "Price sync failed.";
    return status;
  }
  if (status.status === "completed") {
    startupPriceSyncStatus.value = "completed";
    recordCompletedPriceSync(status);
    startupPriceSyncMessage.value = lastPriceSyncOutcome.value?.message || status.message || "";
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
      }
    } catch {
      stopPolling();
      startupPriceSyncStatus.value = "failed";
      startupPriceSyncMessage.value = "Could not check price sync.";
    }
  }, PRICE_SYNC_POLL_MS);
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
