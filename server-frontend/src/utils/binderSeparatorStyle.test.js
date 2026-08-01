import { describe, expect, it } from "vitest";

import {
  binderFontStack,
  binderSeparatorClassNames,
  binderStyleToCssVars,
  DEFAULT_BINDER_SEPARATOR_STYLE,
  normalizeBinderSeparatorStyle,
  parchmentFilterFromSoftness,
} from "./binderSeparatorStyle.js";

describe("binderSeparatorStyle", () => {
  it("normalizes invalid values to defaults", () => {
    const style = normalizeBinderSeparatorStyle({
      inkColor: "not-a-color",
      borderStyle: "fancy",
      parchmentOpacity: 140,
      fontFamily: "comic",
      titleScale: "xl",
    });
    expect(style.inkColor).toBe(DEFAULT_BINDER_SEPARATOR_STYLE.inkColor);
    expect(style.borderStyle).toBe("ornate");
    expect(style.parchmentOpacity).toBe(100);
    expect(style.fontFamily).toBe("cinzel");
    expect(style.titleScale).toBe("md");
  });

  it("builds css vars from settings", () => {
    const vars = binderStyleToCssVars({
      inkColor: "#112233",
      accentColor: "#aabbcc",
      baseColor: "#ffeecc",
      parchmentOpacity: 40,
      parchmentSoftness: 0,
    });
    expect(vars["--binder-ink"]).toBe("#112233");
    expect(vars["--binder-accent"]).toBe("#aabbcc");
    expect(vars["--binder-base"]).toBe("#ffeecc");
    expect(vars["--parchment-opacity"]).toBe("0.400");
    expect(Number(vars["--parchment-brightness"])).toBeCloseTo(1.08, 2);
  });

  it("maps softness to brighter softer parchment", () => {
    const soft = parchmentFilterFromSoftness(100);
    const hard = parchmentFilterFromSoftness(0);
    expect(Number(soft.brightness)).toBeGreaterThan(Number(hard.brightness));
    expect(Number(soft.contrast)).toBeLessThan(Number(hard.contrast));
  });

  it("returns modifier class names", () => {
    const classes = binderSeparatorClassNames({
      borderStyle: "simple",
      titleScale: "lg",
      softVeil: false,
      showCorners: false,
      showJewels: true,
      showOrnament: false,
      artStyleUppercase: false,
    });
    expect(classes).toContain("binder-separator--border-simple");
    expect(classes).toContain("binder-separator--title-lg");
    expect(classes).toContain("binder-separator--no-veil");
    expect(classes).toContain("binder-separator--no-corners");
    expect(classes).toContain("binder-separator--no-ornament");
    expect(classes).toContain("binder-separator--art-normal-case");
    expect(classes).not.toContain("binder-separator--no-jewels");
  });

  it("resolves font stacks", () => {
    expect(binderFontStack("libre")).toContain("Libre Baskerville");
    expect(binderFontStack("unknown")).toContain("Cinzel");
  });
});
