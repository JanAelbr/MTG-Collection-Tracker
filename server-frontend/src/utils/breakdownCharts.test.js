import { describe, expect, it } from "vitest";
import {
  normalizeBreakdownCharts,
} from "./breakdownCharts.js";
import {
  HISTORY_TOP_SERIES,
  buildHistoryChartView,
  historySourceOptions,
} from "./breakdownHistory.js";

const points = [
  {
    date: "2026-08-01",
    copies: 10,
    current: 100,
    locations: [
      { id: "storage:general", label: "General", copies: 6, current: 40 },
      { id: "binder:ltr", label: "LTR binder", copies: 4, current: 60 },
    ],
    sets: [
      { id: "LTR", label: "LTR", copies: 8, current: 80 },
      { id: "LTC", label: "LTC", copies: 2, current: 20 },
    ],
    artStyles: [
      { id: "Showcase", label: "Showcase", copies: 3, current: 50 },
    ],
  },
  {
    date: "2026-08-15",
    copies: 12,
    current: 140,
    locations: [
      { id: "storage:general", label: "General", copies: 7, current: 50 },
      { id: "binder:ltr", label: "LTR binder", copies: 5, current: 90 },
    ],
    sets: [
      { id: "LTR", label: "LTR", copies: 9, current: 110 },
      { id: "LTC", label: "LTC", copies: 3, current: 30 },
    ],
    artStyles: [
      { id: "Showcase", label: "Showcase", copies: 4, current: 70 },
    ],
  },
];

describe("normalizeBreakdownCharts", () => {
  const sources = historySourceOptions({ hasArtStyles: true });

  it("always keeps dedicated set and storage charts", () => {
    const charts = normalizeBreakdownCharts(null, { sources });
    expect(charts.map((item) => item.source)).toEqual(["set", "storage"]);
    expect(charts[0]).toMatchObject({ id: "set-value", series: HISTORY_TOP_SERIES });
    expect(charts[1]).toMatchObject({ id: "storage-value", series: HISTORY_TOP_SERIES });
  });

  it("ignores extras and preserves dedicated series", () => {
    const charts = normalizeBreakdownCharts(
      [
        { id: "all-value", source: "all" },
        { id: "storage-value", source: "storage", series: "binder:ltr" },
        { id: "extra-art", source: "artStyle", series: "Showcase" },
      ],
      { sources },
    );
    expect(charts).toHaveLength(2);
    expect(charts[0]).toMatchObject({ source: "set" });
    expect(charts[1]).toMatchObject({ source: "storage", series: "binder:ltr" });
  });
});

describe("buildHistoryChartView", () => {
  it("plots all storage as one line", () => {
    const view = buildHistoryChartView(points, { source: "all" });
    expect(view.dates).toEqual(["2026-08-01", "2026-08-15"]);
    expect(view.series).toHaveLength(1);
    expect(view.series[0].values).toEqual([100, 140]);
  });

  it("keeps the top storage locations by latest value", () => {
    const view = buildHistoryChartView(points, { source: "storage" });
    expect(view.series.map((item) => item.id)).toEqual(["binder:ltr", "storage:general"]);
    expect(view.series[0].values).toEqual([60, 90]);
  });

  it("can pin one set", () => {
    const view = buildHistoryChartView(points, {
      source: "set",
      series: "LTC",
    });
    expect(view.series).toHaveLength(1);
    expect(view.series[0].values).toEqual([20, 30]);
  });
});

describe("historySourceOptions", () => {
  it("adds art style only when snapshots include it", () => {
    expect(historySourceOptions({ hasArtStyles: false }).map((item) => item.id))
      .toEqual(["all", "storage", "set"]);
    expect(historySourceOptions({ hasArtStyles: true }).some((item) => item.id === "artStyle"))
      .toBe(true);
  });
});
