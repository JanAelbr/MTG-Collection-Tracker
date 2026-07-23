import { describe, expect, it } from "vitest";
import {
  acceptOcrParse,
  fixOcrSetCode,
  isAlchemyCollectorNumber,
  MIN_OCR_CONFIDENCE,
  normalizeOcrText,
  parseCollectorAndSet,
  setCodeCandidates,
} from "./cardOcr";

describe("cardOcr parseCollectorAndSet", () => {
  it("parses modern collector line with slash and set code", () => {
    expect(parseCollectorAndSet("279/291 C\nCLU · EN")).toMatchObject({
      setCode: "CLU",
      collectorNumber: "279",
      usedSlash: true,
    });
  });

  it("parses spaced slash forms", () => {
    expect(parseCollectorAndSet("42 / 264 MH2 EN")).toMatchObject({
      setCode: "MH2",
      collectorNumber: "42",
      usedSlash: true,
    });
  });

  it("parses lettered collector numbers", () => {
    expect(parseCollectorAndSet("12a/281 LTR EN")).toMatchObject({
      setCode: "LTR",
      collectorNumber: "12A",
      usedSlash: true,
    });
  });

  it("rejects alchemy collector numbers", () => {
    expect(isAlchemyCollectorNumber("A-123")).toBe(true);
    expect(parseCollectorAndSet("A-123/280 SNC EN")).toBeNull();
  });

  it("parses set code without a collector number", () => {
    expect(parseCollectorAndSet("CLU · EN")).toMatchObject({
      setCode: "CLU",
      collectorNumber: null,
      usedSlash: false,
    });
  });

  it("returns null without a set code", () => {
    expect(parseCollectorAndSet("279/291")).toBeNull();
  });

  it("normalizes noisy OCR text", () => {
    expect(normalizeOcrText("  clu · en  ")).toBe("CLU EN");
  });

  it("fixes common set-code OCR substitutions", () => {
    expect(fixOcrSetCode("CL0")).toBe("CLO");
    expect(fixOcrSetCode("MH5")).toBe("MHS");
    expect(setCodeCandidates("CL0")).toContain("CLO");
  });

  it("accepts slash parses even with low confidence", () => {
    const parsed = parseCollectorAndSet("10/264 LTR EN");
    expect(acceptOcrParse(parsed, 20)).toBe(true);
  });

  it("rejects low-confidence non-slash parses", () => {
    const parsed = parseCollectorAndSet("161 MH3 EN");
    expect(parsed?.usedSlash).toBe(false);
    expect(acceptOcrParse(parsed, MIN_OCR_CONFIDENCE - 1)).toBe(false);
    expect(acceptOcrParse(parsed, MIN_OCR_CONFIDENCE)).toBe(true);
  });

  it("accepts set-only parses", () => {
    const parsed = parseCollectorAndSet("MH3 EN");
    expect(parsed?.collectorNumber).toBeNull();
    expect(acceptOcrParse(parsed, 10)).toBe(true);
    expect(acceptOcrParse(parsed, 10, { allowSetOnly: false })).toBe(false);
  });
});
