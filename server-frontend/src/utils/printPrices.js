import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  canManageFinish,
  isFinishOwnedOnCard,
} from "./finishes";

const FINISHES = [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED];
export const PRINT_PRICE_FETCH_CONCURRENCY = 2;

export function slimPrintPriceCard(card, set, { ownedOnly = true } = {}) {
  if (!card) {
    return null;
  }
  if (ownedOnly && !card.ownedNonfoil && !card.ownedFoil && !card.ownedEtched) {
    return null;
  }
  return {
    setCode: card.setCode,
    setName: set?.name || set?.label || card.setName || card.setCode,
    setIconUri: set?.iconUri || card.setIconUri || "",
    collectorNumber: card.collectorNumber,
    name: card.name,
    artStyle: card.artStyle || "",
    ownedNonfoil: Boolean(card.ownedNonfoil),
    ownedFoil: Boolean(card.ownedFoil),
    ownedEtched: Boolean(card.ownedEtched),
    hasNonfoil: Boolean(card.hasNonfoil),
    hasFoil: Boolean(card.hasFoil),
    hasEtched: Boolean(card.hasEtched),
    valuesByFinish: card.valuesByFinish || {},
  };
}

export function slimOwnedPrintPriceCard(card, set) {
  return slimPrintPriceCard(card, set, { ownedOnly: true });
}

export async function mapWithConcurrency(items, limit, mapper) {
  const list = items || [];
  if (!list.length) {
    return [];
  }
  const results = new Array(list.length);
  let next = 0;
  async function worker() {
    while (next < list.length) {
      const index = next;
      next += 1;
      results[index] = await mapper(list[index], index);
    }
  }
  const size = Math.min(Math.max(1, limit), list.length);
  await Promise.all(Array.from({ length: size }, () => worker()));
  return results;
}

function collectorSortKey(value) {
  const match = String(value ?? "").match(/^(\d+)(.*)$/);
  if (!match) {
    return [Number.MAX_SAFE_INTEGER, String(value ?? "").toLowerCase()];
  }
  return [Number(match[1]), match[2].toLowerCase()];
}

function compareCollectorNumbers(left, right) {
  const [leftNumber, leftSuffix] = collectorSortKey(left);
  const [rightNumber, rightSuffix] = collectorSortKey(right);
  return leftNumber - rightNumber || leftSuffix.localeCompare(rightSuffix);
}

function finishPrice(card, finish, strategy) {
  const prices = card?.valuesByFinish?.[String(finish)] ?? card?.valuesByFinish?.[finish];
  const price = prices?.[strategy];
  return price == null || Number.isNaN(Number(price)) ? null : Number(price);
}

export function buildPrintPriceRows(cards, {
  strategy = "trend",
  minimumPrice = null,
  ownedOnly = true,
} = {}) {
  const threshold = minimumPrice == null || minimumPrice === "" ? null : Number(minimumPrice);
  const rows = [];

  for (const card of cards || []) {
    for (const finish of FINISHES) {
      const includeFinish = ownedOnly
        ? isFinishOwnedOnCard(card, finish)
        : canManageFinish(card, finish);
      if (!includeFinish) {
        continue;
      }
      const price = finishPrice(card, finish, strategy);
      if (price == null || (threshold != null && price <= threshold)) {
        continue;
      }
      rows.push({
        id: `${card.setCode}:${card.collectorNumber}:${finish}`,
        setCode: card.setCode,
        setName: card.setName || card.setCode,
        setIconUri: card.setIconUri || "",
        artStyle: card.artStyle || "Unclassified",
        collectorNumber: card.collectorNumber,
        name: card.name,
        finish,
        price,
      });
    }
  }
  return rows;
}

export function artStyleSelectionKey(setCode, artStyle) {
  return `${setCode}:${artStyle || "Unclassified"}`;
}

export function buildArtStyleGroups(cards) {
  const bySet = new Map();
  for (const card of cards || []) {
    const setCode = card.setCode;
    const artStyle = card.artStyle || "Unclassified";
    if (!bySet.has(setCode)) {
      bySet.set(setCode, {
        setCode,
        setName: card.setName || setCode,
        styles: new Map(),
      });
    }
    const group = bySet.get(setCode);
    const key = artStyleSelectionKey(setCode, artStyle);
    if (!group.styles.has(key)) {
      group.styles.set(key, { key, artStyle });
    }
  }
  return [...bySet.values()]
    .sort((left, right) => left.setName.localeCompare(right.setName) || left.setCode.localeCompare(right.setCode))
    .map((group) => ({
      setCode: group.setCode,
      setName: group.setName,
      styles: [...group.styles.values()].sort((left, right) => left.artStyle.localeCompare(right.artStyle)),
    }));
}

export function allArtStyleKeys(groups) {
  return (groups || []).flatMap((group) => group.styles.map((style) => style.key));
}

export function previewSetStartIndexes(groups) {
  const starts = [];
  let previous = null;
  for (let index = 0; index < (groups || []).length; index += 1) {
    const setCode = groups[index].setCode;
    if (setCode !== previous) {
      starts.push(index);
      previous = setCode;
    }
  }
  return starts;
}

export function stepPreviewSetIndex(groups, currentIndex, delta) {
  const starts = previewSetStartIndexes(groups);
  if (starts.length < 2) {
    return currentIndex;
  }
  const currentSet = groups[currentIndex]?.setCode;
  let setIndex = starts.findIndex((start) => groups[start].setCode === currentSet);
  if (setIndex < 0) {
    setIndex = 0;
  }
  const next = (setIndex + delta + starts.length) % starts.length;
  return starts[next];
}

export function groupPrintPriceRows(rows, sort = "collector") {
  const groups = new Map();
  for (const row of rows || []) {
    const key = `${row.setCode}:${row.artStyle}`;
    if (!groups.has(key)) {
      groups.set(key, {
        id: key,
        setCode: row.setCode,
        setName: row.setName,
        setIconUri: row.setIconUri || "",
        artStyle: row.artStyle,
        rows: [],
      });
    }
    groups.get(key).rows.push(row);
  }

  return [...groups.values()]
    .sort((left, right) =>
      left.setName.localeCompare(right.setName) || left.artStyle.localeCompare(right.artStyle),
    )
    .map((group) => ({
      ...group,
      rows: group.rows.sort((left, right) => {
        if (sort === "price") {
          return right.price - left.price || compareCollectorNumbers(left.collectorNumber, right.collectorNumber);
        }
        return compareCollectorNumbers(left.collectorNumber, right.collectorNumber)
          || left.finish - right.finish;
      }),
    }));
}
