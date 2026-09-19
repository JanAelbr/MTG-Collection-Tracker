import { describe, expect, it } from "vitest";
import {
  lastPriceSyncOutcome,
  normalizePriceSyncMovers,
  priceSyncHasMovers,
  priceSyncMoversModalOpen,
  recordCompletedPriceSync,
  shouldStartStartupPriceSync,
} from "./startupPriceSync";

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

describe("recordCompletedPriceSync", () => {
  it("stores unchanged copy for the user", () => {
    recordCompletedPriceSync({
      status: "completed",
      pricesUnchanged: true,
      message: "Prices unchanged since last sync.",
      movers: { risers: [], fallers: [] },
    });
    expect(lastPriceSyncOutcome.value.pricesUnchanged).toBe(true);
    expect(lastPriceSyncOutcome.value.message).toContain("unchanged");
    expect(priceSyncHasMovers(lastPriceSyncOutcome.value)).toBe(false);
  });

  it("opens the movers modal after a changed sync", () => {
    recordCompletedPriceSync({
      status: "completed",
      pricesUnchanged: false,
      movers: {
        absolute: { risers: [{ id: "a", label: "Riser" }], fallers: [] },
        relative: { risers: [], fallers: [{ id: "b", label: "Faller" }] },
      },
    });
    expect(lastPriceSyncOutcome.value.pricesUnchanged).toBe(false);
    expect(priceSyncHasMovers(lastPriceSyncOutcome.value)).toBe(true);
    expect(priceSyncMoversModalOpen.value).toBe(true);
  });

  it("normalizes legacy flat mover lists", () => {
    const movers = normalizePriceSyncMovers({
      risers: [{ id: "a" }],
      fallers: [{ id: "b" }],
    });
    expect(movers.absolute.risers[0].id).toBe("a");
    expect(movers.relative.fallers[0].id).toBe("b");
  });
});
