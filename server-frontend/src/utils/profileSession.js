// Active profile id for this browser tab. sessionStorage keeps tabs independent;
// localStorage remembers the last-used profile as the default for new tabs.

export const PROFILE_HEADER = "X-Profile-Id";
export const ACTIVE_PROFILE_SESSION_KEY = "lotr.activeProfileId";
export const LAST_PROFILE_KEY = "lotr.lastProfileId";
const PROFILE_ID_PATTERN = /^[0-9a-f]{32}$/;

let activeProfileId = null;

function storageArea(name) {
  try {
    return globalThis[name] ?? null;
  } catch {
    return null;
  }
}

function readStored(name, key) {
  try {
    const value = storageArea(name)?.getItem(key) ?? "";
    return isValidProfileId(value) ? value : null;
  } catch {
    return null;
  }
}

function writeStored(name, key, value) {
  try {
    const area = storageArea(name);
    if (!area) {
      return;
    }
    if (value) {
      area.setItem(key, value);
    } else {
      area.removeItem(key);
    }
  } catch {
    // Private mode / quota: the in-memory id still works for this page.
  }
}

export function isValidProfileId(value) {
  return typeof value === "string" && PROFILE_ID_PATTERN.test(value);
}

/** Id remembered for this tab, else the last profile used in any tab. */
export function rememberedProfileId() {
  return readStored("sessionStorage", ACTIVE_PROFILE_SESSION_KEY)
    || readStored("localStorage", LAST_PROFILE_KEY);
}

export function hasTabProfile() {
  return readStored("sessionStorage", ACTIVE_PROFILE_SESSION_KEY) !== null;
}

export function getActiveProfileId() {
  return activeProfileId;
}

export function setActiveProfileId(profileId, { remember = true } = {}) {
  activeProfileId = isValidProfileId(profileId) ? profileId : null;
  if (!remember) {
    return;
  }
  writeStored("sessionStorage", ACTIVE_PROFILE_SESSION_KEY, activeProfileId);
  if (activeProfileId) {
    writeStored("localStorage", LAST_PROFILE_KEY, activeProfileId);
  }
}

export function forgetProfileId(profileId) {
  if (readStored("sessionStorage", ACTIVE_PROFILE_SESSION_KEY) === profileId) {
    writeStored("sessionStorage", ACTIVE_PROFILE_SESSION_KEY, null);
  }
  if (readStored("localStorage", LAST_PROFILE_KEY) === profileId) {
    writeStored("localStorage", LAST_PROFILE_KEY, null);
  }
  if (activeProfileId === profileId) {
    activeProfileId = null;
  }
}

/** Headers that scope an API request to the active profile. */
export function profileHeaders(headers = {}) {
  if (!activeProfileId) {
    return { ...headers };
  }
  return { ...headers, [PROFILE_HEADER]: activeProfileId };
}

/** Append ``profileId`` for plain links (downloads) that cannot set headers. */
export function withProfileQuery(url) {
  if (!activeProfileId) {
    return url;
  }
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}profileId=${activeProfileId}`;
}
