import { computed, ref } from "vue";

import { api } from "../api";
import { setDisplayName, setShortName } from "../utils/format";
import {
  applySetGalleryIconFallback,
  resolveSetGalleryIconUri,
  resolveSetIconUri,
} from "../utils/scryfall";
import { releaseYear } from "../utils/separatorItems";
import {
  formatSubsetTypeLabel,
  isSetsPagePromoType,
  isTokenOrArtSetType,
} from "../utils/setBrowserSubsets";

export const SCOPE_LOADED = "loaded";
export const SCOPE_ALL = "all";

function isSelectableSet(set) {
  return Boolean(set?.setCode) && set.setCode !== "All";
}

function isFamilyRootSet(set) {
  if (!set?.setCode) {
    return false;
  }
  if (set.isFamilyRoot != null) {
    return Boolean(set.isFamilyRoot);
  }
  const root = set.familyRoot || set.setCode;
  return set.setCode === root;
}

function compareSelectableSets(a, b) {
  const rootA = String(a.familyRoot || a.setCode);
  const rootB = String(b.familyRoot || b.setCode);
  const byRoot = rootA.localeCompare(rootB);
  if (byRoot) {
    return byRoot;
  }
  const aIsRoot = isFamilyRootSet(a) ? 0 : 1;
  const bIsRoot = isFamilyRootSet(b) ? 0 : 1;
  if (aIsRoot !== bIsRoot) {
    return aIsRoot - bIsRoot;
  }
  return String(a.setCode).localeCompare(String(b.setCode));
}

function enrichTrackedSet(set) {
  return {
    ...set,
    familyRoot: set.familyRoot || set.parentSetCode || set.setCode,
    parentSetCode: set.parentSetCode || "",
    iconUri: set.iconUri || "",
    familyMembers: set.familyMembers || [set.setCode],
    releasedAt: set.releasedAt || "",
    isFamilyRoot: isFamilyRootSet(set),
    pendingImport: false,
  };
}

function enrichAvailableSet(set) {
  const setCode = String(set.setCode || "").trim();
  const name = String(set.name || "").trim();
  const label = name ? `${name} (${setCode})` : setCode;
  return {
    setCode,
    label,
    name: name || setCode,
    iconUri: set.iconUri || "",
    setType: set.setType,
    parentSetCode: set.parentSetCode || "",
    familyMembers: set.familyMembers || [setCode],
    familyRoot: setCode,
    isFamilyRoot: true,
    ownedCount: 0,
    catalogCount: 0,
    favorite: false,
    pendingImport: true,
    releasedAt: set.releasedAt || "",
    digital: Boolean(set.digital),
  };
}

