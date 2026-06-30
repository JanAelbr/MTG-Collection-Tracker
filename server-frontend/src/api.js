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
      invalidateAfterMutation(path, method);
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

  createManagerSet: (body) =>

    apiRequest("/manager/sets", {

      method: "POST",

      body: JSON.stringify(body),

    }),

  deleteManagerSet: (setCode) =>

    apiRequest(`/manager/sets/${encodeURIComponent(setCode)}`, {

      method: "DELETE",

    }),

  pruneOrphanCatalogs: () =>

    apiRequest("/manager/catalogs/prune-orphans", {

      method: "POST",

    }),

  toggleManagerSetFavorite: (setCode) =>

    apiRequest(`/manager/sets/${encodeURIComponent(setCode)}/favorite`, {

      method: "POST",

    }),

  getManagerSetCards: (setCode, params = {}) => {

    const query = new URLSearchParams();

    if (params.artStyle) query.set("artStyle", params.artStyle);

    if (params.search) query.set("search", params.search);

    if (params.foilFilter && params.foilFilter !== "all") query.set("foilFilter", params.foilFilter);

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

  updateCardCopyStorage: (instanceId, body) =>

    apiRequest(`/manager/copies/${instanceId}/storage`, {

      method: "PATCH",

      body: JSON.stringify(body),

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
    if (params.setCode) query.set("setCode", params.setCode);
    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);
    if (params.foilFilter) query.set("foilFilter", params.foilFilter);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("pageSize", String(params.pageSize));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/reports/search${suffix}`);
  },

  getRandomSearchExplore: (params = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.setCode) query.set("setCode", params.setCode);
    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);
    if (params.foilFilter) query.set("foilFilter", params.foilFilter);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/reports/search/random${suffix}`);
  },

  getSearchNameVariants: (params = {}) => {
    const query = new URLSearchParams();
    if (params.name) query.set("name", params.name);
    if (params.q) query.set("q", params.q);
    if (params.setCode) query.set("setCode", params.setCode);
    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);
    if (params.foilFilter) query.set("foilFilter", params.foilFilter);
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

  getDeckBrowseIndex: () => apiRequest("/decks/browse-index"),

  triggerPriceSync: () =>

    apiRequest("/prices/sync", {

      method: "POST",

    }),

  getPriceSyncStatus: () => apiRequest("/prices/sync/status"),

};


