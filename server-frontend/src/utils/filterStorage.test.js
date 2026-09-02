import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  CATALOG_GALLERY_ROLLUP_KEY,
  FILTER_SECTION_PREFS_KEY,
  defaultFilterSectionPrefs,
  getFilterSectionPrefs,
  getStoredCatalogGalleryRollup,
  setFilterSectionExpanded,
  storeCatalogGalleryRollup,
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
  localStorage.removeItem(CATALOG_GALLERY_ROLLUP_KEY);
});

describe("catalog gallery rollup pref", () => {
  it("defaults to on", () => {
    expect(getStoredCatalogGalleryRollup()).toBe(true);
  });

  it("persists off and on", () => {
    storeCatalogGalleryRollup(false);
    expect(getStoredCatalogGalleryRollup()).toBe(false);
    expect(localStorage.getItem(CATALOG_GALLERY_ROLLUP_KEY)).toBe("0");
    storeCatalogGalleryRollup(true);
    expect(getStoredCatalogGalleryRollup()).toBe(true);
  });
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
