import { compareCollectorNumbers } from "../composables/useManagerSetTable.js";
import { COLLECTION_RARITY_ORDER } from "./collectionRarities.js";
import { parseNumericStat } from "./collectionFilters.js";
import { compareGroupKeys } from "./searchResults.js";

export const COLLECTION_SORT_FIELDS = new Set([
  "number",
  "value",
  "name",
  "artStyle",
  "set",
  "finish",
  "copies",
  "cmc",
  "rarity",
  "power",
  "toughness",
]);

export function defaultCollectionSortDir(sort) {
  if (
    sort === "number"
    || sort === "set"
    || sort === "name"
    || sort === "finish"
    || sort === "artStyle"
    || sort === "cmc"
    || sort === "rarity"
  ) {
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

export function compareCollectionCards(left, right, { sort = "value", dir = "desc", allowSet = false } = {}) {
  const normalizedSort = normalizeCollectionSort(sort, { allowSet });
  const ascending = normalizeCollectionSortDir(normalizedSort, dir, { allowSet }) === "asc";
  let primary = 0;
  if (normalizedSort === "value") {
    const leftValue = left?.currentValue ?? Number.NEGATIVE_INFINITY;
    const rightValue = right?.currentValue ?? Number.NEGATIVE_INFINITY;
    primary = ascending ? leftValue - rightValue : rightValue - leftValue;
  } else if (normalizedSort === "name") {
    primary = String(left?.name || "").localeCompare(String(right?.name || ""), undefined, {
      sensitivity: "base",
    });
    if (primary !== 0) {
      return ascending ? primary : -primary;
    }
    return compareCollectionCardTieBreak(left, right);
  } else if (normalizedSort === "artStyle") {
    primary = String(left?.artStyle || "").localeCompare(String(right?.artStyle || ""), undefined, {
      sensitivity: "base",
    });
    if (primary !== 0) {
      return ascending ? primary : -primary;
    }
    return compareCollectionCardTieBreak(left, right);
  } else if (normalizedSort === "set") {
    primary = String(left?.setCode || "").localeCompare(String(right?.setCode || ""), undefined, {
      sensitivity: "base",
    });
    if (primary !== 0) {
      return ascending ? primary : -primary;
    }
    const numberOrder = compareCollectorNumbers(left?.collectorNumber, right?.collectorNumber);
    if (numberOrder !== 0) {
      return ascending ? numberOrder : -numberOrder;
    }
    return (left?.finish ?? left?.foil ?? 0) - (right?.finish ?? right?.foil ?? 0);
  } else if (normalizedSort === "finish") {
    primary = (left?.finish ?? left?.foil ?? 0) - (right?.finish ?? right?.foil ?? 0);
    if (primary !== 0) {
      return ascending ? primary : -primary;
    }
    return compareCollectionCardTieBreak(left, right);
  } else if (normalizedSort === "copies") {
    const leftCopies = Number(left?.copyCount ?? left?.ownedQty ?? 0);
    const rightCopies = Number(right?.copyCount ?? right?.ownedQty ?? 0);
    primary = ascending ? leftCopies - rightCopies : rightCopies - leftCopies;
  } else if (normalizedSort === "cmc") {
    const leftCmc = Number(left?.cmc);
    const rightCmc = Number(right?.cmc);
    const leftMissing = !Number.isFinite(leftCmc);
    const rightMissing = !Number.isFinite(rightCmc);
    if (leftMissing || rightMissing) {
      if (leftMissing && rightMissing) {
        primary = 0;
      } else {
        primary = leftMissing ? 1 : -1;
      }
    } else {
      primary = ascending ? leftCmc - rightCmc : rightCmc - leftCmc;
    }
  } else if (normalizedSort === "rarity") {
    const leftRank = COLLECTION_RARITY_ORDER.indexOf(
      String(left?.rarity || "").trim().toLowerCase(),
    );
    const rightRank = COLLECTION_RARITY_ORDER.indexOf(
      String(right?.rarity || "").trim().toLowerCase(),
    );
    const leftValue = leftRank === -1 ? 99 : leftRank;
    const rightValue = rightRank === -1 ? 99 : rightRank;
    primary = ascending ? leftValue - rightValue : rightValue - leftValue;
  } else if (normalizedSort === "power" || normalizedSort === "toughness") {
    const leftStat = parseNumericStat(left?.[normalizedSort]);
    const rightStat = parseNumericStat(right?.[normalizedSort]);
    if (leftStat == null || rightStat == null) {
      if (leftStat == null && rightStat == null) {
        primary = 0;
      } else {
        primary = leftStat == null ? 1 : -1;
      }
    } else {
      primary = ascending ? leftStat - rightStat : rightStat - leftStat;
    }
  } else {
    primary = compareCollectorNumbers(left?.collectorNumber, right?.collectorNumber);
    if (primary !== 0) {
      return ascending ? primary : -primary;
    }
    return (left?.finish ?? left?.foil ?? 0) - (right?.finish ?? right?.foil ?? 0);
  }
  if (primary !== 0) {
    return primary;
  }
  return compareCollectionCardTieBreak(left, right);
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
  return [...(cards || [])].sort((left, right) =>
    compareCollectionCards(left, right, { sort, dir, allowSet }),
  );
}

const EMPTY_GROUP_KEYS = new Set(["__none__", "unpriced"]);

function isEmptyGroupKey(key) {
  return EMPTY_GROUP_KEYS.has(String(key || ""));
}

function groupCopyCount(group) {
  if (Number.isFinite(Number(group?.copyCount))) {
    return Number(group.copyCount);
  }
  let copies = 0;
  for (const card of group?.cards || []) {
    copies += Number(card.copyCount ?? card.ownedQty ?? 0);
  }
  return copies;
}

function groupTotalValue(group) {
  if (group?.totalValue != null && Number.isFinite(Number(group.totalValue))) {
    return Number(group.totalValue);
  }
  let total = 0;
  let priced = false;
  for (const card of group?.cards || []) {
    if (card?.currentValue == null || Number.isNaN(Number(card.currentValue))) {
      continue;
    }
    const copies = Number(card.copyCount ?? card.ownedQty ?? 1) || 1;
    total += Number(card.currentValue) * copies;
    priced = true;
  }
  return priced ? total : null;
}

function groupRepresentativeCard(group) {
  if (group?.groups?.length) {
    return groupRepresentativeCard(group.groups[0]);
  }
  return group?.cards?.[0] || null;
}

function compareNullableNumbers(left, right, ascending) {
  const leftMissing = left == null || !Number.isFinite(Number(left));
  const rightMissing = right == null || !Number.isFinite(Number(right));
  if (leftMissing || rightMissing) {
    if (leftMissing && rightMissing) {
      return 0;
    }
    return leftMissing ? 1 : -1;
  }
  const delta = Number(left) - Number(right);
  return ascending ? delta : -delta;
}

function compareGroupsByCanonicalKey(left, right, ascending) {
  const leftEmpty = isEmptyGroupKey(left?.key);
  const rightEmpty = isEmptyGroupKey(right?.key);
  if (leftEmpty || rightEmpty) {
    if (leftEmpty && rightEmpty) {
      return 0;
    }
    return leftEmpty ? 1 : -1;
  }
  const cmp = compareGroupKeys(left?.groupBy, left?.key, right?.key);
  return ascending ? cmp : -cmp;
}

function compareCollectionCardGroups(left, right, { sort = "value", dir = "desc", allowSet = true } = {}) {
  if (typeof sort !== "string" || !COLLECTION_SORT_FIELDS.has(sort)) {
    return compareGroupKeys(left?.groupBy, left?.key, right?.key);
  }

  const normalizedSort = normalizeCollectionSort(sort, { allowSet });
  const ascending = normalizeCollectionSortDir(normalizedSort, dir, { allowSet }) === "asc";
  const groupBy = left?.groupBy || right?.groupBy;

  if (normalizedSort === groupBy) {
    return compareGroupsByCanonicalKey(left, right, ascending);
  }
  if (normalizedSort === "value") {
    return compareNullableNumbers(groupTotalValue(left), groupTotalValue(right), ascending);
  }
  if (normalizedSort === "copies") {
    return compareNullableNumbers(groupCopyCount(left), groupCopyCount(right), ascending);
  }
  if (normalizedSort === "name") {
    const cmp = String(left?.label || left?.key || "").localeCompare(
      String(right?.label || right?.key || ""),
      undefined,
      { sensitivity: "base" },
    );
    return ascending ? cmp : -cmp;
  }

  const leftCard = groupRepresentativeCard(left);
  const rightCard = groupRepresentativeCard(right);
  if (!leftCard || !rightCard) {
    if (!leftCard && !rightCard) {
      return 0;
    }
    return leftCard ? -1 : 1;
  }
  return compareCollectionCards(leftCard, rightCard, { sort: normalizedSort, dir, allowSet });
}

/**
 * Sort a group tree with the same field/direction as cards. Nested groups are
 * sorted first. Value and copies use group totals; matching group-by fields
 * keep their canonical order (reversed when descending). Other fields use the
 * leading card in each group after its own sort.
 */
export function sortCollectionCardGroups(groups = [], options = {}) {
  const nested = (groups || []).map((group) => ({
    ...group,
    groups: group?.groups?.length
      ? sortCollectionCardGroups(group.groups, options)
      : (group?.groups || []),
  }));
  return nested.sort((left, right) => compareCollectionCardGroups(left, right, options));
}

/**
 * Partition cards into set groups. Cards within each group are sorted with
 * `sortCollectionCards`. Groups follow the same sort field and direction.
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
    key: setCode,
    setCode,
    label: setCode,
    groupBy: "set",
    cards: sortCollectionCards(groupCards, { sort, dir, allowSet }),
    groups: [],
  }));

  return sortCollectionCardGroups(groups, { sort, dir, allowSet });
}
