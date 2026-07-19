import {

  cacheKeyFor,

  clearClientCache,

  clientTtlForPath,

  getCachedEntry,

  invalidateAfterMutation,

  noteServerEpoch,

  setCachedEntry,

  touchCachedEntry,

} from "./apiCache.js";



const listeners = {
  error: new Set(),
};

const activeControllers = new Map();

export class ApiAbortError extends Error {
  constructor() {
    super("Request aborted");
    this.name = "ApiAbortError";
  }
}

export function isApiAbortError(error) {
  return error instanceof ApiAbortError || error?.name === "ApiAbortError";
}

export function ignoreAborted(promise) {
  return promise.catch((error) => {
    if (isApiAbortError(error)) {
      return undefined;
    }
    throw error;
  });
}

function requestEndpointKey(method, path) {
  const [pathname] = path.split("?");
  return `${method}:${pathname}`;
}

function cancelActiveRequest(key) {
  const existing = activeControllers.get(key);
  if (existing) {
    existing.abort();
    activeControllers.delete(key);
  }
}

function notifyError(message) {
  for (const listener of listeners.error) {
    listener(message);
  }
}

export function onError(callback) {
  listeners.error.add(callback);
  return () => listeners.error.delete(callback);
}



async function parseJson(response) {

  const text = await response.text();

  if (!text) {

    return null;

  }

  try {

    return JSON.parse(text);

  } catch {

    return { detail: text };

  }

}



function shouldUseClientCache(method, path) {

  if (method !== "GET") {

    return false;

  }

  if (path.startsWith("/prices/sync/status")) {

    return false;

  }

  return clientTtlForPath(path) > 0;

}



export async function apiRequest(path, options = {}) {

  const method = (options.method || "GET").toUpperCase();

  const cacheKey = cacheKeyFor(method, path);

  const useCache = shouldUseClientCache(method, path);

  const endpointKey = requestEndpointKey(method, path);

  cancelActiveRequest(endpointKey);

  const controller = new AbortController();

  activeControllers.set(endpointKey, controller);



  if (useCache) {

    const cached = getCachedEntry(cacheKey);

    if (cached) {

      activeControllers.delete(endpointKey);

      return cached.data;

    }

  }



  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (useCache) {
    const cached = getCachedEntry(cacheKey);
    if (cached?.etag) {
      headers["If-None-Match"] = cached.etag;
    }
  }

  try {
    const response = await fetch(`/api${path}`, {
      ...options,
      method,
      headers,
      signal: controller.signal,
      cache: options.cache ?? "no-store",
    });

    noteServerEpoch(response.headers.get("X-Cache-Epoch"));

    if (response.status === 304 && useCache) {
      const cached = getCachedEntry(cacheKey);
      if (cached) {
        touchCachedEntry(cacheKey);
        return cached.data;
      }
    }

    const payload = await parseJson(response);
    if (!response.ok) {
      const detail = payload?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((item) => item.msg || String(item)).join(", ")
            : `Request failed (${response.status})`;
      notifyError(message);
      throw new Error(message);
    }

    if (useCache) {
      setCachedEntry(
        cacheKey,
        payload,
        response.headers.get("ETag"),
        clientTtlForPath(path),
      );
      if (payload?.cacheEpoch != null) {
        noteServerEpoch(String(payload.cacheEpoch));
      }
    } else if (method !== "GET") {
      let mutationBody = null;
      if (options.body) {
        try {
          mutationBody = typeof options.body === "string" ? JSON.parse(options.body) : options.body;
        } catch {
          mutationBody = null;
        }
      }
      invalidateAfterMutation(path, method, mutationBody);
    }

    return payload;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new ApiAbortError();
    }
    throw error;
  } finally {
    if (activeControllers.get(endpointKey) === controller) {
      activeControllers.delete(endpointKey);
    }
  }
}



export { clearClientCache };



