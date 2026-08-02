import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  FILTER_SECTION_PREFS_KEY,
  defaultFilterSectionPrefs,
  getFilterSectionPrefs,
  setFilterSectionExpanded,
  storeFilterSectionPrefs,
} from "./filterStorage.js";

function installLocalStorageMock() {
  const store = new Map();
  globalThis.localStorage = {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(String(key), String(value));
    },
    removeItem(key) {
      store.delete(String(key));
    },
    clear() {
      store.clear();
    },
  };
}

beforeEach(() => {
  installLocalStorageMock();
});

afterEach(() => {
  localStorage.removeItem(FILTER_SECTION_PREFS_KEY);
});

describe("filter section prefs", () => {
  it("defaults all groups to collapsed", () => {
    expect(defaultFilterSectionPrefs()).toEqual({
      card: false,
      role: false,
      storage: false,
      details: false,
    });
    expect(getFilterSectionPrefs()).toEqual(defaultFilterSectionPrefs());
  });

  it("hydrates and persists expanded section state", () => {
    storeFilterSectionPrefs({ card: true, details: true });
    expect(getFilterSectionPrefs()).toEqual({
      card: true,
      role: false,
      storage: false,
      details: true,
    });

    setFilterSectionExpanded("storage", true);
    expect(getFilterSectionPrefs().storage).toBe(true);
    expect(JSON.parse(localStorage.getItem(FILTER_SECTION_PREFS_KEY))).toMatchObject({
      storage: true,
    });
  });
});
