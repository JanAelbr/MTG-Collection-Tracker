import { ref } from "vue";
import { api, ignoreAborted, isApiAbortError } from "../api";

const availableSets = ref([]);
const loadingAvailableSets = ref(false);
const loadError = ref("");
let inflight = null;

export async function fetchAvailableManagerSets({ force = false } = {}) {
  if (!force && inflight) {
    return inflight;
  }

  inflight = (async () => {
    loadingAvailableSets.value = true;
    if (force) {
      loadError.value = "";
    }
    try {
      const payload = await ignoreAborted(api.listAvailableManagerSets());
      if (payload) {
        availableSets.value = payload.sets || [];
        loadError.value = "";
      }
    } catch (error) {
      if (!isApiAbortError(error)) {
        availableSets.value = [];
        loadError.value = error.message || "Could not load available sets.";
      }
    } finally {
      loadingAvailableSets.value = false;
      inflight = null;
    }
  })();

  return inflight;
}

export function removeAvailableSet(setCode) {
  const normalized = String(setCode || "").trim().toUpperCase();
  if (!normalized) {
    return;
  }
  availableSets.value = availableSets.value.filter((set) => set.setCode !== normalized);
}

export function useAvailableManagerSets() {
  return {
    availableSets,
    loadingAvailableSets,
    loadError,
    fetchAvailableManagerSets,
    removeAvailableSet,
  };
}
