import { describe, expect, it } from "vitest";

import {
  loadPrintPricesState,
  normalizePrintPricesState,
  PRINT_PRICES_STATE_KEY,
  savePrintPricesState,
} from "./printPricesState";

describe("print prices state", () => {
  it("clamps font scale and keeps selected codes", () => {
    expect(normalizePrintPricesState({
      fontScale: 73,
      selectedCodes: ["LTR", "LTC"],
      sort: "price",
      showSetIcon: false,
    })).toMatchObject({
      fontScale: 75,
      selectedCodes: ["LTR", "LTC"],
      sort: "price",
      showSetIcon: false,
      showFullSetName: true,
      columnCount: 1,
    });
  });

  it("round-trips through localStorage", () => {
    const storage = new Map();
    globalThis.localStorage = {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, String(value)),
    };
    savePrintPricesState({ selectedCodes: ["LTR"], fontScale: 80, columnCount: 3 });
    expect(JSON.parse(storage.get(PRINT_PRICES_STATE_KEY))).toMatchObject({
      selectedCodes: ["LTR"],
      fontScale: 80,
      columnCount: 3,
    });
    expect(loadPrintPricesState().selectedCodes).toEqual(["LTR"]);
  });
});
