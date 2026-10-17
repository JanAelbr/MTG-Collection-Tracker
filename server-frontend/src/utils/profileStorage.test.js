import { beforeEach, describe, expect, it } from "vitest";

import {
  cacheKeyFor,
  clearClientCache,
  getKnownEpoch,
  noteServerEpoch,
  setCachedEntry,
  getCachedEntry,
} from "../apiCache.js";
import {
  getActiveProfileId,
  profileHeaders,
  rememberedProfileId,
  setActiveProfileId,
} from "./profileSession.js";
import {
  migrateLegacyProfileStorage,
  profileLocalStorage,
  profileStorageKey,
  PROFILE_STORAGE_MIGRATED_KEY,
} from "./profileStorage.js";

const PROFILE_A = "a".repeat(32);
const PROFILE_B = "b".repeat(32);

function installStorage() {
  const areas = { localStorage: new Map(), sessionStorage: new Map() };
  for (const name of Object.keys(areas)) {
    const area = areas[name];
    globalThis[name] = {
      getItem: (key) => (area.has(key) ? area.get(key) : null),
      setItem: (key, value) => area.set(key, value),
      removeItem: (key) => area.delete(key),
      get length() {
        return area.size;
      },
      key: (index) => [...area.keys()][index] ?? null,
    };
  }
}

describe("profile session and storage", () => {
  beforeEach(() => {
    installStorage();
    clearClientCache();
    setActiveProfileId(null);
  });

  it("sends the active profile id and remembers it per tab", () => {
    expect(profileHeaders({ Accept: "application/json" })).toEqual({
      Accept: "application/json",
    });
    setActiveProfileId(PROFILE_A);
    expect(getActiveProfileId()).toBe(PROFILE_A);
    expect(profileHeaders()).toEqual({ "X-Profile-Id": PROFILE_A });
    expect(rememberedProfileId()).toBe(PROFILE_A);
    expect(globalThis.sessionStorage.getItem("lotr.activeProfileId")).toBe(PROFILE_A);
    expect(globalThis.localStorage.getItem("lotr.lastProfileId")).toBe(PROFILE_A);
  });

  it("namespaces profile data and migrates legacy keys once", () => {
    globalThis.localStorage.setItem("lotr.printList", "[1]");
    expect(migrateLegacyProfileStorage(PROFILE_A, ["lotr.printList"])).toBe(1);
    expect(globalThis.localStorage.getItem(profileStorageKey("lotr.printList", PROFILE_A))).toBe("[1]");
    expect(migrateLegacyProfileStorage(PROFILE_B, ["lotr.printList"])).toBe(0);

    setActiveProfileId(PROFILE_A);
    expect(profileLocalStorage.getItem("lotr.printList")).toBe("[1]");
    setActiveProfileId(PROFILE_B);
    profileLocalStorage.setItem("lotr.printList", "[2]");
    expect(globalThis.localStorage.getItem(profileStorageKey("lotr.printList", PROFILE_B))).toBe("[2]");
    expect(globalThis.localStorage.getItem(PROFILE_STORAGE_MIGRATED_KEY)).toBe("1");
  });

  it("scopes cache keys by profile and treats epochs as strings", () => {
    setActiveProfileId(PROFILE_A);
    const keyA = cacheKeyFor("GET", "/settings");
    setCachedEntry(keyA, { pageSize: 25 }, "etag", 60_000);
    setActiveProfileId(PROFILE_B);
    const keyB = cacheKeyFor("GET", "/settings");
    expect(keyA).not.toBe(keyB);
    expect(getCachedEntry(keyA)).toBeTruthy();
    expect(getCachedEntry(keyB)).toBeNull();

    noteServerEpoch("1.0");
    expect(getKnownEpoch()).toBe("1.0");
    setCachedEntry(keyB, { pageSize: 50 }, "etag", 60_000);
    noteServerEpoch("1.1");
    expect(getCachedEntry(keyB)).toBeNull();
    noteServerEpoch("1.1");
    setCachedEntry(keyB, { pageSize: 50 }, "etag", 60_000);
    expect(getCachedEntry(keyB)).toBeTruthy();
  });
});
