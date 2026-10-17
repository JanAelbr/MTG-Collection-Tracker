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
import { profileHeaders } from "./utils/profileSession.js";



const listeners = {
  error: new Set(),
  profileNotFound: new Set(),
};

const activeControllers = new Map();
/** In-flight GET promises keyed by method+full path (including query). */
const inflightGets = new Map();

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
  // Keep the query string so parallel GETs that differ only by params
  // (e.g. /manager/copies?finish=0 vs finish=1) do not abort each other.
  return `${method}:${path}`;
}

function requestAbortFamilyKey(method, path) {
  // Search re-fires as filters/query change; abort the previous in-flight
  // search (any query string) so superseded responses cannot win the race.
  const pathOnly = String(path || "").split("?")[0];
  if (
    pathOnly === "/reports/search" ||
    pathOnly === "/reports/search/variants"
  ) {
    return `${method}:${pathOnly}`;
  }
  return requestEndpointKey(method, path);
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

/** Called when the server no longer knows this tab's profile (deleted elsewhere). */
export function onProfileNotFound(callback) {
  listeners.profileNotFound.add(callback);
  return () => listeners.profileNotFound.delete(callback);
}

export function isProfileNotFound(response, payload) {
  return response?.status === 404 && payload?.detail?.code === "profile_not_found";
}

function errorMessage(response, payload, fallback) {
  const detail = payload?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || String(item)).join(", ");
  }
  if (detail && typeof detail.message === "string") {
    return detail.message;
  }
  return `${fallback} (${response.status})`;
}

/** Non-JSON-body requests (multipart uploads, downloads) with profile scoping. */
async function profileFetch(path, options = {}, failureLabel = "Request failed") {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: profileHeaders(options.headers || {}),
  });
  if (response.ok) {
    return response;
  }
  const payload = await parseJson(response);
  if (isProfileNotFound(response, payload)) {
    listeners.profileNotFound.forEach((listener) => listener());
  }
  const message = errorMessage(response, payload, failureLabel);
  notifyError(message);
  throw new Error(message);
}

function filenameFromResponse(response, fallback) {
  const header = response.headers.get("Content-Disposition") || "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
}

async function downloadResponse(response, fallbackName) {
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameFromResponse(response, fallbackName);
  link.click();
  URL.revokeObjectURL(url);
}

function defaultBackupFilename() {
  const stamp = new Date().toISOString().slice(0, 10);
  return `mtg-collection-${stamp}.mtgbackup.zip`;
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

  if (path.startsWith("/prices/sync/status") || path.startsWith("/profiles")) {

    return false;

  }

  return clientTtlForPath(path) > 0;

}



export async function apiRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const endpointKey = requestEndpointKey(method, path);

  if (method === "GET") {
    const inflight = inflightGets.get(endpointKey);
    if (inflight) {
      return inflight;
    }
    const requestPromise = performApiRequest(path, options).finally(() => {
      if (inflightGets.get(endpointKey) === requestPromise) {
        inflightGets.delete(endpointKey);
      }
    });
    inflightGets.set(endpointKey, requestPromise);
    return requestPromise;
  }

  return performApiRequest(path, options);
}

