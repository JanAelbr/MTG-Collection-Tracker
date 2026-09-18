import { describe, expect, it } from "vitest";
import {
  normalizeBreakdownCharts,
} from "./breakdownCharts.js";
import {
  HISTORY_TOP_SERIES,
  buildHistoryChartView,
  historySourceOptions,
  seriesPickerOptions,
  topArtStyleMoversFromHistory,
  topArtStyleRisersFromHistory,
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
      { id: "LTR|Showcase", label: "Showcase", copies: 3, current: 50 },
      { id: "MH3|Showcase", label: "Showcase", copies: 1, current: 12 },
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
      { id: "LTR|Showcase", label: "Showcase", copies: 4, current: 70 },
      { id: "MH3|Showcase", label: "Showcase", copies: 1, current: 18 },
    ],
  },
];

describe("normalizeBreakdownCharts", () => {
  const sources = historySourceOptions({ hasArtStyles: true });

  it("always keeps dedicated all, set, art style, and storage charts", () => {
    const charts = normalizeBreakdownCharts(null, { sources });
    expect(charts.map((item) => item.source)).toEqual(["all", "set", "artStyle", "storage"]);
    expect(charts[0]).toMatchObject({ id: "all-value", series: HISTORY_TOP_SERIES });
    expect(charts[1]).toMatchObject({ id: "set-value", series: HISTORY_TOP_SERIES });
    expect(charts[2]).toMatchObject({ id: "art-style-value", series: HISTORY_TOP_SERIES });
    expect(charts[3]).toMatchObject({ id: "storage-value", series: HISTORY_TOP_SERIES });
  });

  it("ignores extras and preserves dedicated series", () => {
    const charts = normalizeBreakdownCharts(
      [
        { id: "all-value", source: "all" },
        { id: "storage-value", source: "storage", series: "binder:ltr" },
        { id: "extra-type", source: "type", series: "creature" },
      ],
      { sources },
    );
    expect(charts).toHaveLength(4);
    expect(charts[0]).toMatchObject({ source: "all" });
    expect(charts[3]).toMatchObject({ source: "storage", series: "binder:ltr" });
  });
});

describe("buildHistoryChartView", () => {
  it("plots all storage as one line", () => {
    const view = buildHistoryChartView(points, { source: "all" });
    expect(view.dates).toEqual(["2026-08-01", "2026-08-15"]);
    expect(view.series).toHaveLength(1);
    expect(view.series[0].values).toEqual([100, 140]);
    expect(view.series[0].rawValues).toEqual([100, 140]);
  });

  it("rebases relative prices to the first non-zero value", () => {
    const view = buildHistoryChartView(points, { source: "all", scale: "relative" });
    expect(view.series[0].values).toEqual([100, 140]);
  });

  it("indexes each series to its first non-zero price", () => {
    const view = buildHistoryChartView(points, {
      source: "set",
      series: "LTR",
      scale: "relative",
    });
    expect(view.series[0].values[0]).toBe(100);
    expect(view.series[0].values[1]).toBeCloseTo(137.5);
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

  it("prefixes art styles with set codes and orders picker options by value", () => {
    const view = buildHistoryChartView(points, { source: "artStyle" });
    expect(view.series.map((item) => item.label)).toEqual([
      "LTR Showcase",
      "MH3 Showcase",
    ]);
    expect(seriesPickerOptions(points, "set").map((item) => item.id)).toEqual([
      HISTORY_TOP_SERIES,
      "LTR",
      "LTC",
    ]);
    expect(seriesPickerOptions(points, "artStyle")[1]).toMatchObject({
      id: "LTR|Showcase",
      label: "LTR Showcase",
    });
  });
});

describe("topArtStyleRisersFromHistory", () => {
  it("returns the top percent gainers versus the previous snapshot", () => {
    const ranked = topArtStyleRisersFromHistory(points, { limit: 3 });
    expect(ranked.map((item) => item.id)).toEqual(["MH3|Showcase", "LTR|Showcase"]);
    expect(ranked[0].percent).toBeCloseTo(50);
    expect(ranked[1].percent).toBeCloseTo(40);
  });

  it("needs two snapshots", () => {
    expect(topArtStyleRisersFromHistory(points.slice(0, 1))).toEqual([]);
  });

  it("can restrict risers to favourite art styles", () => {
    const ranked = topArtStyleRisersFromHistory(points, {
      limit: 3,
      favoriteIds: ["LTR|Showcase"],
    });
    expect(ranked.map((item) => item.id)).toEqual(["LTR|Showcase"]);
    expect(topArtStyleRisersFromHistory(points, { favoriteIds: [] })).toEqual([]);
  });

  it("can restrict risers to art styles from favourite sets", () => {
    const ranked = topArtStyleRisersFromHistory(points, {
      limit: 3,
      favoriteSetCodes: ["LTR"],
    });
    expect(ranked.map((item) => item.id)).toEqual(["LTR|Showcase"]);
    expect(topArtStyleRisersFromHistory(points, { favoriteSetCodes: [] })).toEqual([]);
  });

  it("returns the top percent losers versus the previous snapshot", () => {
    const fallingPoints = [
      {
        date: "2026-08-01",
        artStyles: [
          { id: "LTR|Showcase", label: "Showcase", current: 50 },
          { id: "MH3|Showcase", label: "Showcase", current: 20 },
        ],
      },
      {
        date: "2026-08-15",
        artStyles: [
          { id: "LTR|Showcase", label: "Showcase", current: 40 },
          { id: "MH3|Showcase", label: "Showcase", current: 10 },
        ],
      },
    ];
    const ranked = topArtStyleMoversFromHistory(fallingPoints, { direction: "down" });
    expect(ranked.map((item) => item.id)).toEqual(["MH3|Showcase", "LTR|Showcase"]);
    expect(ranked[0].percent).toBeCloseTo(-50);
    expect(ranked[1].percent).toBeCloseTo(-20);
  });

  it("can rank by euro change instead of percent", () => {
    const mixed = [
      {
        date: "2026-08-01",
        artStyles: [
          { id: "LTR|A", label: "A", current: 10 },
          { id: "LTR|B", label: "B", current: 100 },
        ],
      },
      {
        date: "2026-08-15",
        artStyles: [
          { id: "LTR|A", label: "A", current: 20 },
          { id: "LTR|B", label: "B", current: 130 },
        ],
      },
    ];
    expect(topArtStyleRisersFromHistory(mixed).map((item) => item.id))
      .toEqual(["LTR|A", "LTR|B"]);
    expect(topArtStyleRisersFromHistory(mixed, { scale: "absolute" }).map((item) => item.id))
      .toEqual(["LTR|B", "LTR|A"]);
  });
});

describe("historySourceOptions", () => {
  it("always includes all, set, art style, and storage", () => {
    expect(historySourceOptions({ hasArtStyles: false }).map((item) => item.id))
      .toEqual(["all", "set", "artStyle", "storage"]);
    expect(historySourceOptions({ hasArtStyles: true }).map((item) => item.id))
      .toEqual(["all", "set", "artStyle", "storage"]);
  });
});
