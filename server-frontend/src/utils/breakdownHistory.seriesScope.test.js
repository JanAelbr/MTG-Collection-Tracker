import { describe, expect, it } from "vitest";
import { historySeriesCardScope } from "./breakdownHistory";

describe("historySeriesCardScope", () => {
  it("opens a set series by set code", () => {
    expect(historySeriesCardScope("set", { id: "ltr", label: "LTR" })).toEqual({
      source: "set",
      setCode: "LTR",
      artStyle: "",
      label: "LTR",
    });
  });

  it("opens an art style series from set|style ids", () => {
    expect(historySeriesCardScope("artStyle", {
      id: "LTR|14. Borderless poster",
      label: "LTR 14. Borderless poster",
    })).toEqual({
      source: "artStyle",
      setCode: "LTR",
      artStyle: "14. Borderless poster",
      label: "LTR 14. Borderless poster",
    });
  });

  it("skips all and storage series", () => {
    expect(historySeriesCardScope("all", { id: "all", label: "All" })).toBeNull();
    expect(historySeriesCardScope("storage", { id: "storage:general", label: "General" })).toBeNull();
  });
});
