import { isEffectivelyOwned } from "../composables/cardContextMenu";

export function computeCollectionScopeStats(cards = []) {
  let ownedCount = 0;
  let ownedValue = 0;
  let missingValue = 0;

  for (const card of cards) {
    const value = Number(card.currentValue) || 0;
    if (isEffectivelyOwned(card)) {
      ownedCount += 1;
      ownedValue += value;
    } else {
      missingValue += value;
    }
  }

  const totalCount = cards.length;
  const missingCount = totalCount - ownedCount;
  const completionPct = totalCount ? (ownedCount / totalCount) * 100 : 0;

  return {
    totalCount,
    ownedCount,
    missingCount,
    ownedValue,
    missingValue,
    completionPct,
  };
}

export function cardSelectionKey(card) {
  return `${card.setCode}|${card.collectorNumber}|${card.finish ?? card.foil ?? 0}`;
}
