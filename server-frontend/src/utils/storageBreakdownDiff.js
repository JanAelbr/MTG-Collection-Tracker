import { mergeStorageBreakdownPayloads } from "./storageMerge";

function numeric(value) {
  if (value == null || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function signedDelta(saved, current) {
  const left = numeric(saved);
  const right = numeric(current);
  if (left == null && right == null) {
    return null;
  }
  return Math.round(((right || 0) - (left || 0)) * 100) / 100;
}

function printKey(card) {
  return [
    String(card?.setCode || "").toUpperCase(),
    String(card?.collectorNumber || ""),
    String(card?.finish ?? 0),
  ].join("|");
}

/**
 * Frozen snapshot locations matching the current storage selection.
 */
export function sliceSnapshotBreakdown(snapshot, slugs = []) {
  const wanted = new Set((slugs || []).map(String));
  const locations = (snapshot?.locations || []).filter((location) => (
    wanted.has(String(location.slug))
  ));
  return mergeStorageBreakdownPayloads(locations, { topSets: 10_000, topCards: 8 });
}

export function snapshotSetLookup(breakdown) {
  const map = new Map();
  for (const row of breakdown?.bySet || []) {
    const setCode = String(row.setCode || "").toUpperCase();
    if (!setCode) {
      continue;
    }
    map.set(setCode, {
      copies: Number(row.copies ?? row.count) || 0,
      current: numeric(row.current),
    });
  }
  return map;
}

export function diffBreakdownTotals(savedTotals = null, currentTotals = null) {
  const fields = ["copies", "uniquePrints", "current", "invested", "profit"];
  const result = {};
  for (const field of fields) {
    const saved = savedTotals?.[field] ?? null;
    const current = currentTotals?.[field] ?? null;
    result[field] = {
      saved,
      current,
      delta: signedDelta(saved, current),
    };
  }
  return result;
}

function indexRows(rows, keyFn) {
  const map = new Map();
  for (const row of rows || []) {
    const key = keyFn(row);
    if (!key) {
      continue;
    }
    map.set(key, row);
  }
  return map;
}

function presence(saved, current) {
  if (saved && current) {
    return "both";
  }
  if (saved) {
    return "saved-only";
  }
  return "current-only";
}

export function diffFinishRows(savedRows = [], currentRows = []) {
  const savedMap = indexRows(savedRows, (row) => String(row.id));
  const currentMap = indexRows(currentRows, (row) => String(row.id));
  const keys = new Set([...savedMap.keys(), ...currentMap.keys()]);
  return [...keys]
    .sort((left, right) => Number(left) - Number(right))
    .map((key) => {
      const saved = savedMap.get(key);
      const current = currentMap.get(key);
      const savedCopies = numeric(saved?.copies ?? saved?.count) ?? 0;
      const currentCopies = numeric(current?.copies ?? current?.count) ?? 0;
      const savedValue = numeric(saved?.current);
      const currentValue = numeric(current?.current);
      return {
        id: Number(saved?.id ?? current?.id),
        label: current?.label || saved?.label || key,
        savedCopies,
        currentCopies,
        copiesDelta: signedDelta(savedCopies, currentCopies),
        savedValue,
        currentValue,
        valueDelta: signedDelta(savedValue, currentValue),
        presence: presence(saved, current),
      };
    });
}

export function diffSetRows(savedRows = [], currentRows = []) {
  const savedMap = indexRows(savedRows, (row) => String(row.setCode || "").toUpperCase());
  const currentMap = indexRows(currentRows, (row) => String(row.setCode || "").toUpperCase());
  const keys = [...new Set([...savedMap.keys(), ...currentMap.keys()])]
    .filter(Boolean)
    .sort();
  return keys.map((setCode) => {
    const saved = savedMap.get(setCode);
    const current = currentMap.get(setCode);
    const savedCopies = numeric(saved?.copies ?? saved?.count) ?? 0;
    const currentCopies = numeric(current?.copies ?? current?.count) ?? 0;
    const savedValue = numeric(saved?.current);
    const currentValue = numeric(current?.current);
    return {
      setCode,
      label: current?.label || saved?.label || setCode,
      savedCopies,
      currentCopies,
      copiesDelta: signedDelta(savedCopies, currentCopies),
      savedValue,
      currentValue,
      valueDelta: signedDelta(savedValue, currentValue),
      presence: presence(saved, current),
    };
  });
}

export function diffTopCards(savedCards = [], currentCards = []) {
  const savedMap = indexRows(savedCards, printKey);
  const currentMap = indexRows(currentCards, printKey);
  const keys = [...new Set([...savedMap.keys(), ...currentMap.keys()])]
    .filter((key) => key && key !== "||0");
  const rows = keys.map((key) => {
    const saved = savedMap.get(key);
    const current = currentMap.get(key);
    const source = current || saved || {};
    const savedCopies = numeric(saved?.copyCount) ?? 0;
    const currentCopies = numeric(current?.copyCount) ?? 0;
    const savedValue = numeric(saved?.current);
    const currentValue = numeric(current?.current);
    return {
      key,
      name: source.name || "",
      setCode: source.setCode,
      collectorNumber: source.collectorNumber,
      finish: source.finish ?? 0,
      imageUri: source.imageUri || "",
      savedCopies,
      currentCopies,
      copiesDelta: signedDelta(savedCopies, currentCopies),
      savedValue,
      currentValue,
      valueDelta: signedDelta(savedValue, currentValue),
      presence: presence(saved, current),
    };
  }).sort((left, right) => (
    (Number(right.currentValue) || Number(right.savedValue) || 0)
    - (Number(left.currentValue) || Number(left.savedValue) || 0)
  ));

  return {
    rows,
    entered: rows.filter((row) => row.presence === "current-only"),
    left: rows.filter((row) => row.presence === "saved-only"),
  };
}

/**
 * Diff a frozen (already merged) breakdown against the live merged breakdown.
 */
export function diffStorageBreakdown(savedBreakdown, currentBreakdown) {
  return {
    totals: diffBreakdownTotals(savedBreakdown?.totals, currentBreakdown?.totals),
    byFinish: diffFinishRows(savedBreakdown?.byFinish, currentBreakdown?.byFinish),
    bySet: diffSetRows(savedBreakdown?.bySet, currentBreakdown?.bySet),
    topCards: diffTopCards(savedBreakdown?.topCards, currentBreakdown?.topCards),
  };
}
