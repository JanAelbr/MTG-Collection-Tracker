import { computed, ref } from "vue";
import { api } from "../api";
import { setCardCopyAllocations, fetchCardCopyState, updateCardCopyStorage } from "./cardContextMenu";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  canManageFinish,
} from "../utils/finishes";
import { valueForStrategy } from "../utils/priceStrategies";

export const MANAGER_TABLE_SORT_FIELDS = new Set(["number", "name", "artStyle", "value"]);

const MAX_OWNED_COPIES = 99;
const MANAGEABLE_FINISHES = [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED];

export function priceIssueLabel(issue) {
  const [kind, finish] = String(issue || "").split(":");
  const finishLabel = finish ? ` (${finish})` : "";
  if (kind === "missing_url") {
    return `Missing Cardmarket URL${finishLabel}`;
  }
  if (kind === "no_price") {
    return `No market price${finishLabel}`;
  }
  return issue;
}

export function cardPriceIssueTitle(card) {
  return (card.priceIssues || []).map(priceIssueLabel).join("; ");
}

export function copyCountForFinish(card, finish) {
  if (finish === FINISH_FOIL) {
    return card.ownedCountFoil ?? (card.ownedFoil ? 1 : 0);
  }
  if (finish === FINISH_ETCHED) {
    return card.ownedCountEtched ?? (card.ownedEtched ? 1 : 0);
  }
  return card.ownedCountNonfoil ?? (card.ownedNonfoil ? 1 : 0);
}

export function finishRowKey(card, finish) {
  return `${card.collectorNumber}:${finish}`;
}

export function locationsForFinish(card, finish) {
  if (finish === FINISH_FOIL) {
    return card.locationsFoil || [];
  }
  if (finish === FINISH_ETCHED) {
    return card.locationsEtched || [];
  }
  return card.locationsNonfoil || [];
}

export function formatLocationsSummary(locations = []) {
  if (!locations.length) {
    return "";
  }
  return locations
    .map((location) => {
      const label = String(location.label || location.slug || "").trim();
      const count = Number(location.count) || 0;
      return count > 1 ? `${label} ×${count}` : label;
    })
    .filter(Boolean)
    .join(", ");
}

function setLocationsForFinish(card, finish, locations) {
  const next = Array.isArray(locations) ? locations : [];
  if (finish === FINISH_FOIL) {
    card.locationsFoil = next;
    return;
  }
  if (finish === FINISH_ETCHED) {
    card.locationsEtched = next;
    return;
  }
  card.locationsNonfoil = next;
}

export function expandCardFinishRows(cards = []) {
  const rows = [];
  for (const card of cards) {
    const finishes = MANAGEABLE_FINISHES.filter((finish) => canManageFinish(card, finish));
    finishes.forEach((finish, index) => {
      rows.push({
        card,
        finish,
        rowKey: finishRowKey(card, finish),
        isFirstFinishRow: index === 0,
        finishRowCount: finishes.length,
      });
    });
  }
  return rows;
}

export function collectorSortKey(value) {
  const text = String(value ?? "");
  if (/^\d+$/.test(text)) {
    return [0, Number(text), ""];
  }
  return [1, 0, text];
}

export function compareCollectorNumbers(left, right) {
  const leftKey = collectorSortKey(left);
  const rightKey = collectorSortKey(right);
  for (let index = 0; index < 3; index += 1) {
    if (leftKey[index] < rightKey[index]) {
      return -1;
    }
    if (leftKey[index] > rightKey[index]) {
      return 1;
    }
  }
  return 0;
}

export function managerCardPrice(card, strategyId = "trend") {
  if (!card) {
    return null;
  }
  return valueForStrategy(
    {
      ...card,
      currentValue: card.marketValue ?? card.currentValue ?? null,
      valuesByStrategy: card.valuesByStrategy,
    },
    strategyId,
  );
}

export function compareManagerCardPrices(left, right, strategyId = "trend") {
  const leftValue = managerCardPrice(left, strategyId);
  const rightValue = managerCardPrice(right, strategyId);
  const leftMissing = leftValue == null;
  const rightMissing = rightValue == null;
  if (leftMissing && rightMissing) {
    return 0;
  }
  if (leftMissing) {
    return 1;
  }
  if (rightMissing) {
    return -1;
  }
  return leftValue - rightValue;
}

