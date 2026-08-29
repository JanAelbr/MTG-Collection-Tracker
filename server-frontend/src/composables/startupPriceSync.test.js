import { describe, expect, it } from "vitest";
import { shouldStartStartupPriceSync } from "./startupPriceSync";

describe("shouldStartStartupPriceSync", () => {
  it("polls when a sync is already running", () => {
    expect(shouldStartStartupPriceSync({ status: "running", pricesOutdated: false })).toBe("poll");
  });

  it("starts when prices are not from today", () => {
    expect(shouldStartStartupPriceSync({ status: "idle", pricesOutdated: true })).toBe("start");
  });

  it("skips when today's prices are already present", () => {
    expect(shouldStartStartupPriceSync({ status: "idle", pricesOutdated: false })).toBe("skip");
    expect(shouldStartStartupPriceSync({ status: "completed", pricesOutdated: false })).toBe("skip");
  });
});