function setMatchesQuery(set, query) {
  if (!query) {
    return true;
  }
  const typeLabel = formatSubsetTypeLabel(set.setType);
  const haystack = [
    set.setCode,
    set.label,
    setDisplayName(set),
    setShortName(set),
    set.setType,
    typeLabel,
    set.familyRoot,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

export function useSeparatorSetPicker() {
  const trackedSets = ref([]);
  const availableSets = ref([]);
  const storageLocations = ref([]);
  const loading = ref(false);
  const loadError = ref("");
  const filterQuery = ref("");
  const setScope = ref(SCOPE_LOADED);
  const showTokenAndArtSets = ref(false);
  const showPromoSets = ref(false);
  const selectedCodes = ref(new Set());
  const storageSelectSlug = ref("");
  const storageSelectLoading = ref(false);
  const storageSelectError = ref("");

  const trackedByCode = computed(() => {
    const map = new Map();
    for (const set of trackedSets.value) {
      if (set?.setCode) {
        map.set(set.setCode, set);
      }
    }
    return map;
  });

  const catalogSets = computed(() => {
    const tracked = trackedSets.value
      .filter((set) => isSelectableSet(set))
      .map(enrichTrackedSet);
    const trackedCodes = new Set(tracked.map((set) => set.setCode));
    const available = availableSets.value
      .filter((set) => isSelectableSet(set) && !trackedCodes.has(set.setCode))
      .map(enrichAvailableSet);
    return [...tracked, ...available].sort(compareSelectableSets);
  });

  const selectableSets = computed(() => {
    if (setScope.value === SCOPE_ALL) {
      return catalogSets.value;
    }
    return catalogSets.value.filter((set) => !set.pendingImport);
  });

  function setGroupYear(set) {
    const rootCode = set.familyRoot || set.setCode;
    const root = trackedByCode.value.get(rootCode);
    return releaseYear(root) || releaseYear(set) || "unknown";
  }

  const visibleSets = computed(() => {
    const query = filterQuery.value.trim().toLowerCase();
    return selectableSets.value.filter((set) => {
      if (!query) {
        if (!showTokenAndArtSets.value && isTokenOrArtSetType(set.setType)) {
          return false;
        }
        if (!showPromoSets.value && isSetsPagePromoType(set.setType)) {
          return false;
        }
      }
      return setMatchesQuery(set, query);
    });
  });

  const visibleGroups = computed(() => {
    const favorites = [];
    const byYear = new Map();

    for (const set of visibleSets.value) {
      if (set.favorite && isFamilyRootSet(set)) {
        favorites.push(set);
        continue;
      }
      const year = setGroupYear(set);
      const bucket = byYear.get(year);
      if (bucket) {
        bucket.push(set);
      } else {
        byYear.set(year, [set]);
      }
    }

    const years = [...byYear.keys()].sort((a, b) => {
      if (a === "unknown") {
        return 1;
      }
      if (b === "unknown") {
        return -1;
      }
      return b.localeCompare(a);
    });

    const groups = [];
    if (favorites.length) {
      groups.push({
        key: "favorites",
        label: "Favourites",
        sets: [...favorites].sort(compareSelectableSets),
      });
    }
    for (const year of years) {
      groups.push({
        key: year,
        label: year === "unknown" ? "Unknown year" : year,
        sets: [...byYear.get(year)].sort(compareSelectableSets),
      });
    }
    return groups;
  });

  const selectedSets = computed(() => {
    const selected = [];
    for (const set of catalogSets.value) {
      if (selectedCodes.value.has(set.setCode)) {
        selected.push(set);
      }
    }
    return selected;
  });

  const loadedSelectedSets = computed(() =>
    selectedSets.value.filter((set) => !set.pendingImport),
  );

  const selectedCount = computed(() => selectedCodes.value.size);

  function isSelected(set) {
    return selectedCodes.value.has(set.setCode);
  }

  function toggleSelect(set) {
    if (!set?.setCode) {
      return;
    }
    const next = new Set(selectedCodes.value);
    if (next.has(set.setCode)) {
      next.delete(set.setCode);
    } else {
      next.add(set.setCode);
    }
    selectedCodes.value = next;
  }

  function clearSelection() {
    selectedCodes.value = new Set();
  }

  function allSelectedInGroup(group) {
    const sets = group?.sets || [];
    if (!sets.length) {
      return false;
    }
    return sets.every((set) => selectedCodes.value.has(set.setCode));
  }

  function toggleSelectYear(group) {
    const sets = group?.sets || [];
    if (!sets.length) {
      return;
    }
    const next = new Set(selectedCodes.value);
    if (allSelectedInGroup(group)) {
      for (const set of sets) {
        next.delete(set.setCode);
      }
    } else {
      for (const set of sets) {
        next.add(set.setCode);
      }
    }
    selectedCodes.value = next;
  }

  function selectAllVisible() {
    const next = new Set(selectedCodes.value);
    for (const set of visibleSets.value) {
      next.add(set.setCode);
    }
    selectedCodes.value = next;
  }

  async function selectAllInStorage(slug) {
    const locationSlug = String(slug || "").trim();
    storageSelectSlug.value = locationSlug;
    storageSelectError.value = "";
    if (!locationSlug) {
      return;
    }
    storageSelectLoading.value = true;
    try {
      const payload = await api.getStorageLocationCards(locationSlug);
      const codesInLocation = new Set();
      for (const card of payload?.cards || []) {
        const code = String(card.setCode || "").trim().toUpperCase();
        if (code) {
          codesInLocation.add(code);
        }
      }
      const selectableByCode = new Map(
        catalogSets.value
          .filter((set) => !set.pendingImport)
          .map((set) => [String(set.setCode || "").trim().toUpperCase(), set.setCode]),
      );
      const next = new Set();
      for (const code of codesInLocation) {
        const selectableCode = selectableByCode.get(code);
        if (selectableCode) {
          next.add(selectableCode);
        }
      }
      selectedCodes.value = next;
      if (!next.size) {
        storageSelectError.value = "No tracked sets found in that storage location.";
      }
    } catch (error) {
      storageSelectError.value = error.message || "Could not load storage location.";
    } finally {
      storageSelectLoading.value = false;
      storageSelectSlug.value = "";
    }
  }

  function setPickerLabel(set) {
    return setDisplayName(set) || set.setCode;
  }

  function setIconUri(set) {
    return resolveSetIconUri(set) || resolveSetGalleryIconUri(set);
  }

  function onSetIconError(event, set) {
    applySetGalleryIconFallback(event.target, set);
  }

  async function loadTrackedSets() {
    loadError.value = "";
    try {
      const payload = await api.listManagerSets();
      trackedSets.value = payload?.sets || [];
    } catch (error) {
      loadError.value = error.message || "Could not load sets.";
      trackedSets.value = [];
    }
  }

  async function loadAvailableSets() {
    try {
      const payload = await api.listAvailableManagerSets();
      availableSets.value = payload?.sets || [];
    } catch {
      availableSets.value = [];
    }
  }

  async function loadStorageLocations() {
    try {
      const payload = await api.listStorageLocations();
      storageLocations.value = payload?.locations || [];
    } catch {
      storageLocations.value = [];
    }
  }

  async function loadPicker() {
    loading.value = true;
    await Promise.all([loadTrackedSets(), loadAvailableSets(), loadStorageLocations()]);
    loading.value = false;
  }

  return {
    SCOPE_LOADED,
    SCOPE_ALL,
    trackedSets,
    availableSets,
    storageLocations,
    loading,
    loadError,
    filterQuery,
    setScope,
    showTokenAndArtSets,
    showPromoSets,
    selectedCodes,
    selectedSets,
    loadedSelectedSets,
    selectedCount,
    visibleSets,
    visibleGroups,
    storageSelectSlug,
    storageSelectLoading,
    storageSelectError,
    isSelected,
    toggleSelect,
    clearSelection,
    allSelectedInGroup,
    toggleSelectYear,
    selectAllVisible,
    selectAllInStorage,
    setPickerLabel,
    setIconUri,
    onSetIconError,
    loadPicker,
  };
}