export const api = {

  getSettings: () => apiRequest("/settings"),

  getAppMeta: () => apiRequest("/meta"),

  updateSettings: (body) =>

    apiRequest("/settings", {

      method: "PATCH",

      body: JSON.stringify(body),

    }),

  listStorageLocations: () => apiRequest("/storage/locations"),

  createStorageLocation: (body) =>

    apiRequest("/storage/locations", {

      method: "POST",

      body: JSON.stringify(body),

    }),

  updateStorageLocation: (slug, body) =>

    apiRequest(`/storage/locations/${encodeURIComponent(slug)}`, {

      method: "PATCH",

      body: JSON.stringify(body),

    }),

  deleteStorageLocation: (slug) =>

    apiRequest(`/storage/locations/${encodeURIComponent(slug)}`, {

      method: "DELETE",

    }),

  getStorageLocationCards: (slug) =>

    apiRequest(`/storage/locations/${encodeURIComponent(slug)}/cards`),

  deleteInstance: (instanceId) =>

    apiRequest(`/storage/instances/${instanceId}`, {

      method: "DELETE",

    }),

  listManagerSets: () => apiRequest("/manager/sets"),

  listAvailableManagerSets: () => apiRequest("/manager/sets/available"),

  createManagerSet: (body) =>

    apiRequest("/manager/sets", {

      method: "POST",

      body: JSON.stringify(body),

    }),

  deleteManagerSet: (setCode) =>

    apiRequest(`/manager/sets/${encodeURIComponent(setCode)}`, {

      method: "DELETE",

    }),

  reloadManagerSetCatalog: (setCode) =>

    apiRequest(`/manager/sets/${encodeURIComponent(setCode)}/catalog/reload`, {

      method: "POST",

    }),

  pruneOrphanCatalogs: () =>

    apiRequest("/manager/catalogs/prune-orphans", {

      method: "POST",

    }),

  toggleManagerSetFavorite: (setCode) =>

    apiRequest(`/manager/sets/${encodeURIComponent(setCode)}/favorite`, {

      method: "POST",

    }),

  getManagerArtStyleRules: (setCode) =>

    apiRequest(`/manager/sets/${encodeURIComponent(setCode)}/art-style-rules`),

  saveManagerArtStyleRules: (setCode, rules) =>

    apiRequest(`/manager/sets/${encodeURIComponent(setCode)}/art-style-rules`, {

      method: "PUT",

      body: JSON.stringify({ rules }),

    }),

  getManagerSetCards: (setCode, params = {}) => {

    const query = new URLSearchParams();

    if (params.artStyle) query.set("artStyle", params.artStyle);

    if (params.search) query.set("search", params.search);

    if (params.foilFilter && params.foilFilter !== "all") query.set("foilFilter", params.foilFilter);

    if (params.priceIssuesOnly) query.set("priceIssuesOnly", "true");

    if (params.page) query.set("page", String(params.page));

    if (params.pageSize) query.set("pageSize", String(params.pageSize));

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(`/manager/sets/${encodeURIComponent(setCode)}/cards${suffix}`);

  },

  updateOwnership: (body) =>

    apiRequest("/manager/ownership", {

      method: "PATCH",

      body: JSON.stringify(body),

    }),

  changeOwnershipFinish: (body) =>

    apiRequest("/manager/ownership/finish", {

      method: "PATCH",

      body: JSON.stringify(body),

    }),

  bulkUpdateOwnership: (body) =>

    apiRequest("/manager/ownership/bulk", {

      method: "POST",

      body: JSON.stringify(body),

    }),

  bulkAssignStorage: (body) =>

    apiRequest("/manager/bulk-assign-storage", {

      method: "POST",

      body: JSON.stringify(body),

    }),

  getCardCopyState: (params = {}) => {

    const query = new URLSearchParams();

    if (params.setCode) query.set("setCode", params.setCode);

    if (params.collectorNumber) query.set("collectorNumber", params.collectorNumber);

    if (params.finish != null) query.set("finish", String(params.finish));

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(`/manager/copies${suffix}`);

  },

  adjustCardCopyCount: (body) =>

    apiRequest("/manager/copies", {

      method: "PATCH",

      body: JSON.stringify(body),

    }),

  setCardCopyAllocations: (body) =>

    apiRequest("/manager/copies/allocations", {

      method: "PUT",

      body: JSON.stringify(body),

    }),

  updateCardCopyStorage: (instanceId, body) =>

    apiRequest(`/manager/copies/${instanceId}/storage`, {

      method: "PATCH",

      body: JSON.stringify(body),

    }),

  updateCardInstance: (instanceId, body) =>

    apiRequest(`/manager/copies/${instanceId}`, {

      method: "PATCH",

      body: JSON.stringify(body),

    }),

  deleteCardInstance: (instanceId) =>

    apiRequest(`/manager/copies/${instanceId}`, {

      method: "DELETE",

    }),

  getReportsMeta: () => apiRequest("/reports/meta"),

  getReportCards: (params = {}) => {

    const query = new URLSearchParams();

    if (params.report) query.set("report", params.report);

    if (params.setCode) query.set("setCode", params.setCode);

    if (params.artStyle) query.set("artStyle", params.artStyle);

    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);

    if (params.foilFilter) query.set("foilFilter", params.foilFilter);

    if (params.typeFilter && params.typeFilter !== "all") {
      query.set("typeFilter", params.typeFilter);
    }

    if (params.colorFilters?.length) {
      query.set("colors", params.colorFilters.join(","));
    }

    if (params.compareDate) query.set("compareDate", params.compareDate);

    if (params.pageSize) query.set("pageSize", String(params.pageSize));

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(`/reports/cards${suffix}`);

  },

  searchCards: (params = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.text) query.set("text", params.text);
    if (params.creatureType) query.set("creatureType", params.creatureType);
    if (params.setCode) query.set("setCode", params.setCode);
    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);
    if (params.foilFilter) query.set("foilFilter", params.foilFilter);
    if (params.typeFilter && params.typeFilter !== "all") query.set("type", params.typeFilter);
    if (params.colorFilters?.length) query.set("colors", params.colorFilters.join(","));
    if (params.rarityFilter && params.rarityFilter !== "all") query.set("rarity", params.rarityFilter);
    if (params.cmcMin != null) query.set("cmcMin", String(params.cmcMin));
    if (params.cmcMax != null) query.set("cmcMax", String(params.cmcMax));
    if (params.powerMin != null) query.set("powMin", String(params.powerMin));
    if (params.toughnessMin != null) query.set("tghMin", String(params.toughnessMin));
    if (params.storageFilters?.length) query.set("storage", params.storageFilters.join(","));
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("pageSize", String(params.pageSize));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/reports/search${suffix}`);
  },

  getSearchNameVariants: (params = {}) => {
    const query = new URLSearchParams();
    if (params.name) query.set("name", params.name);
    if (params.setCode) query.set("setCode", params.setCode);
    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);
    if (params.foilFilter) query.set("foilFilter", params.foilFilter);
    if (params.typeFilter && params.typeFilter !== "all") query.set("type", params.typeFilter);
    if (params.colorFilters?.length) query.set("colors", params.colorFilters.join(","));
    if (params.rarityFilter && params.rarityFilter !== "all") query.set("rarity", params.rarityFilter);
    if (params.cmcMin != null) query.set("cmcMin", String(params.cmcMin));
    if (params.cmcMax != null) query.set("cmcMax", String(params.cmcMax));
    if (params.powerMin != null) query.set("powMin", String(params.powerMin));
    if (params.toughnessMin != null) query.set("tghMin", String(params.toughnessMin));
    if (params.storageFilters?.length) query.set("storage", params.storageFilters.join(","));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/reports/search/variants${suffix}`);
  },

  getCardDetail: (setCode, collectorNumber, params = {}) => {

    const query = new URLSearchParams();

    if (params.finish != null) query.set("finish", String(params.finish));

    if (params.compareDate) query.set("compareDate", params.compareDate);

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(

      `/cards/${encodeURIComponent(setCode)}/${encodeURIComponent(collectorNumber)}${suffix}`,

    );

  },

  getCollectionStats: (params = {}) => {

    const query = new URLSearchParams();

    if (params.setCode) query.set("setCode", params.setCode);

    if (params.foilFilter) query.set("foilFilter", params.foilFilter);

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(`/stats/collection${suffix}`);

  },

  listDecks: () => apiRequest("/decks"),

  getDeckStats: (params = {}) => {

    const query = new URLSearchParams();

    if (params.deckId) query.set("deckId", params.deckId);

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(`/decks/stats${suffix}`);

  },

  getDeckBrowse: (deckId) =>

    apiRequest(`/decks/${encodeURIComponent(deckId)}/browse`),

  refreshDeckUnpricedMetadata: (deckId) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/metadata/refresh-unpriced`, {
      method: "POST",
    }),

  getDeckBrowseIndex: () => apiRequest("/decks/browse-index"),

  addCardToDeck: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  removeCardFromDeck: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards`, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),

  adjustDeckCardQty: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards/qty`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  setDeckCardOwned: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards/owned`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  renameDeck: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteDeck: (deckId) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}`, {
      method: "DELETE",
    }),

  createDeck: (body) =>
    apiRequest("/decks", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getBuilderCommanders: (params = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("pageSize", String(params.pageSize));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/builder/commanders${suffix}`);
  },

  previewBuilderPool: (body) =>
    apiRequest("/builder/pool/preview", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  generateDeck: (body) =>
    apiRequest("/builder/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  assessBuilderPower: (body) =>
    apiRequest("/builder/assess-power", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  bulkAddDeckCards: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards/bulk`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  previewDeckCsvImport: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards/csv/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  applyDeckCsvImport: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards/csv/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getDeckPower: (deckId) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/power`),

  triggerPriceSync: () =>

    apiRequest("/prices/sync", {

      method: "POST",

    }),

  getPriceSyncStatus: () => apiRequest("/prices/sync/status"),

  exportCollectionBackup: async () => {
    const response = await fetch("/api/backup/export");
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const message = payload?.detail || `Export failed (${response.status})`;
      notifyError(message);
      throw new Error(message);
    }
    const blob = await response.blob();
    const stamp = new Date().toISOString().slice(0, 10);
    const filename = `mtg-collection-${stamp}.mtgbackup.zip`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  previewCollectionBackup: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/backup/preview", {
      method: "POST",
      body: form,
    });
    const payload = await parseJson(response);
    if (!response.ok) {
      const message = payload?.detail || `Preview failed (${response.status})`;
      notifyError(message);
      throw new Error(message);
    }
    return payload;
  },

  importCollectionBackup: async (file, mode = "replace") => {
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    const response = await fetch("/api/backup/import", {
      method: "POST",
      body: form,
    });
    const payload = await parseJson(response);
    if (!response.ok) {
      const message = payload?.detail || `Import failed (${response.status})`;
      notifyError(message);
      throw new Error(message);
    }
    clearClientCache();
    return payload;
  },

  syncBackupCatalogs: (setCodes) =>
    apiRequest("/backup/sync-catalogs", {
      method: "POST",
      body: JSON.stringify({ setCodes }),
    }),

};


