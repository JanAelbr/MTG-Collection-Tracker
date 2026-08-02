/**
 * Merge card payloads from several storage locations into one gallery scope.
 * Same print (set + number + finish) combines copy counts and instance ids.
 */
export function mergeStorageCardPayloads(payloads = []) {
  const list = (payloads || []).filter(Boolean);
  if (!list.length) {
    return {
      location: null,
      cards: [],
      totalCopies: 0,
      uniquePrints: 0,
    };
  }
  if (list.length === 1) {
    return list[0];
  }

  const byKey = new Map();
  let totalCopies = 0;

  for (const payload of list) {
    totalCopies += Number(payload.totalCopies) || 0;
    for (const card of payload.cards || []) {
      const key = [
        String(card.setCode || "").toUpperCase(),
        String(card.collectorNumber || ""),
        String(card.finish ?? card.foil ?? 0),
      ].join("|");
      const existing = byKey.get(key);
      if (!existing) {
        byKey.set(key, {
          ...card,
          copyCount: Number(card.copyCount) || 0,
          instanceIds: [...(card.instanceIds || [])],
        });
        continue;
      }
      existing.copyCount += Number(card.copyCount) || 0;
      existing.instanceIds.push(...(card.instanceIds || []));
      if (card.forSale) {
        existing.forSale = true;
        const ask = card.listingPrice;
        if (
          ask != null
          && (existing.listingPrice == null || ask < existing.listingPrice)
        ) {
          existing.listingPrice = ask;
          existing.listingId = card.listingId;
          existing.listedInstanceId = card.listedInstanceId;
        }
      }
    }
  }

  return {
    location: null,
    cards: [...byKey.values()],
    totalCopies,
    uniquePrints: byKey.size,
  };
}

function mergeNumeric(left, right) {
  if (left == null && right == null) {
    return null;
  }
  return (Number(left) || 0) + (Number(right) || 0);
}

/**
 * Merge breakdown payloads so multi-location analytics still work.
 */
export function mergeStorageBreakdownPayloads(payloads = [], { topCards = 8, topSets = 8 } = {}) {
  const list = (payloads || []).filter(Boolean);
  if (!list.length) {
    return null;
  }
  if (list.length === 1) {
    return list[0];
  }

  const totals = {
    copies: 0,
    uniquePrints: 0,
    current: null,
    invested: null,
    profit: null,
    pricedCopies: 0,
    unpricedCopies: 0,
  };
  const byFinish = new Map();
  const bySet = new Map();
  const byPrint = new Map();

  for (const payload of list) {
    const t = payload.totals || {};
    totals.copies += Number(t.copies) || 0;
    totals.pricedCopies += Number(t.pricedCopies) || 0;
    totals.unpricedCopies += Number(t.unpricedCopies) || 0;
    totals.current = mergeNumeric(totals.current, t.current);
    totals.invested = mergeNumeric(totals.invested, t.invested);

    for (const row of payload.byFinish || []) {
      const id = Number(row.id);
      const existing = byFinish.get(id) || {
        id,
        label: row.label,
        count: 0,
        copies: 0,
        current: 0,
      };
      existing.count += Number(row.copies ?? row.count) || 0;
      existing.copies += Number(row.copies ?? row.count) || 0;
      existing.current += Number(row.current) || 0;
      byFinish.set(id, existing);
    }

    for (const row of payload.bySet || []) {
      const code = String(row.setCode || "").toUpperCase();
      if (!code) {
        continue;
      }
      const existing = bySet.get(code) || {
        id: code,
        setCode: code,
        label: row.label || code,
        count: 0,
        copies: 0,
        uniquePrints: 0,
        current: 0,
      };
      existing.count += Number(row.copies ?? row.count) || 0;
      existing.copies += Number(row.copies ?? row.count) || 0;
      existing.uniquePrints += Number(row.uniquePrints) || 0;
      existing.current += Number(row.current) || 0;
      bySet.set(code, existing);
    }

    for (const row of payload.topCards || []) {
      const key = [
        String(row.setCode || "").toUpperCase(),
        String(row.collectorNumber || ""),
        String(row.finish ?? 0),
      ].join("|");
      const existing = byPrint.get(key);
      if (!existing) {
        byPrint.set(key, {
          ...row,
          copyCount: Number(row.copyCount) || 0,
          current: Number(row.current) || 0,
        });
        continue;
      }
      existing.copyCount += Number(row.copyCount) || 0;
      existing.current += Number(row.current) || 0;
    }
  }

  totals.uniquePrints = byPrint.size || list.reduce(
    (sum, payload) => sum + (Number(payload.totals?.uniquePrints) || 0),
    0,
  );
  if (totals.current != null && totals.invested != null && totals.pricedCopies && list.some((p) => p.totals?.invested != null)) {
    totals.profit = Math.round((totals.current - totals.invested) * 100) / 100;
  } else {
    totals.profit = null;
  }
  if (totals.current != null) {
    totals.current = Math.round(totals.current * 100) / 100;
  }
  if (totals.invested != null) {
    totals.invested = Math.round(totals.invested * 100) / 100;
  }

  const finishRows = [...byFinish.values()]
    .filter((row) => row.copies > 0)
    .sort((left, right) => left.id - right.id)
    .map((row) => ({
      ...row,
      current: Math.round(row.current * 100) / 100,
      share: totals.copies ? row.copies / totals.copies : 0,
    }));

  const setRows = [...bySet.values()]
    .filter((row) => row.copies > 0)
    .map((row) => ({
      ...row,
      current: Math.round(row.current * 100) / 100,
      share: totals.copies ? row.copies / totals.copies : 0,
      valueShare: totals.current ? row.current / totals.current : 0,
    }))
    .sort((left, right) => (
      right.current - left.current
      || right.copies - left.copies
      || left.setCode.localeCompare(right.setCode)
    ))
    .slice(0, topSets);

  const topCardRows = [...byPrint.values()]
    .map((row) => ({
      ...row,
      current: Math.round(row.current * 100) / 100,
    }))
    .sort((left, right) => (
      right.current - left.current
      || right.copyCount - left.copyCount
      || String(left.name || "").localeCompare(String(right.name || ""))
    ))
    .slice(0, topCards);

  return {
    location: null,
    totals,
    byFinish: finishRows,
    bySet: setRows,
    topCards: topCardRows,
  };
}
