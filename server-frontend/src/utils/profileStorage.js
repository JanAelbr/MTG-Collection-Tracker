import { getActiveProfileId } from "./profileSession.js";

// localStorage keys that hold profile data (print lists, separator styles,
// chart layouts). Device preferences such as sidebar width stay global.
export const PROFILE_SCOPED_KEYS = Object.freeze([
  "lotr.printList",
  "lotr.printList.selected",
  "lotr.print.prices",
  "lotr.separators.storageStyle",
  "lotr.separators.binderStyle",
  "lotr.separators.binderExcludedArtStyles",
  "settingsBreakdownHistoryCharts",
  "settingsBreakdownHistoryCharts:view",
  "reportPageSize",
]);

function area() {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function profileStorageKey(key, profileId = getActiveProfileId()) {
  return profileId ? `profile:${profileId}:${key}` : key;
}

/** localStorage-compatible facade that namespaces keys by the active profile. */
export const profileLocalStorage = {
  getItem(key) {
    return area()?.getItem(profileStorageKey(key)) ?? null;
  },
  setItem(key, value) {
    area()?.setItem(profileStorageKey(key), value);
  },
  removeItem(key) {
    area()?.removeItem(profileStorageKey(key));
  },
};

export function removeProfileStorage(profileId) {
  const storage = area();
  if (!storage || !profileId) {
    return;
  }
  const prefix = `profile:${profileId}:`;
  const doomed = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(prefix)) {
      doomed.push(key);
    }
  }
  doomed.forEach((key) => storage.removeItem(key));
}
