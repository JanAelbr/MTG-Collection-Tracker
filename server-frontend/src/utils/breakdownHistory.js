import { formatEuro, formatProfit } from "./format.js";

export const HISTORY_TOP_N = 3;
export const HISTORY_TOP_SERIES = "top";
export const HISTORY_METRIC_VALUE = "value";
export const HISTORY_METRIC_CHANGE = "change";
export const HISTORY_SCALE_ABSOLUTE = "absolute";
export const HISTORY_SCALE_RELATIVE = "relative";

export function normalizeHistoryView(raw) {
  return {
    metric: raw?.metric === HISTORY_METRIC_CHANGE
      ? HISTORY_METRIC_CHANGE
      : HISTORY_METRIC_VALUE,
    scale: raw?.scale === HISTORY_SCALE_RELATIVE
      ? HISTORY_SCALE_RELATIVE
      : HISTORY_SCALE_ABSOLUTE,
  };
}

export function loadHistoryView(storageKey) {
  if (!storageKey || typeof localStorage === "undefined") {
    return normalizeHistoryView(null);
  }
  try {
    return normalizeHistoryView(JSON.parse(localStorage.getItem(`${storageKey}:view`) || "null"));
  } catch {
    return normalizeHistoryView(null);
  }
}

export function saveHistoryView(storageKey, view) {
  if (!storageKey || typeof localStorage === "undefined") {
    return;
  }
  localStorage.setItem(`${storageKey}:view`, JSON.stringify(normalizeHistoryView(view)));
}

export function rebaseSeriesValues(values, { metric, scale } = normalizeHistoryView(null)) {
  const nums = (values || []).map((value) => Number(value) || 0);
  const { metric: kind, scale: unit } = normalizeHistoryView({ metric, scale });
  if (kind === HISTORY_METRIC_VALUE && unit === HISTORY_SCALE_ABSOLUTE) {
    return nums;
  }
  if (kind === HISTORY_METRIC_VALUE) {
    const base = nums.find((value) => value !== 0);
    if (base == null) {
      return nums.map(() => 0);
    }
    return nums.map((value) => (value / base) * 100);
  }
  if (unit === HISTORY_SCALE_ABSOLUTE) {
    return nums.map((value, index) => (index === 0 ? 0 : value - nums[index - 1]));
  }
  return nums.map((value, index) => {
    if (index === 0) {
      return 0;
    }
    const previous = nums[index - 1];
    if (previous === 0) {
      return 0;
    }
    return ((value - previous) / previous) * 100;
  });
}

export function formatHistoryPlotValue(value, view) {
  const { metric, scale } = normalizeHistoryView(view);
  if (value == null || Number.isNaN(Number(value))) {
    return "Unknown";
  }
  const amount = Number(value);
  if (scale === HISTORY_SCALE_RELATIVE) {
    const formatted = `${Math.abs(amount).toFixed(1)}%`;
    if (metric === HISTORY_METRIC_CHANGE) {
      if (amount > 0) {
        return `+${formatted}`;
      }
      if (amount < 0) {
        return `−${formatted}`;
      }
    }
    return amount < 0 ? `−${formatted}` : formatted;
  }
  if (metric === HISTORY_METRIC_CHANGE) {
    return amount === 0 ? formatEuro(0) : formatProfit(amount);
  }
  return formatEuro(amount);
}

export function formatHistoryAxisValue(value, view) {
  const { metric, scale } = normalizeHistoryView(view);
  if (value == null || Number.isNaN(Number(value))) {
    return "";
  }
  const amount = Number(value);
  if (scale === HISTORY_SCALE_RELATIVE) {
    const abs = Math.abs(amount);
    const formatted = `${abs >= 100 ? abs.toFixed(0) : abs.toFixed(1)}%`;
    if (metric === HISTORY_METRIC_CHANGE && amount < 0) {
      return `−${formatted}`;
    }
    if (metric === HISTORY_METRIC_CHANGE && amount > 0) {
      return `+${formatted}`;
    }
    return amount < 0 ? `−${formatted}` : formatted;
  }
  if (metric === HISTORY_METRIC_CHANGE) {
    return amount === 0 ? formatEuro(0) : formatProfit(amount);
  }
  return formatEuro(amount);
}