async function performApiRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const cacheKey = cacheKeyFor(method, path);
  const useCache = shouldUseClientCache(method, path);
  const abortFamilyKey = requestAbortFamilyKey(method, path);

  cancelActiveRequest(abortFamilyKey);
  const controller = new AbortController();
  activeControllers.set(abortFamilyKey, controller);

  if (useCache) {
    const cached = getCachedEntry(cacheKey);
    if (cached) {
      activeControllers.delete(abortFamilyKey);
      return cached.data;
    }
  }

  const headers = profileHeaders({
    "Content-Type": "application/json",
    ...(options.headers || {}),
  });

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
      if (isProfileNotFound(response, payload)) {
        listeners.profileNotFound.forEach((listener) => listener());
      }
      const message = errorMessage(response, payload, "Request failed");
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
    if (activeControllers.get(abortFamilyKey) === controller) {
      activeControllers.delete(abortFamilyKey);
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

  deleteStorageLocation: (slug, { disposition = null, moveTo = null } = {}) => {
    const params = new URLSearchParams();
    if (disposition) {
      params.set("disposition", disposition);
    }
    if (moveTo) {
      params.set("moveTo", moveTo);
    }
    const query = params.toString();
    return apiRequest(
      `/storage/locations/${encodeURIComponent(slug)}${query ? `?${query}` : ""}`,
      { method: "DELETE" },
    );
  },

  getStorageLocationCards: (slug) =>
    apiRequest(`/storage/locations/${encodeURIComponent(slug)}/cards`),

  getStorageBreakdown: (slug) =>
    apiRequest(`/storage/locations/${encodeURIComponent(slug)}/breakdown`),

  saveStorageBreakdownSnapshot: (body = {}) =>
    apiRequest("/storage/breakdowns", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listStorageBreakdownSnapshots: () => apiRequest("/storage/breakdowns"),

  listStorageBreakdownHistory: () => apiRequest("/storage/breakdowns/history"),

  pruneStorageBreakdownSnapshots: () =>
    apiRequest("/storage/breakdowns/prune", {
      method: "POST",
    }),

  getStorageBreakdownSnapshot: (snapshotId) =>
    apiRequest(`/storage/breakdowns/${encodeURIComponent(snapshotId)}`),

  deleteStorageBreakdownSnapshot: (snapshotId) =>
    apiRequest(`/storage/breakdowns/${encodeURIComponent(snapshotId)}`, {
      method: "DELETE",
    }),

  deleteInstance: (instanceId) =>
    apiRequest(`/storage/instances/${instanceId}`, {

      method: "DELETE",

    }),

  getSalesListed: () => apiRequest("/sales/listed"),

  getSalesSold: () => apiRequest("/sales/sold"),

  createSaleListing: (body) =>
    apiRequest("/sales/listed", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateSaleListed: (listingId, body) =>
    apiRequest(`/sales/listed/${listingId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  sellSaleListing: (listingId, body) =>
    apiRequest(`/sales/listed/${listingId}/sell`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  unlistSaleListing: (listingId) =>
    apiRequest(`/sales/listed/${listingId}`, {
      method: "DELETE",
    }),

  updateSaleSold: (listingId, body) =>
    apiRequest(`/sales/sold/${listingId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteSaleSold: (listingId) =>
    apiRequest(`/sales/sold/${listingId}`, {
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

  getFavorites: () => apiRequest("/favorites"),

  toggleFavoriteCard: (body) =>

    apiRequest("/favorites/cards", {

      method: "POST",

      body: JSON.stringify(body),

    }),

  toggleFavoriteArtStyle: (body) =>

    apiRequest("/favorites/art-styles", {

      method: "POST",

      body: JSON.stringify(body),

    }),

  reorderFavoriteCards: (cards) =>

    apiRequest("/favorites/cards", {

      method: "PUT",

      body: JSON.stringify({ cards }),

    }),

  reorderFavoriteArtStyles: (artStyles) =>

    apiRequest("/favorites/art-styles", {

      method: "PUT",

      body: JSON.stringify({ artStyles }),

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

  getSearchFacets: () => apiRequest("/reports/search/facets"),

  getReportCards: (params = {}) => {

    const query = new URLSearchParams();

    if (params.report) query.set("report", params.report);

    if (params.setCode) query.set("setCode", params.setCode);

    if (params.family) query.set("family", "true");

    if (params.artStyle) query.set("artStyle", params.artStyle);

    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);

    if (params.foilFilter) query.set("foilFilter", params.foilFilter);

    if (params.typeFilter && params.typeFilter !== "all") {
      query.set("typeFilter", params.typeFilter);
    }

    if (params.colorFilters?.length) {
      query.set("colors", params.colorFilters.join(","));
    }

    if (params.colorMode === "includes") {
      query.set("colorMode", "includes");
    }

    if (params.storageFilters?.length) query.set("storage", params.storageFilters.join(","));

    if (params.search) query.set("search", params.search);

    if (params.rarityFilter && params.rarityFilter !== "all") query.set("rarity", params.rarityFilter);

    if (params.cmcMin != null) query.set("cmcMin", String(params.cmcMin));

    if (params.cmcMax != null) query.set("cmcMax", String(params.cmcMax));

    if (params.priceMin != null) query.set("priceMin", String(params.priceMin));

    if (params.priceMax != null) query.set("priceMax", String(params.priceMax));

    if (params.powerMin != null) query.set("powMin", String(params.powerMin));

    if (params.toughnessMin != null) query.set("tghMin", String(params.toughnessMin));

    if (params.sort) query.set("sort", params.sort);

    if (params.dir || params.sortDir) query.set("dir", params.dir || params.sortDir);

    if (params.page) query.set("page", String(params.page));

    if (params.pageSize) query.set("pageSize", String(params.pageSize));

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(`/reports/cards${suffix}`);

  },

  searchCards: (params = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.text) query.set("text", params.text);
    if (params.creatureType) query.set("creatureType", params.creatureType);
    if (params.keyword) query.set("keyword", params.keyword);
    if (params.setCode) query.set("setCode", params.setCode);
    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);
    if (params.foilFilter) query.set("foilFilter", params.foilFilter);
    if (params.typeFilter && params.typeFilter !== "all") query.set("type", params.typeFilter);
    if (params.colorFilters?.length) query.set("colors", params.colorFilters.join(","));
    if (params.colorMode === "includes") query.set("colorMode", "includes");
    if (params.colorIdentity != null) query.set("colorIdentity", params.colorIdentity.join(","));
    if (params.rarityFilter && params.rarityFilter !== "all") query.set("rarity", params.rarityFilter);
    if (params.cmcMin != null) query.set("cmcMin", String(params.cmcMin));
    if (params.cmcMax != null) query.set("cmcMax", String(params.cmcMax));
    if (params.priceMin != null) query.set("priceMin", String(params.priceMin));
    if (params.priceMax != null) query.set("priceMax", String(params.priceMax));
    if (params.powerMin != null) query.set("powMin", String(params.powerMin));
    if (params.toughnessMin != null) query.set("tghMin", String(params.toughnessMin));
    if (params.storageFilters?.length) query.set("storage", params.storageFilters.join(","));
    if (params.roleFilters?.length) query.set("roles", params.roleFilters.join(","));
    if (params.sort) query.set("sort", params.sort);
    if (params.dir) query.set("dir", params.dir);
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
    if (params.colorMode === "includes") query.set("colorMode", "includes");
    if (params.colorIdentity != null) query.set("colorIdentity", params.colorIdentity.join(","));
    if (params.rarityFilter && params.rarityFilter !== "all") query.set("rarity", params.rarityFilter);
    if (params.cmcMin != null) query.set("cmcMin", String(params.cmcMin));
    if (params.cmcMax != null) query.set("cmcMax", String(params.cmcMax));
    if (params.priceMin != null) query.set("priceMin", String(params.priceMin));
    if (params.priceMax != null) query.set("priceMax", String(params.priceMax));
    if (params.powerMin != null) query.set("powMin", String(params.powerMin));
    if (params.toughnessMin != null) query.set("tghMin", String(params.toughnessMin));
    if (params.storageFilters?.length) query.set("storage", params.storageFilters.join(","));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/reports/search/variants${suffix}`);
  },

  getCardDetail: (setCode, collectorNumber, params = {}) => {

    const query = new URLSearchParams();

    if (params.finish != null) query.set("finish", String(params.finish));

    const suffix = query.toString() ? `?${query.toString()}` : "";

    return apiRequest(

      `/cards/${encodeURIComponent(setCode)}/${encodeURIComponent(collectorNumber)}${suffix}`,

    );

  },

  getCollectionStats: (params = {}) => {

    const query = new URLSearchParams();

    if (params.setCode) query.set("setCode", params.setCode);

    if (params.family) query.set("family", "true");

    if (params.foilFilter) query.set("foilFilter", params.foilFilter);

    if (params.artStyle) query.set("artStyle", params.artStyle);

    if (params.ownedFilter) query.set("ownedFilter", params.ownedFilter);

    if (params.typeFilter && params.typeFilter !== "all") {
      query.set("typeFilter", params.typeFilter);
    }

    if (params.colorFilters?.length) {
      query.set("colors", params.colorFilters.join(","));
    }

    if (params.colorMode === "includes") {
      query.set("colorMode", "includes");
    }

    if (params.storageFilters?.length) {
      query.set("storage", params.storageFilters.join(","));
    }

    if (params.search) query.set("search", params.search);

    if (params.rarityFilter && params.rarityFilter !== "all") {
      query.set("rarity", params.rarityFilter);
    }

    if (params.cmcMin != null) query.set("cmcMin", String(params.cmcMin));

    if (params.cmcMax != null) query.set("cmcMax", String(params.cmcMax));

    if (params.priceMin != null) query.set("priceMin", String(params.priceMin));

    if (params.priceMax != null) query.set("priceMax", String(params.priceMax));

    if (params.powerMin != null) query.set("powMin", String(params.powerMin));

    if (params.toughnessMin != null) query.set("tghMin", String(params.toughnessMin));

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

  moveDeckCardSection: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards/section`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  swapDeckCard: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/cards/swap`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  renameDeck: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  toggleDeckFavorite: (deckId) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/favorite`, {
      method: "POST",
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
    if (params.colors) query.set("colors", String(params.colors));
    if (params.uniquePrints != null) query.set("uniquePrints", params.uniquePrints ? "true" : "false");
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

  improveDeck: (body) =>
    apiRequest("/builder/improve", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getBuilderPresets: () => apiRequest("/builder/presets"),

  applyDeckProposal: (deckId, body) =>
    apiRequest(`/decks/${encodeURIComponent(deckId)}/apply-proposal`, {
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

  triggerPriceSync: (options = {}) => {
    const params = new URLSearchParams();
    if (options.setCode) {
      params.set("setCode", options.setCode);
    }
    if (options.force) {
      params.set("force", "true");
    }
    const query = params.toString();
    return apiRequest(`/prices/sync${query ? `?${query}` : ""}`, {
      method: "POST",
    });
  },

  getPriceSyncStatus: () => apiRequest("/prices/sync/status"),

  getPriceSyncArtStyleCards: ({ setCode = "", artStyle = "" } = {}) => {
    const params = new URLSearchParams();
    if (setCode) {
      params.set("setCode", setCode);
    }
    if (artStyle) {
      params.set("artStyle", artStyle);
    }
    const query = params.toString();
    return apiRequest(`/prices/sync/cards${query ? `?${query}` : ""}`);
  },

  exportCollectionBackup: async () => {
    const response = await profileFetch("/backup/export", {}, "Export failed");
    await downloadResponse(response, defaultBackupFilename());
  },

  previewCollectionBackup: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const response = await profileFetch(
      "/backup/preview",
      { method: "POST", body: form },
      "Preview failed",
    );
    return parseJson(response);
  },

  importCollectionBackup: async (file, mode = "replace") => {
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    const response = await profileFetch(
      "/backup/import",
      { method: "POST", body: form },
      "Import failed",
    );
    clearClientCache();
    return parseJson(response);
  },

  listProfiles: ({ stats = false } = {}) =>
    apiRequest(`/profiles${stats ? "?stats=true" : ""}`),

  getProfile: (profileId) => apiRequest(`/profiles/${encodeURIComponent(profileId)}`),

  createProfile: ({ name, color = null, avatar = null, copyFrom = null }) =>
    apiRequest("/profiles", {
      method: "POST",
      body: JSON.stringify({ name, color, avatar, copyFrom }),
    }),

  updateProfile: (profileId, patch) =>
    apiRequest(`/profiles/${encodeURIComponent(profileId)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteProfile: (profileId) =>
    apiRequest(`/profiles/${encodeURIComponent(profileId)}`, { method: "DELETE" }),

  activateProfile: (profileId) =>
    apiRequest(`/profiles/${encodeURIComponent(profileId)}/activate`, { method: "POST" }),

  reorderProfiles: (profileIds) =>
    apiRequest("/profiles/order", {
      method: "PUT",
      body: JSON.stringify({ profileIds }),
    }),

  importProfile: async (file, { name = "", color = "" } = {}) => {
    const form = new FormData();
    form.append("file", file);
    if (name) {
      form.append("name", name);
    }
    if (color) {
      form.append("color", color);
    }
    const response = await profileFetch(
      "/profiles/import",
      { method: "POST", body: form },
      "Profile import failed",
    );
    return parseJson(response);
  },

  exportProfile: async (profileId) => {
    const response = await profileFetch(
      `/profiles/${encodeURIComponent(profileId)}/export`,
      {},
      "Export failed",
    );
    await downloadResponse(response, defaultBackupFilename());
  },

  syncBackupCatalogs: (setCodes) =>
    apiRequest("/backup/sync-catalogs", {
      method: "POST",
      body: JSON.stringify({ setCodes }),
    }),

};