export function defaultManagerTableSortDir(sort) {
  return sort === "value" ? "desc" : "asc";
}

export function normalizeManagerTableSort(sort) {
  return MANAGER_TABLE_SORT_FIELDS.has(sort) ? sort : "number";
}

function compareManagerCards(left, right, sort, priceStrategy, ascending) {
  if (sort === "name") {
    return String(left.name || "").localeCompare(String(right.name || ""), undefined, { sensitivity: "base" });
  }
  if (sort === "artStyle") {
    return String(left.artStyle || "").localeCompare(String(right.artStyle || ""), undefined, { sensitivity: "base" });
  }
  if (sort === "value") {
    const leftValue = managerCardPrice(left, priceStrategy);
    const rightValue = managerCardPrice(right, priceStrategy);
    const leftMissing = leftValue == null;
    const rightMissing = rightValue == null;
    if (leftMissing && rightMissing) {
      return 0;
    }
    if (leftMissing) {
      return 1;
    }
    if (rightMissing) {
      return -1;
    }
    const diff = leftValue - rightValue;
    return ascending ? diff : -diff;
  }
  return compareCollectorNumbers(left.collectorNumber, right.collectorNumber);
}

export function sortManagerCards(cards = [], { sort = "number", sortDir = "asc", priceStrategy = "trend" } = {}) {
  const normalizedSort = normalizeManagerTableSort(sort);
  const ascending = sortDir === "asc";
  return [...cards].sort((left, right) => {
    const primary = compareManagerCards(left, right, normalizedSort, priceStrategy, ascending);
    if (primary !== 0) {
      if (normalizedSort === "value") {
        return primary;
      }
      return ascending ? primary : -primary;
    }
    const numberOrder = compareCollectorNumbers(left.collectorNumber, right.collectorNumber);
    if (numberOrder !== 0) {
      return numberOrder;
    }
    return String(left.name || "").localeCompare(String(right.name || ""), undefined, { sensitivity: "base" });
  });
}

function buildAllocationsFromLocations(locations, totalCount, defaultLocationSlug) {
  const normalized = (locations || [])
    .map((location) => ({
      locationSlug: location.slug,
      count: Math.max(0, Number(location.count) || 0),
    }))
    .filter((item) => item.locationSlug && item.count > 0);
  const allocated = normalized.reduce((sum, item) => sum + item.count, 0);
  if (totalCount <= 0) {
    return [];
  }
  if (!normalized.length) {
    return [{ locationSlug: defaultLocationSlug, count: totalCount }];
  }
  if (allocated === totalCount) {
    return normalized;
  }
  if (allocated < totalCount) {
    const fallbackSlug = defaultLocationSlug || normalized[0].locationSlug;
    const existing = normalized.find((item) => item.locationSlug === fallbackSlug);
    if (existing) {
      existing.count += totalCount - allocated;
    } else {
      normalized.push({ locationSlug: fallbackSlug, count: totalCount - allocated });
    }
    return normalized;
  }
  let remaining = totalCount;
  const trimmed = [];
  for (const item of normalized) {
    if (remaining <= 0) {
      break;
    }
    const count = Math.min(item.count, remaining);
    if (count > 0) {
      trimmed.push({ locationSlug: item.locationSlug, count });
      remaining -= count;
    }
  }
  return trimmed;
}

