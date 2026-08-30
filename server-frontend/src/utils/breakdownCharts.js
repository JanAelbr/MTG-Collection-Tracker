import { historySourceOptions, HISTORY_TOP_SERIES } from "./breakdownHistory.js";

export const DEDICATED_BREAKDOWN_CHARTS = [
  { id: "set-value", source: "set" },
  { id: "storage-value", source: "storage" },
];

export function normalizeBreakdownChart(raw, { sources = [], defaults = {} } = {}) {
  const sourceIds = sources.map((source) => source.id);
  const fallbackSource = defaults.source || sourceIds[0] || "set";
  const source = sourceIds.includes(raw?.source) ? raw.source : fallbackSource;
  const series = String(raw?.series || defaults.series || HISTORY_TOP_SERIES).trim() || HISTORY_TOP_SERIES;
  const id = String(raw?.id || defaults.id || "").trim() || fallbackSource;
  return { id, source, series };
}

function savedForDedicated(incoming, dedicated) {
  return incoming.find((item) => item?.id === dedicated.id)
    || incoming.find((item) => item?.source === dedicated.source)
    || {};
}

export function normalizeBreakdownCharts(raw, options = {}) {
  const sources = options.sources || historySourceOptions(options.history);
  const incoming = Array.isArray(raw) ? raw.filter(Boolean) : [];
  return DEDICATED_BREAKDOWN_CHARTS.map((item) => normalizeBreakdownChart(
    {
      ...savedForDedicated(incoming, item),
      id: item.id,
      source: item.source,
    },
    { sources, defaults: item },
  ));
}

export function loadBreakdownCharts(storageKey, options = {}) {
  if (!storageKey || typeof localStorage === "undefined") {
    return normalizeBreakdownCharts(null, options);
  }
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || "null");
    return normalizeBreakdownCharts(parsed, options);
  } catch {
    return normalizeBreakdownCharts(null, options);
  }
}

export function saveBreakdownCharts(storageKey, charts, options = {}) {
  if (!storageKey || typeof localStorage === "undefined") {
    return;
  }
  localStorage.setItem(
    storageKey,
    JSON.stringify(normalizeBreakdownCharts(charts, options)),
  );
}
