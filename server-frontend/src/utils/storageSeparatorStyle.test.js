import { describe, expect, it } from "vitest";

import {
  DEFAULT_STORAGE_SEPARATOR_STYLE,
  formatStorageMetaLine,
  normalizeStorageSeparatorStyle,
  storageSeparatorClassNames,
  storageStyleToCssVars,
} from "./storageSeparatorStyle.js";

describe("storageSeparatorStyle", () => {
  it("normalizes invalid values", () => {
    const style = normalizeStorageSeparatorStyle({
      tabColor: "nope",
      metaFormat: "weird",
      iconScale: "xl",
    });
    expect(style.tabColor).toBe(DEFAULT_STORAGE_SEPARATOR_STYLE.tabColor);
    expect(style.metaFormat).toBe("yearCode");
    expect(style.iconScale).toBe("lg");
  });

  it("formats meta lines", () => {
    expect(formatStorageMetaLine("2023", "LTR", "yearCode")).toBe("2023 - LTR");
    expect(formatStorageMetaLine("2023", "LTR", "codeYear")).toBe("LTR - 2023");
    expect(formatStorageMetaLine("2023", "LTR", "year")).toBe("2023");
    expect(formatStorageMetaLine("2023", "LTR", "code")).toBe("LTR");
    expect(formatStorageMetaLine("2023", "LTR", "none")).toBe("");
  });

  it("builds css vars and classes", () => {
    const vars = storageStyleToCssVars({
      tabColor: "#abcdef",
      showIcon: false,
      iconScale: "sm",
      nameScale: "lg",
    });
    expect(vars["--storage-tab"]).toBe("#abcdef");
    expect(storageSeparatorClassNames({
      showIcon: false,
      iconScale: "sm",
      nameScale: "lg",
    })).toEqual([
      "storage-separator--icon-sm",
      "storage-separator--name-lg",
      "storage-separator--no-icon",
    ]);
  });
});
