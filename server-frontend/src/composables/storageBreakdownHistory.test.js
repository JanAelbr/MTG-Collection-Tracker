import { describe, expect, it } from "vitest";
import { snapshotOptionLabel, hasSnapshotForDate } from "./storageBreakdownHistory";

describe("snapshotOptionLabel", () => {
  it("shows date and combined value", () => {
    expect(snapshotOptionLabel({
      snapshotDate: "2026-08-29",
      totals: { current: 12.5 },
    })).toBe("2026-08-29 · €12.50");
  });

  it("appends a note when present", () => {
    expect(snapshotOptionLabel({
      snapshotDate: "2026-08-29",
      note: "Evening",
      totals: { current: 10 },
    })).toBe("2026-08-29 · €10.00 · Evening");
  });
});

describe("hasSnapshotForDate", () => {
  it("matches the UTC day on a snapshot list", () => {
    expect(hasSnapshotForDate(
      [{ snapshotDate: "2026-09-14" }, { snapshotDate: "2026-09-13" }],
      "2026-09-14",
    )).toBe(true);
    expect(hasSnapshotForDate([{ snapshotDate: "2026-09-13" }], "2026-09-14")).toBe(false);
  });
});
