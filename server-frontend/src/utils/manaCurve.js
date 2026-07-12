export const MANA_CURVE_BUCKETS = [
  { id: 0, label: "0" },
  { id: 1, label: "1" },
  { id: 2, label: "2" },
  { id: 3, label: "3" },
  { id: 4, label: "4" },
  { id: 5, label: "5" },
  { id: 6, label: "6" },
  { id: 7, label: "7+" },
];

/** Typical Commander nonland spell distribution (sums to 1). */
export const IDEAL_MANA_CURVE_PERCENT = {
  0: 0.03,
  1: 0.11,
  2: 0.19,
  3: 0.16,
  4: 0.13,
  5: 0.09,
  6: 0.06,
  7: 0.23,
};

export function cmcToBucket(cmc) {
  const value = Math.floor(Number(cmc) || 0);
  if (value >= 7) {
    return 7;
  }
  return Math.max(0, value);
}

export function manaBucketLabel(bucketId) {
  const bucket = MANA_CURVE_BUCKETS.find((item) => item.id === bucketId);
  return bucket ? `CMC ${bucket.label}` : `CMC ${bucketId}`;
}

export function cardMatchesManaBucket(card, bucketId) {
  const cmc = Number(card?.cmc);
  if (!Number.isFinite(cmc) || cmc <= 0) {
    return false;
  }
  return cmcToBucket(cmc) === bucketId;
}

export function filterCardsByManaBucket(cards = [], bucketId) {
  return cards
    .filter((card) => cardMatchesManaBucket(card, bucketId))
    .sort((left, right) => String(left?.cardName || "").localeCompare(String(right?.cardName || "")));
}

export function buildManaCurveChartData(cards = []) {
  const counts = Object.fromEntries(MANA_CURVE_BUCKETS.map((bucket) => [bucket.id, 0]));
  const cmcValues = [];
  let total = 0;

  for (const card of cards) {
    const cmc = Number(card?.cmc);
    if (!Number.isFinite(cmc) || cmc <= 0) {
      continue;
    }
    const qty = Math.max(1, Number(card?.qty) || 1);
    const bucket = cmcToBucket(cmc);
    counts[bucket] += qty;
    total += qty;
    for (let index = 0; index < qty; index += 1) {
      cmcValues.push(cmc);
    }
  }

  const maxCount = Math.max(
    1,
    ...MANA_CURVE_BUCKETS.map((bucket) => counts[bucket.id]),
    ...MANA_CURVE_BUCKETS.map((bucket) => (
      total > 0 ? Math.round(IDEAL_MANA_CURVE_PERCENT[bucket.id] * total) : 0
    )),
  );

  const buckets = MANA_CURVE_BUCKETS.map((bucket) => {
    const actual = counts[bucket.id];
    const ideal = total > 0
      ? Number((IDEAL_MANA_CURVE_PERCENT[bucket.id] * total).toFixed(1))
      : Number((IDEAL_MANA_CURVE_PERCENT[bucket.id] * 100).toFixed(1));
    const actualPercent = total > 0 ? Math.round((actual / total) * 100) : 0;
    const idealPercent = Math.round(IDEAL_MANA_CURVE_PERCENT[bucket.id] * 100);
    return {
      id: bucket.id,
      label: bucket.label,
      actual,
      ideal,
      actualPercent,
      idealPercent,
    };
  });

  const averageCmc = cmcValues.length
    ? Math.round((cmcValues.reduce((sum, value) => sum + value, 0) / cmcValues.length) * 10) / 10
    : null;

  return {
    buckets,
    total,
    maxCount,
    averageCmc,
    hasData: total > 0,
  };
}