export function historyPlotFromZero(view) {
  const { metric, scale } = normalizeHistoryView(view);
  return metric === HISTORY_METRIC_VALUE && scale === HISTORY_SCALE_ABSOLUTE;
}

export function seriesValue(row) {
  return Number(row?.current) || 0;
}

export function formatArtStyleSeriesLabel(id, label = "") {
  const text = String(label || "").trim();
  const rawId = String(id || "");
  const separator = rawId.indexOf("|");
  if (separator <= 0) {
    return text || rawId;
  }
  const setCode = rawId.slice(0, separator);
  const style = rawId.slice(separator + 1);
  if (text.startsWith(`${setCode} `) || text.startsWith(`${setCode}|`)) {
    return text;
  }
  return `${setCode} ${text || style}`.trim();
}

export function pointMix(point, source) {
  if (source === "storage") {
    return point?.locations || [];
  }
  if (source === "set") {
    return point?.sets || [];
  }
  if (source === "artStyle") {
    return point?.artStyles || [];
  }
  return [];
}

export function historySourceOptions(_history) {
  return [
    { id: "all", label: "All" },
    { id: "set", label: "Set" },
    { id: "artStyle", label: "Art style" },
    { id: "storage", label: "Storage" },
  ];
}

export function collectSeriesMeta(points = [], source) {
  const map = new Map();
  for (const point of points) {
    for (const row of pointMix(point, source)) {
      const id = String(row.id || "");
      if (!id) {
        continue;
      }
      const previous = map.get(id) || { id, label: row.label || id };
      previous.label = source === "artStyle"
        ? formatArtStyleSeriesLabel(id, row.label || previous.label)
        : (row.label || previous.label);
      map.set(id, previous);
    }
  }
  return [...map.values()];
}

export function seriesPickerOptions(points, source) {
  const named = collectSeriesMeta(points, source)
    .map((item) => ({
      ...item,
      value: lastAmount(points, source, item.id),
    }))
    .sort((left, right) => {
      const delta = right.value - left.value;
      return delta || left.label.localeCompare(right.label);
    });
  return [
    { id: HISTORY_TOP_SERIES, label: `Top ${HISTORY_TOP_N}`, value: null },
    ...named,
  ];
}

function lastAmount(points, source, seriesId) {
  if (!points.length) {
    return 0;
  }
  const row = pointMix(points[points.length - 1], source).find((item) => item.id === seriesId);
  return seriesValue(row);
}

function withPlotValues(series, view) {
  const plot = normalizeHistoryView(view);
  return series.map((item) => {
    const rawValues = item.values || [];
    return {
      ...item,
      rawValues,
      values: rebaseSeriesValues(rawValues, plot),
    };
  });
}

export function buildHistoryChartView(
  points = [],
  {
    source = "all",
    series = HISTORY_TOP_SERIES,
    topN = HISTORY_TOP_N,
    metric = HISTORY_METRIC_VALUE,
    scale = HISTORY_SCALE_ABSOLUTE,
  } = {},
) {
  const view = normalizeHistoryView({ metric, scale });
  const dates = points.map((point) => point.date);
  if (source === "all") {
    return {
      dates,
      ...view,
      series: withPlotValues([{
        id: "all",
        label: "All",
        values: points.map((point) => seriesValue(point)),
        copies: points.map((point) => Number(point?.copies) || 0),
      }], view),
    };
  }

  const metas = collectSeriesMeta(points, source);
  let selected;
  if (series && series !== HISTORY_TOP_SERIES && metas.some((item) => item.id === series)) {
    selected = metas.filter((item) => item.id === series);
  } else {
    selected = metas
      .slice()
      .sort((left, right) => {
        const delta = lastAmount(points, source, right.id)
          - lastAmount(points, source, left.id);
        return delta || left.label.localeCompare(right.label);
      })
      .slice(0, topN);
  }

  return {
    dates,
    ...view,
    series: withPlotValues(selected.map((meta) => ({
      id: meta.id,
      label: source === "artStyle"
        ? formatArtStyleSeriesLabel(meta.id, meta.label)
        : meta.label,
      values: points.map((point) => {
        const row = pointMix(point, source).find((item) => item.id === meta.id);
        return seriesValue(row);
      }),
      copies: points.map((point) => {
        const row = pointMix(point, source).find((item) => item.id === meta.id);
        return Number(row?.copies) || 0;
      }),
    })), view),
  };
}

