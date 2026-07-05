const DEFAULT_TTL_MS = 60_000;

const TTL_BY_PREFIX = [
  ["/meta", 30_000],
  ["/prices/sync/status", 0],
  ["/reports/search/random", 0],
  ["/settings", 60_000],
  ["/stats/", 120_000],
  ["/decks/", 120_000],
  ["/reports/", 120_000],
  ["/cards/", 120_000],
  ["/storage/", 45_000],
  ["/manager/", 45_000],
];

const store = new Map();
let knownEpoch = null;

function ttlForPath(path) {
  for (const [prefix, ttl] of TTL_BY_PREFIX) {
    if (path.startsWith(prefix)) {
      return ttl;
    }
  }
  return DEFAULT_TTL_MS;
}

export function getKnownEpoch() {
  return knownEpoch;
}

export function noteServerEpoch(epoch) {
  if (epoch == null || epoch === "") {
    return;
  }
  const next = Number(epoch);
  if (Number.isNaN(next)) {
    return;
  }
  if (knownEpoch !== null && knownEpoch !== next) {
    store.clear();
  }
  knownEpoch = next;
}

export function getCachedEntry(cacheKey) {
  const entry = store.get(cacheKey);
  if (!entry) {
    return null;
  }
  if (Date.now() > entry.expiresAt) {
    store.delete(cacheKey);
    return null;
  }
  return entry;
}

export function setCachedEntry(cacheKey, data, etag, ttlMs) {
  store.set(cacheKey, {
    data,
    etag: etag || null,
    expiresAt: Date.now() + ttlMs,
    cachedAt: Date.now(),
  });
}

export function touchCachedEntry(cacheKey) {
  const entry = store.get(cacheKey);
  if (!entry) {
    return;
  }
  const path = cacheKey.includes(":") ? cacheKey.split(":").slice(1).join(":") : cacheKey;
  entry.expiresAt = Date.now() + ttlForPath(path);
}

export function clearClientCache() {
  store.clear();
}

export function clearClientCachePrefix(prefix) {
  for (const key of [...store.keys()]) {
    if (key.includes(prefix)) {
      store.delete(key);
    }
  }
}

const MUTATION_PREFIXES = {
  "/settings": ["/settings", "/stats/", "/reports/", "/decks/", "/cards/", "/storage/"],
  "/storage/": ["/storage/", "/reports/", "/stats/"],
  "/manager/": ["/manager/", "/stats/", "/reports/", "/decks/", "/storage/"],
  "/decks/": ["/decks/", "/stats/"],
  "/prices/sync": () => clearClientCache(),
};

export function invalidateAfterMutation(path, method) {
  if (method !== "POST" && method !== "PATCH" && method !== "DELETE") {
    return;
  }
  if (path.startsWith("/prices/sync")) {
    clearClientCache();
    return;
  }
  for (const [prefix, targets] of Object.entries(MUTATION_PREFIXES)) {
    if (!path.startsWith(prefix)) {
      continue;
    }
    if (typeof targets === "function") {
      targets();
      return;
    }
    for (const target of targets) {
      clearClientCachePrefix(target);
    }
    return;
  }
}

export function cacheKeyFor(method, path) {
  return `${method}:${path}`;
}

export function clientTtlForPath(path) {
  return ttlForPath(path);
}
