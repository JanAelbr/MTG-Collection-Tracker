import { describe, expect, it } from "vitest";

import {
  binderArtStyleKey,
  buildBinderArtStyleGroups,
  buildBinderSeparators,
  buildStorageSeparators,
  formatArtStyleNumberRange,
  loadBinderExcludedArtStyles,
  releaseYear,
  saveBinderExcludedArtStyles,
} from "./separatorItems.js";

describe("separatorItems", () => {
  it("extracts release year", () => {
    expect(releaseYear({ releasedAt: "2023-06-16" })).toBe("2023");
    expect(releaseYear({ releasedAt: "" })).toBe("");
  });

  it("formats art style number ranges", () => {
    expect(formatArtStyleNumberRange({ matchType: "all" })).toBe("All");
    expect(formatArtStyleNumberRange({
      matchType: "prefix",
      prefix: "A",
    })).toBe("#A…");
    expect(formatArtStyleNumberRange({
      matchType: "range",
      firstNumber: 1,
      lastNumber: 280,
    })).toBe("#1 – #280");
    expect(formatArtStyleNumberRange({
      matchType: "range_suffix",
      firstNumber: 1,
      lastNumber: 10,
      suffix: "★",
    })).toBe("#1 – #10★");
    expect(formatArtStyleNumberRange({
      matchType: "range",
      firstNumber: 149,
      lastNumber: 149,
    })).toBe("#149");
    expect(formatArtStyleNumberRange({
      matchType: "range_suffix",
      firstNumber: "5",
      lastNumber: "5",
      suffix: "a",
    })).toBe("#5a");
  });

  it("builds one storage separator per set", () => {
    const items = buildStorageSeparators([
      { setCode: "LTR", label: "The Lord of the Rings (LTR)", releasedAt: "2023-06-16" },
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      mode: "storage",
      setCode: "LTR",
      year: "2023",
    });
    expect(items[0].setName).toBe("The Lord of the Rings (LTR)");
  });

  it("builds binder separators from art style rules", () => {
    const rules = new Map([
      ["LTR", [
        { name: "Regular", firstNumber: 1, lastNumber: 280 },
        { name: "Showcase", firstNumber: 301, lastNumber: 350 },
      ]],
    ]);
    const items = buildBinderSeparators(
      [{ setCode: "LTR", label: "The Lord of the Rings (LTR)" }],
      rules,
    );
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({
      mode: "binder",
      artStyle: "Regular",
      numberRange: "#1 – #280",
    });
    expect(items[1].artStyle).toBe("Showcase");
  });

  it("skips binder separators for excluded art styles", () => {
    const rules = new Map([
      ["LTR", [
        { name: "Regular", firstNumber: 1, lastNumber: 280 },
        { name: "Showcase", firstNumber: 301, lastNumber: 350 },
      ]],
      ["MH3", []],
    ]);
    const sets = [
      { setCode: "LTR", label: "The Lord of the Rings (LTR)" },
      { setCode: "MH3", label: "Modern Horizons 3 (MH3)" },
    ];
    const groups = buildBinderArtStyleGroups(sets, rules);
    expect(groups).toHaveLength(1);
    expect(groups[0].styles.map((style) => style.artStyle)).toEqual(["Regular", "Showcase"]);
    expect(groups[0].styles[1].key).toBe(binderArtStyleKey("LTR", "Showcase"));

    const items = buildBinderSeparators(sets, rules, {
      excludedKeys: new Set([binderArtStyleKey("ltr", "Regular")]),
    });
    expect(items.map((item) => item.artStyle)).toEqual(["Showcase", ""]);
    expect(items[1].setCode).toBe("MH3");
  });

  it("remembers excluded binder art styles", () => {
    const store = new Map();
    globalThis.localStorage = {
      getItem: (key) => store.get(key) ?? null,
      setItem: (key, value) => store.set(key, value),
    };
    saveBinderExcludedArtStyles(new Set(["LTR|Showcase", "", 4]));
    expect(loadBinderExcludedArtStyles()).toEqual(new Set(["LTR|Showcase"]));
  });

  it("falls back to one binder separator when a set has no rules", () => {
    const items = buildBinderSeparators(
      [{ setCode: "MH3", label: "Modern Horizons 3 (MH3)" }],
      new Map([["MH3", []]]),
    );
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      mode: "binder",
      artStyle: "",
      numberRange: "",
    });
  });
});
