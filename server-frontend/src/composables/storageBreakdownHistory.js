import { computed, ref } from "vue";

import { api } from "../api";
import { confirmDialog } from "./confirmDialog";
import { formatEuro } from "../utils/format";

export const snapshotList = ref([]);
export const selectedSnapshotId = ref(null);
export const selectedSnapshot = ref(null);
export const compareToCurrent = ref(true);
export const savingSnapshot = ref(false);
export const snapshotError = ref("");

export function snapshotOptionLabel(snapshot) {
  const date = snapshot?.snapshotDate || "Unknown date";
  const value = formatEuro(snapshot?.totals?.current);
  const note = String(snapshot?.note || "").trim();
  return note ? `${date} · ${value} · ${note}` : `${date} · ${value}`;
}

export async function loadSnapshots() {
  snapshotError.value = "";
  try {
    const payload = await api.listStorageBreakdownSnapshots();
    snapshotList.value = payload.snapshots || [];
  } catch (error) {
    snapshotError.value = error.message || "Could not load snapshots.";
  }
}

export async function loadSelectedSnapshot(snapshotId) {
  if (!snapshotId) {
    selectedSnapshot.value = null;
    return;
  }
  try {
    selectedSnapshot.value = await api.getStorageBreakdownSnapshot(snapshotId);
  } catch (error) {
    snapshotError.value = error.message || "Could not load snapshot.";
    selectedSnapshot.value = null;
    selectedSnapshotId.value = null;
  }
}

export async function applySnapshotSelection(rawId) {
  const text = String(rawId ?? "").trim();
  if (!text) {
    selectedSnapshotId.value = null;
    selectedSnapshot.value = null;
    return false;
  }
  const snapshotId = Number(text);
  selectedSnapshotId.value = snapshotId;
  compareToCurrent.value = true;
  await loadSelectedSnapshot(snapshotId);
  return Boolean(selectedSnapshot.value);
}

export async function saveDailySnapshot({ select = false } = {}) {
  if (savingSnapshot.value) {
    return null;
  }
  savingSnapshot.value = true;
  snapshotError.value = "";
  try {
    const saved = await api.saveStorageBreakdownSnapshot();
    await loadSnapshots();
    if (select) {
      selectedSnapshotId.value = saved.id;
      compareToCurrent.value = true;
      await loadSelectedSnapshot(saved.id);
    }
    return saved;
  } catch (error) {
    snapshotError.value = error.message || "Could not save breakdown.";
    return null;
  } finally {
    savingSnapshot.value = false;
  }
}

export async function deleteSnapshot(snapshot) {
  if (!snapshot?.id) {
    return false;
  }
  const ok = await confirmDialog({
    title: "Delete snapshot",
    message: `Delete the ${snapshot.snapshotDate} breakdown snapshot?`,
    confirmLabel: "Delete",
    danger: true,
  });
  if (!ok) {
    return false;
  }
  await api.deleteStorageBreakdownSnapshot(snapshot.id);
  if (selectedSnapshotId.value === snapshot.id) {
    selectedSnapshotId.value = null;
    selectedSnapshot.value = null;
  }
  await loadSnapshots();
  return true;
}

export async function deleteSelectedSnapshot() {
  const snapshot = selectedSnapshot.value
    || snapshotList.value.find((item) => item.id === selectedSnapshotId.value);
  return deleteSnapshot(snapshot);
}

export function useStorageBreakdownHistory() {
  const hasSelection = computed(() => Boolean(selectedSnapshotId.value));

  return {
    snapshotList,
    selectedSnapshotId,
    selectedSnapshot,
    compareToCurrent,
    savingSnapshot,
    snapshotError,
    hasSelection,
    snapshotOptionLabel,
    loadSnapshots,
    applySnapshotSelection,
    saveDailySnapshot,
    deleteSnapshot,
    deleteSelectedSnapshot,
  };
}
