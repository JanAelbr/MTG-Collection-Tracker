import { describe, expect, it } from "vitest";

import { SEPARATOR_COLOR_PRESETS } from "./separatorColorPresets.js";

describe("separatorColorPresets", () => {
  it("provides 20 matching binder and storage themes", () => {
    expect(SEPARATOR_COLOR_PRESETS).toHaveLength(20);
    const ids = new Set();
    for (const preset of SEPARATOR_COLOR_PRESETS) {
      expect(preset.id).toBeTruthy();
      expect(ids.has(preset.id)).toBe(false);
      ids.add(preset.id);
      expect(preset.binder.inkColor).toMatch(/^#[0-9a-f]{6}$/i);
      expect(preset.binder.accentColor).toMatch(/^#[0-9a-f]{6}$/i);
      expect(preset.binder.baseColor).toMatch(/^#[0-9a-f]{6}$/i);
      expect(preset.storage.tabColor).toMatch(/^#[0-9a-f]{6}$/i);
      expect(preset.storage.nameColor).toMatch(/^#[0-9a-f]{6}$/i);
      expect(preset.storage.metaColor).toMatch(/^#[0-9a-f]{6}$/i);
      expect(preset.storage.borderColor).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
