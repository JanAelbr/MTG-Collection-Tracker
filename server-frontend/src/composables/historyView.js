import { ref } from "vue";
import {
  loadHistoryView,
  normalizeHistoryView,
  saveHistoryView,
} from "../utils/breakdownHistory";

export const STATS_HISTORY_VIEW_KEY = "settingsBreakdownHistoryCharts";

const viewsByKey = new Map();

export function useHistoryView(storageKey = STATS_HISTORY_VIEW_KEY) {
  if (!viewsByKey.has(storageKey)) {
    viewsByKey.set(storageKey, ref(loadHistoryView(storageKey)));
  }
  const historyView = viewsByKey.get(storageKey);

  function setHistoryView(patch) {
    historyView.value = normalizeHistoryView({
      ...historyView.value,
      ...patch,
    });
    saveHistoryView(storageKey, historyView.value);
  }

  return { historyView, setHistoryView };
}