export function useManagerSetTable(getParams) {
  const accumulatedCards = ref([]);
  const cardsMeta = ref(null);
  const loadedPages = ref(0);
  const loadingCards = ref(false);
  const loadingMore = ref(false);
  const selectedRows = ref(new Set());
  const selectAllVisible = ref(false);
  let cardsLoadToken = 0;
  let defaultStorageSlug = "";

  function applyFinishCopyState(card, finish, state) {
    const count = Math.max(0, Number(state?.ownedCount) || 0);
    const locations = state?.locations || locationsForFinish(card, finish);
    if (finish === FINISH_FOIL) {
      card.ownedCountFoil = count;
      card.ownedFoil = count > 0;
      setLocationsForFinish(card, finish, locations);
      return;
    }
    if (finish === FINISH_ETCHED) {
      card.ownedCountEtched = count;
      card.ownedEtched = count > 0;
      setLocationsForFinish(card, finish, locations);
      return;
    }
    card.ownedCountNonfoil = count;
    card.ownedNonfoil = count > 0;
    setLocationsForFinish(card, finish, locations);
  }

  async function ensureDefaultStorageSlug() {
    if (defaultStorageSlug) {
      return defaultStorageSlug;
    }
    const payload = await api.listStorageLocations();
    defaultStorageSlug = payload.defaultLocation || payload.locations?.[0]?.slug || "";
    return defaultStorageSlug;
  }

  function buildFinishCard(card, setCode, finish) {
    return {
      ...card,
      setCode: card.setCode || setCode,
      finish,
      foil: finish,
    };
  }

  async function setCopyCount(setCode, card, finish, rawCount) {
    const parsed = Number.parseInt(String(rawCount ?? ""), 10);
    const nextCount = Number.isFinite(parsed)
      ? Math.max(0, Math.min(MAX_OWNED_COPIES, parsed))
      : 0;
    const previousCount = copyCountForFinish(card, finish);
    if (nextCount === previousCount) {
      return;
    }
    const locationSlug = await ensureDefaultStorageSlug();
    if (nextCount > 0 && !locationSlug) {
      throw new Error("No storage location is configured.");
    }
    const finishCard = buildFinishCard(card, setCode, finish);
    const allocations = buildAllocationsFromLocations(
      locationsForFinish(card, finish),
      nextCount,
      locationSlug,
    );
    const state = await setCardCopyAllocations(finishCard, allocations);
    applyFinishCopyState(card, finish, state);
    return state;
  }

  async function updateSingleStorage(setCode, card, finish, locationSlug) {
    if (!locationSlug) {
      throw new Error("Invalid storage assignment.");
    }
    const finishCard = buildFinishCard(card, setCode, finish);
    const payload = await fetchCardCopyState(finishCard);
    const instanceId = payload?.state?.copies?.[0]?.instanceId;
    if (!instanceId) {
      throw new Error("No owned copy found.");
    }
    const state = await updateCardCopyStorage(finishCard, instanceId, locationSlug);
    applyFinishCopyState(card, finish, state);
    return state;
  }

  async function applyStorageModalState(card, finish, state) {
    applyFinishCopyState(card, finish, state);
  }

  const visibleCards = computed(() => {
    const params = getParams();
    return sortManagerCards(accumulatedCards.value, {
      sort: params.sort,
      sortDir: params.sortDir,
      priceStrategy: params.priceStrategy,
    });
  });
  const finishRows = computed(() => expandCardFinishRows(visibleCards.value));
  const totalMatches = computed(() => cardsMeta.value?.total ?? 0);
  const totalPages = computed(() => cardsMeta.value?.totalPages ?? 1);
  const hasMoreCards = computed(() => loadedPages.value < totalPages.value);
  const artStyles = computed(() => cardsMeta.value?.artStyles || []);
  const priceIssueCount = computed(() => cardsMeta.value?.priceIssueCount ?? 0);

  const allVisibleSelected = computed({
    get() {
      const rows = finishRows.value;
      if (!rows.length) {
        return false;
      }
      return rows.every((row) => selectedRows.value.has(row.rowKey));
    },
    set(checked) {
      if (!checked) {
        clearRowSelection();
        return;
      }
      const next = new Set(selectedRows.value);
      for (const row of finishRows.value) {
        next.add(row.rowKey);
      }
      selectedRows.value = next;
      selectAllVisible.value = true;
    },
  });

  async function loadAllPages() {
    while (hasMoreCards.value) {
      const pagesBefore = loadedPages.value;
      await loadMoreCards();
      if (loadedPages.value === pagesBefore) {
        break;
      }
    }
  }

  async function selectAllRows() {
    await loadAllPages();
    const next = new Set();
    for (const row of finishRows.value) {
      next.add(row.rowKey);
    }
    selectedRows.value = next;
    selectAllVisible.value = true;
  }

  function clearRowSelection() {
    selectedRows.value = new Set();
    selectAllVisible.value = false;
  }

  function rowKey(row) {
    if (row?.rowKey) {
      return row.rowKey;
    }
    if (row?.finish != null && row?.collectorNumber != null) {
      return finishRowKey(row, row.finish);
    }
    return row?.collectorNumber || "";
  }

  function isRowSelected(row) {
    return selectedRows.value.has(rowKey(row));
  }

  function toggleRow(row) {
    const next = new Set(selectedRows.value);
    const key = rowKey(row);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    selectedRows.value = next;
  }

  function applyCardsPayload(payload, { append = false } = {}) {
    const nextCards = payload?.cards || [];
    cardsMeta.value = {
      total: payload?.total ?? 0,
      totalPages: payload?.totalPages ?? 1,
      artStyles: payload?.artStyles || cardsMeta.value?.artStyles || [],
      priceIssueCount: payload?.priceIssueCount ?? 0,
    };
    accumulatedCards.value = append
      ? [...accumulatedCards.value, ...nextCards]
      : nextCards;
    loadedPages.value = payload?.page ?? 1;
  }

  function resetTableState() {
    accumulatedCards.value = [];
    cardsMeta.value = null;
    loadedPages.value = 0;
    selectedRows.value = new Set();
    selectAllVisible.value = false;
  }

  async function loadCards() {
    const params = getParams();
    if (!params.setCode) {
      resetTableState();
      return;
    }
    const token = ++cardsLoadToken;
    loadingCards.value = true;
    try {
      const payload = await api.getManagerSetCards(params.setCode, {
        artStyle: params.artStyle,
        search: params.search,
        foilFilter: params.foilFilter,
        priceIssuesOnly: params.priceIssuesOnly,
        page: 1,
        pageSize: params.pageSize,
      });
      if (token !== cardsLoadToken) {
        return;
      }
      applyCardsPayload(payload, { append: false });
      selectedRows.value = new Set();
      selectAllVisible.value = false;
    } finally {
      if (token === cardsLoadToken) {
        loadingCards.value = false;
      }
    }
  }

  async function loadMoreCards() {
    const params = getParams();
    if (loadingMore.value || loadingCards.value || !hasMoreCards.value || !params.setCode) {
      return;
    }
    loadingMore.value = true;
    const token = cardsLoadToken;
    try {
      const payload = await api.getManagerSetCards(params.setCode, {
        artStyle: params.artStyle,
        search: params.search,
        foilFilter: params.foilFilter,
        priceIssuesOnly: params.priceIssuesOnly,
        page: loadedPages.value + 1,
        pageSize: params.pageSize,
      });
      if (token !== cardsLoadToken) {
        return;
      }
      applyCardsPayload(payload, { append: true });
    } finally {
      loadingMore.value = false;
    }
  }

  function ownedItemsForSelectedRows() {
    const items = [];
    for (const row of finishRows.value) {
      if (!selectedRows.value.has(row.rowKey)) {
        continue;
      }
      if (copyCountForFinish(row.card, row.finish) <= 0) {
        continue;
      }
      items.push({
        setCode: row.card.setCode,
        collectorNumber: row.card.collectorNumber,
        finish: row.finish,
      });
    }
    return items;
  }

  async function assignSelectedToStorage(locationSlug) {
    const items = ownedItemsForSelectedRows();
    if (!items.length) {
      window.alert("Select owned finish rows first.");
      return;
    }
    if (!locationSlug) {
      return;
    }
    const result = await api.bulkAssignStorage({
      locationSlug,
      items,
    });
    window.alert(`Moved ${result.moved} card instance(s).`);
    await loadCards();
  }

  function updateArtStyles(nextArtStyles) {
    if (!nextArtStyles?.length) {
      return;
    }
    cardsMeta.value = {
      ...(cardsMeta.value || {}),
      artStyles: nextArtStyles,
    };
  }

  return {
    accumulatedCards,
    cardsMeta,
    loadedPages,
    loadingCards,
    loadingMore,
    selectedRows,
    selectAllVisible,
    visibleCards,
    finishRows,
    totalMatches,
    totalPages,
    hasMoreCards,
    artStyles,
    priceIssueCount,
    allVisibleSelected,
    rowKey,
    isRowSelected,
    toggleRow,
    loadCards,
    loadMoreCards,
    loadAllPages,
    selectAllRows,
    clearRowSelection,
    resetTableState,
    copyCountForFinish,
    locationsForFinish,
    formatLocationsSummary,
    setCopyCount,
    updateSingleStorage,
    applyStorageModalState,
    assignSelectedToStorage,
    updateArtStyles,
  };
}