export function parseArtStyleSeriesId(id, label = "") {
  const rawId = String(id || "");
  const separator = rawId.indexOf("|");
  if (separator <= 0) {
    const artStyle = String(label || rawId).trim();
    return { id: rawId, setCode: "", artStyle };
  }
  return {
    id: rawId,
    setCode: rawId.slice(0, separator),
    artStyle: rawId.slice(separator + 1),
  };
}

export const MOVER_SCALE_PERCENT = "percent";
export const MOVER_SCALE_ABSOLUTE = "absolute";
const MOVER_SCALE_STORAGE_KEY = "favorites-home:mover-scale";

export function normalizeMoverScale(raw) {
  return raw === MOVER_SCALE_ABSOLUTE ? MOVER_SCALE_ABSOLUTE : MOVER_SCALE_PERCENT;
}

export function loadMoverScale() {
  if (typeof localStorage === "undefined") {
    return MOVER_SCALE_PERCENT;
  }
  try {
    return normalizeMoverScale(localStorage.getItem(MOVER_SCALE_STORAGE_KEY));
  } catch {
    return MOVER_SCALE_PERCENT;
  }
}

export function saveMoverScale(scale) {
  if (typeof localStorage === "undefined") {
    return;
  }
  localStorage.setItem(MOVER_SCALE_STORAGE_KEY, normalizeMoverScale(scale));
}

export function topArtStyleMoversFromHistory(
  points = [],
  { limit = 3, favoriteIds, favoriteSetCodes, direction = "up", scale } = {},
) {
  if (!Array.isArray(points) || points.length < 2) {
    return [];
  }
  const falling = direction === "down";
  const byEuro = normalizeMoverScale(scale) === MOVER_SCALE_ABSOLUTE;
  const allowed = favoriteIds == null
    ? null
    : new Set(
      [...favoriteIds].map((id) => String(id || "").trim()).filter(Boolean),
    );
  const allowedSets = favoriteSetCodes == null
    ? null
    : new Set(
      [...favoriteSetCodes]
        .map((code) => String(code || "").trim().toUpperCase())
        .filter(Boolean),
    );
  if ((allowed && allowed.size === 0) || (allowedSets && allowedSets.size === 0)) {
    return [];
  }
  const currentRows = points[points.length - 1]?.artStyles || [];
  const previousRows = points[points.length - 2]?.artStyles || [];
  const previousById = new Map(
    previousRows.map((row) => [String(row.id || ""), seriesValue(row)]),
  );
  const movers = [];
  for (const row of currentRows) {
    const id = String(row.id || "");
    if (!id || (allowed && !allowed.has(id))) {
      continue;
    }
    const current = seriesValue(row);
    const previous = previousById.get(id);
    if (!(previous > 0)) {
      continue;
    }
    if (falling ? !(current < previous) : !(current > previous)) {
      continue;
    }
    const parsed = parseArtStyleSeriesId(id, row.label);
    if (allowedSets && !allowedSets.has(String(parsed.setCode || "").toUpperCase())) {
      continue;
    }
    movers.push({
      id,
      setCode: parsed.setCode,
      artStyle: parsed.artStyle,
      label: formatArtStyleSeriesLabel(id, row.label),
      current,
      previous,
      delta: current - previous,
      percent: ((current - previous) / previous) * 100,
    });
  }
  movers.sort((left, right) => {
    if (byEuro) {
      return falling
        ? left.delta - right.delta || left.current - right.current
        : right.delta - left.delta || right.current - left.current;
    }
    if (falling) {
      return left.percent - right.percent || left.current - right.current;
    }
    return right.percent - left.percent || right.current - left.current;
  });
  return movers.slice(0, Math.max(0, limit));
}

export function topArtStyleRisersFromHistory(points = [], options = {}) {
  return topArtStyleMoversFromHistory(points, { ...options, direction: "up" });
}
