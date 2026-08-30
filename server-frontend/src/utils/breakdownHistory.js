export const HISTORY_TOP_N = 8;
export const HISTORY_TOP_SERIES = "top";

export function seriesValue(row) {
  return Number(row?.current) || 0;
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

export function historySourceOptions(history) {
  const sources = [
    { id: "all", label: "All" },
    { id: "storage", label: "Storage" },
    { id: "set", label: "Set" },
  ];
  if (history?.hasArtStyles) {
    sources.push({ id: "artStyle", label: "Art style" });
  }
  return sources;
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
      previous.label = row.label || previous.label;
      map.set(id, previous);
    }
  }
  return [...map.values()];
}

export function seriesPickerOptions(points, source) {
  const items = [{ id: HISTORY_TOP_SERIES, label: `Top ${HISTORY_TOP_N}` }];
  const named = collectSeriesMeta(points, source)
    .slice()
    .sort((left, right) => left.label.localeCompare(right.label));
  for (const item of named) {
    items.push({ id: item.id, label: item.label });
  }
  return items;
}

function lastAmount(points, source, seriesId) {
  if (!points.length) {
    return 0;
  }
  const row = pointMix(points[points.length - 1], source).find((item) => item.id === seriesId);
  return seriesValue(row);
}

export function buildHistoryChartView(
  points = [],
  { source = "all", series = HISTORY_TOP_SERIES, topN = HISTORY_TOP_N } = {},
) {
  const dates = points.map((point) => point.date);
  if (source === "all") {
    return {
      dates,
      series: [{
        id: "all",
        label: "All",
        values: points.map((point) => seriesValue(point)),
      }],
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
    series: selected.map((meta) => ({
      id: meta.id,
      label: meta.label,
      values: points.map((point) => {
        const row = pointMix(point, source).find((item) => item.id === meta.id);
        return seriesValue(row);
      }),
    })),
  };
}
