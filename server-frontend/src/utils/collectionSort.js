import { compareCollectorNumbers } from "../composables/useManagerSetTable.js";

export const COLLECTION_SORT_FIELDS = new Set([
  "number",
  "value",
  "name",
  "artStyle",
  "set",
  "finish",
  "copies",
]);

export function defaultCollectionSortDir(sort) {
  if (sort === "number" || sort === "set" || sort === "name" || sort === "finish" || sort === "artStyle") {
    return "asc";
  }
  return "desc";
}

export function normalizeCollectionSort(sort, { allowSet = false } = {}) {
  if (typeof sort !== "string") {
    return "value";
  }
  if (sort === "set" && !allowSet) {
    return "value";
  }
  return COLLECTION_SORT_FIELDS.has(sort) ? sort : "value";
}

export function normalizeCollectionSortDir(sort, dir, options = {}) {
  const normalizedSort = normalizeCollectionSort(sort, options);
  if (dir === "asc" || dir === "desc") {
    return dir;
  }
  return defaultCollectionSortDir(normalizedSort);
}

export function compareCollectionCardTieBreak(left, right) {
  const setOrder = String(left?.setCode || "").localeCompare(
    String(right?.setCode || ""),
    undefined,
    { sensitivity: "base" },
  );
  if (setOrder !== 0) {
    return setOrder;
  }
  const numberOrder = compareCollectorNumbers(left?.collectorNumber, right?.collectorNumber);
  if (numberOrder !== 0) {
    return numberOrder;
  }
  return (left?.finish ?? left?.foil ?? 0) - (right?.finish ?? right?.foil ?? 0);
}

/**
 * Sort a copy of `cards` by collection/storage sort fields.
 * @param {Array} cards
 * @param {{ sort?: string, dir?: string, allowSet?: boolean }} options
 */
export function sortCollectionCards(cards = [], { sort = "value", dir = "desc", allowSet = false } = {}) {
  const normalizedSort = normalizeCollectionSort(sort, { allowSet });
  const ascending = normalizeCollectionSortDir(normalizedSort, dir, { allowSet }) === "asc";
  const list = [...(cards || [])];

  return list.sort((left, right) => {
    let primary = 0;
    if (normalizedSort === "value") {
      const leftValue = left.currentValue ?? Number.NEGATIVE_INFINITY;
      const rightValue = right.currentValue ?? Number.NEGATIVE_INFINITY;
      primary = ascending ? leftValue - rightValue : rightValue - leftValue;
    } else if (normalizedSort === "name") {
      primary = String(left.name || "").localeCompare(String(right.name || ""), undefined, {
        sensitivity: "base",
      });
      if (primary !== 0) {
        return ascending ? primary : -primary;
      }
      return compareCollectionCardTieBreak(left, right);
    } else if (normalizedSort === "artStyle") {
      primary = String(left.artStyle || "").localeCompare(String(right.artStyle || ""), undefined, {
        sensitivity: "base",
      });
      if (primary !== 0) {
        return ascending ? primary : -primary;
      }
      return compareCollectionCardTieBreak(left, right);
    } else if (normalizedSort === "set") {
      primary = String(left.setCode || "").localeCompare(String(right.setCode || ""), undefined, {
        sensitivity: "base",
      });
      if (primary !== 0) {
        return ascending ? primary : -primary;
      }
      const numberOrder = compareCollectorNumbers(left.collectorNumber, right.collectorNumber);
      if (numberOrder !== 0) {
        return ascending ? numberOrder : -numberOrder;
      }
      return (left.finish ?? left.foil ?? 0) - (right.finish ?? right.foil ?? 0);
    } else if (normalizedSort === "finish") {
      primary = (left.finish ?? left.foil ?? 0) - (right.finish ?? right.foil ?? 0);
      if (primary !== 0) {
        return ascending ? primary : -primary;
      }
      return compareCollectionCardTieBreak(left, right);
    } else if (normalizedSort === "copies") {
      const leftCopies = Number(left.copyCount ?? left.ownedQty ?? 0);
      const rightCopies = Number(right.copyCount ?? right.ownedQty ?? 0);
      primary = ascending ? leftCopies - rightCopies : rightCopies - leftCopies;
    } else {
      primary = compareCollectorNumbers(left.collectorNumber, right.collectorNumber);
      if (primary !== 0) {
        return ascending ? primary : -primary;
      }
      return (left.finish ?? left.foil ?? 0) - (right.finish ?? right.foil ?? 0);
    }
    if (primary !== 0) {
      return primary;
    }
    return compareCollectionCardTieBreak(left, right);
  });
}

/**
 * Partition cards into set groups. Cards within each group are sorted with
 * `sortCollectionCards`. Groups are ordered by set code (respecting sort dir
 * when sorting by set), otherwise alphabetically by set code.
 */
export function groupCollectionCardsBySet(
  cards = [],
  { sort = "value", dir = "desc", allowSet = true } = {},
) {
  const buckets = new Map();
  for (const card of cards || []) {
    const code = String(card?.setCode || "").trim().toUpperCase() || "—";
    if (!buckets.has(code)) {
      buckets.set(code, []);
    }
    buckets.get(code).push(card);
  }

  const groups = [...buckets.entries()].map(([setCode, groupCards]) => ({
    setCode,
    cards: sortCollectionCards(groupCards, { sort, dir, allowSet }),
  }));

  const ascending =
    normalizeCollectionSortDir(normalizeCollectionSort(sort, { allowSet }), dir, { allowSet }) ===
    "asc";

  groups.sort((left, right) => {
    const cmp = left.setCode.localeCompare(right.setCode, undefined, { sensitivity: "base" });
    if (normalizeCollectionSort(sort, { allowSet }) === "set") {
      return ascending ? cmp : -cmp;
    }
    return cmp;
  });

  return groups;
}
