import { compareCollectorNumbers } from "../composables/useManagerSetTable";
import { cardFavoriteKeyFromCard, favoriteCardKey } from "./favorites";
import { isSetBrowserHiddenSubsetType } from "./setBrowserSubsets";

export function compareCardsByCollectorNumber(left, right) {
  return compareCollectorNumbers(left?.collectorNumber, right?.collectorNumber)
    || (Number(left?.finish) || 0) - (Number(right?.finish) || 0);
}

export function artStyleMoverKey(row) {
  const setCode = String(row?.setCode || "").trim().toUpperCase();
  const artStyle = String(row?.artStyle || "").trim();
  return `${setCode}|${artStyle}`;
}

export function isCardMoverRow(row) {
  return Boolean(String(row?.collectorNumber || "").trim());
}

export function collectPriceSyncCards(payload) {
  const fromPayload = Array.isArray(payload?.cards) ? payload.cards : [];
  const cards = fromPayload.filter(isCardMoverRow);
  if (cards.length) {
    return cards;
  }
  return [];
}

export function firstPriceSyncCards(...payloads) {
  for (const payload of payloads) {
    const cards = collectPriceSyncCards(payload);
    if (cards.length) {
      return cards;
    }
    const nested = collectPriceSyncCards(payload?.lastSync);
    if (nested.length) {
      return nested;
    }
  }
  return [];
}

export function collectPriceSyncStyleRows(payload) {
  return aggregateArtStyleMovers(collectPriceSyncCards(payload));
}

export function cardsForArtStyle(cards, filter) {
  if (!filter) {
    return (cards || []).filter(isCardMoverRow);
  }
  const setCode = String(filter.setCode || "").trim().toUpperCase();
  const artStyle = String(filter.artStyle || "").trim();
  return (cards || []).filter((row) => (
    isCardMoverRow(row)
    && String(row.setCode || "").trim().toUpperCase() === setCode
    && String(row.artStyle || "").trim() === artStyle
  ));
}

export function aggregateArtStyleMovers(cards) {
  const groups = new Map();
  for (const card of cards || []) {
    const setCode = String(card.setCode || "").trim().toUpperCase();
    const artStyle = String(card.artStyle || "").trim() || "Unknown";
    const id = `${setCode}|${artStyle}`;
    const existing = groups.get(id) || {
      id,
      setCode,
      artStyle,
      label: artStyle,
      previous: 0,
      current: 0,
    };
    existing.previous += Number(card.previous) || 0;
    existing.current += Number(card.current) || 0;
    groups.set(id, existing);
  }
  return [...groups.values()].map((row) => {
    const delta = row.current - row.previous;
    return {
      ...row,
      delta,
      percent: row.previous > 0 ? (delta / row.previous) * 100 : 0,
    };
  }).filter((row) => row.delta !== 0);
}

export function deckPrintKey(card) {
  const setCode = String(card?.setCode || "").trim().toUpperCase();
  const collectorNumber = String(card?.collectorNumber || "").trim();
  const finish = Number(card?.finishId ?? card?.finish);
  if (!setCode || !collectorNumber || !Number.isFinite(finish)) {
    return "";
  }
  return `${setCode}|${collectorNumber}|${finish}`;
}

/** Sync rows for the prints a deck already owns, with owned copy counts. */
export function cardsForDeckPrints(cards, prints) {
  const wanted = new Map();
  for (const line of prints || []) {
    const key = deckPrintKey(line);
    if (!key) {
      continue;
    }
    const qty = Number(line.ownedQty);
    wanted.set(key, (wanted.get(key) || 0) + (Number.isFinite(qty) ? qty : 0));
  }
  if (!wanted.size) {
    return [];
  }
  return (cards || []).flatMap((card) => {
    const key = deckPrintKey(card);
    if (!wanted.has(key)) {
      return [];
    }
    const ownedQty = wanted.get(key);
    return [{ ...card, ownedQty: ownedQty > 0 ? ownedQty : 1 }];
  });
}

/** Price move multiplied by the copies this deck owns. */
export function deckImpactRows(cards, prints) {
  return cardsForDeckPrints(cards, prints).map((card) => {
    const qty = Math.max(1, Number(card.ownedQty) || 1);
    const raw = Number(card.delta);
    const unitDelta = Number.isFinite(raw)
      ? raw
      : (Number(card.current) || 0) - (Number(card.previous) || 0);
    return {
      ...card,
      ownedQty: qty,
      unitDelta,
      delta: unitDelta * qty,
    };
  });
}

/** How many rows rose or fell, plus the collector numbers that moved. */
export function changeMoveCounts(rows) {
  let upCount = 0;
  let downCount = 0;
  const movedSlots = new Set();
  for (const row of rows || []) {
    const delta = Number(row?.delta) || 0;
    if (delta > 0) {
      upCount += 1;
    } else if (delta < 0) {
      downCount += 1;
    } else {
      continue;
    }
    const setCode = String(row?.setCode || "").trim().toUpperCase();
    const number = String(row?.collectorNumber || "").trim();
    if (setCode && number) {
      movedSlots.add(`${setCode}|${number}`);
    }
  }
  return { upCount, downCount, movedSlots };
}

/** Owned deck prints that are not among the rows that rose or fell. */
export function deckUnchangedCount(prints, rows) {
  const moved = new Set();
  for (const row of rows || []) {
    if ((Number(row?.delta) || 0) === 0) {
      continue;
    }
    const key = deckPrintKey(row);
    if (key) {
      moved.add(key);
    }
  }
  let unchanged = 0;
  const seen = new Set();
  for (const line of prints || []) {
    const key = deckPrintKey(line);
    if (!key || seen.has(key)) {
      continue;
    }
    seen.add(key);
    if (!moved.has(key)) {
      unchanged += 1;
    }
  }
  return unchanged;
}

export function deckImpactTotals(rows) {
  let up = 0;
  let down = 0;
  for (const row of rows || []) {
    const impact = Number(row?.delta) || 0;
    if (impact > 0) {
      up += impact;
    } else if (impact < 0) {
      down += impact;
    }
  }
  return { up, down, delta: up + down };
}

export function moverRowToTileCard(row) {
  const finishLabelText = String(row?.finish || "").trim();
  const rawName = String(row?.name || "").trim();
  const label = String(row?.label || "").trim();
  const name = rawName || label.replace(/\s+\((Foil|Etched)\)$/i, "").trim();
  return {
    name,
    cardName: name,
    setCode: String(row?.setCode || "").trim().toUpperCase(),
    collectorNumber: String(row?.collectorNumber || "").trim(),
    imageUri: String(row?.imageUri || row?.image_uri || "").trim(),
    finish: finishLabelText || row?.finish,
    owned: true,
    ownedQty: 1,
  };
}

export function signedDayChange(cards) {
  let up = 0;
  let down = 0;
  let previous = 0;
  let current = 0;
  for (const card of cards || []) {
    const prev = Number(card?.previous) || 0;
    const curr = Number(card?.current) || 0;
    const rawDelta = Number(card?.delta);
    const delta = Number.isFinite(rawDelta) ? rawDelta : curr - prev;
    previous += prev;
    current += curr;
    if (delta > 0) {
      up += delta;
    } else if (delta < 0) {
      down += delta;
    }
  }
  return {
    up,
    down,
    previous,
    current,
    delta: current - previous,
  };
}

function catalogByCode(catalogSets) {
  const catalog = new Map();
  for (const item of catalogSets || []) {
    const itemCode = String(item?.setCode || "").trim().toUpperCase();
    if (itemCode && itemCode !== "ALL") {
      catalog.set(itemCode, item);
    }
  }
  return catalog;
}

export function catalogVisibleFamilyCodes(set, catalogSets, { includeHiddenSubsets = false } = {}) {
  const code = String(set?.setCode || "").trim().toUpperCase();
  const catalog = catalogByCode(catalogSets);
  const catalogMeta = catalog.get(code);
  const root = String(set?.familyRoot || catalogMeta?.familyRoot || code).trim().toUpperCase();
  const ordered = [];
  const seen = new Set();
  const push = (raw) => {
    const member = String(raw || "").trim().toUpperCase();
    if (!member || seen.has(member)) {
      return;
    }
    seen.add(member);
    ordered.push(member);
  };
  push(code);
  push(root);
  for (const raw of set?.familyMembers || []) {
    push(raw);
  }
  for (const raw of catalogMeta?.familyMembers || []) {
    push(raw);
  }
  for (const raw of catalog.get(root)?.familyMembers || []) {
    push(raw);
  }
  for (const [itemCode, item] of catalog) {
    const itemRoot = String(item?.familyRoot || itemCode).trim().toUpperCase();
    if (itemRoot === root) {
      push(itemCode);
    }
  }
  const visible = ordered.filter((member) => {
    if (catalog.size && !catalog.has(member)) {
      return false;
    }
    if (!catalog.size) {
      return member === code;
    }
    const meta = catalog.get(member);
    if (includeHiddenSubsets || member === code || member === root) {
      return true;
    }
    return !isSetBrowserHiddenSubsetType(meta?.setType);
  });
  if (visible.length) {
    return visible;
  }
  return code ? [code] : [];
}

/** Owned and catalog totals for the same visible family the day-change counts use. */
export function familySetCounts(memberCodes, catalogSets, fallback = null) {
  const catalog = catalogByCode(catalogSets);
  const codes = (memberCodes || [])
    .map((code) => String(code || "").trim().toUpperCase())
    .filter(Boolean);
  let owned = 0;
  let catalogTotal = 0;
  let found = false;
  for (const code of codes) {
    const meta = catalog.get(code);
    if (meta?.ownedCount == null || meta?.catalogCount == null) {
      continue;
    }
    found = true;
    owned += Number(meta.ownedCount) || 0;
    catalogTotal += Number(meta.catalogCount) || 0;
  }
  if (!found) {
    return {
      ownedCount: fallback?.ownedCount ?? null,
      catalogCount: fallback?.catalogCount ?? null,
    };
  }
  return { ownedCount: owned, catalogCount: catalogTotal };
}

export function favoriteSetDayRows(sets, cards, { catalogSets = [], includeHiddenSubsets = false } = {}) {
  return (sets || []).map((set) => {
    const setCode = String(set?.setCode || "").trim().toUpperCase();
    const memberCodes = catalogVisibleFamilyCodes(set, catalogSets, { includeHiddenSubsets });
    const members = new Set(memberCodes);
    const matched = (cards || []).filter((card) => (
      isCardMoverRow(card)
      && members.has(String(card.setCode || "").trim().toUpperCase())
    ));
    const change = signedDayChange(matched);
    let upCount = 0;
    let downCount = 0;
    for (const card of matched) {
      const delta = Number(card.delta);
      if (delta > 0) {
        upCount += 1;
      } else if (delta < 0) {
        downCount += 1;
      }
    }
    return {
      id: setCode,
      kind: "set",
      setCode,
      memberCodes,
      label: set?.name || set?.setName || set?.label || setCode,
      ...change,
      upCount,
      downCount,
    };
  }).filter((row) => row.setCode);
}

export function favoriteSetsDayTotal(setRows, cards) {
  const members = new Set();
  for (const row of setRows || []) {
    const codes = row.memberCodes?.length ? row.memberCodes : [row.setCode];
    for (const code of codes) {
      const normalized = String(code || "").trim().toUpperCase();
      if (normalized) {
        members.add(normalized);
      }
    }
  }
  const seen = new Set();
  const matched = [];
  for (const card of cards || []) {
    if (!isCardMoverRow(card)) {
      continue;
    }
    const code = String(card.setCode || "").trim().toUpperCase();
    if (!members.has(code)) {
      continue;
    }
    const key = `${code}|${card.collectorNumber}|${card.finish ?? card.finishId ?? ""}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    matched.push(card);
  }
  return signedDayChange(matched);
}

export function favoriteArtStyleDayRows(styles, cards) {
  return (styles || []).map((style) => {
    const matched = cardsForArtStyle(cards, style);
    const change = signedDayChange(matched);
    const setCode = String(style?.setCode || "").trim().toUpperCase();
    const artStyle = String(style?.artStyle || style?.label || "").trim();
    return {
      id: `${setCode}|${artStyle}`,
      kind: "style",
      setCode,
      artStyle,
      label: artStyle || style?.label || setCode,
      ...change,
    };
  }).filter((row) => row.setCode && row.artStyle);
}

export function favoriteCardDayRows(cards, syncCards) {
  const byKey = new Map();
  for (const card of syncCards || []) {
    const key = favoriteCardKey(
      card.setCode,
      card.collectorNumber,
      card.finishId ?? card.finish,
    );
    if (key) {
      byKey.set(key, card);
    }
  }
  return (cards || []).map((card) => {
    const key = cardFavoriteKeyFromCard(card);
    const matched = byKey.get(key) || null;
    const change = signedDayChange(matched ? [matched] : []);
    const setCode = String(card?.setCode || "").trim().toUpperCase();
    const collectorNumber = String(card?.collectorNumber || "").trim();
    const ownPrice = Number(card?.currentValue ?? card?.current_value);
    const standing = Number.isFinite(ownPrice) ? ownPrice : change.current;
    return {
      ...card,
      id: key || `${setCode}|${collectorNumber}`,
      kind: "card",
      setCode,
      collectorNumber,
      finish: card?.finish ?? matched?.finish,
      name: card?.name || card?.cardName || matched?.name || "",
      label: card?.name || card?.cardName || matched?.label || `${setCode} #${collectorNumber}`,
      imageUri: card?.imageUri || matched?.imageUri || "",
      ...change,
      current: matched ? change.current : standing,
    };
  }).filter((row) => row.setCode && row.collectorNumber);
}

function takeRankedRows(rows, { limit, minChange }) {
  const cap = Math.max(0, limit);
  if (!(minChange > 0)) {
    return rows.slice(0, cap);
  }
  const above = rows.filter((row) => Math.abs(Number(row.delta)) > minChange);
  if (above.length >= cap) {
    return above;
  }
  return rows.slice(0, cap);
}

export function priceChangeStrength(delta) {
  const amount = Math.abs(Number(delta) || 0);
  if (amount <= 0) {
    return 0;
  }
  const scaled = Math.log10(amount + 1) / Math.log10(26);
  return Math.min(1, Math.max(0.16, scaled));
}

/** Home leaves moves under this many euros on a plain tile. */
export const HOME_PRICE_TINT_FLOOR = 0.2;

export function priceChangeTinted(delta, floor = 0) {
  const amount = Math.abs(Number(delta) || 0);
  if (amount <= 0) {
    return false;
  }
  return Math.round(amount * 100) >= Math.round(Number(floor) * 100);
}

export function priceChangeStyle(delta, { floor = 0 } = {}) {
  if (!priceChangeTinted(delta, floor)) {
    return undefined;
  }
  const strength = priceChangeStrength(delta);
  if (!strength) {
    return undefined;
  }
  return { "--change-strength": strength.toFixed(2) };
}

export function rankMoverRows(rows, { scale = "absolute", limit = 25, minChange = 0 } = {}) {
  const risers = (rows || []).filter((row) => Number(row.delta) > 0);
  const fallers = (rows || []).filter((row) => Number(row.delta) < 0);
  const compare = scale === "relative"
    ? (left, right) => (
      Math.abs(right.percent) - Math.abs(left.percent)
      || Math.abs(right.delta) - Math.abs(left.delta)
    )
    : (left, right) => (
      Math.abs(right.delta) - Math.abs(left.delta)
      || Math.abs(right.percent) - Math.abs(left.percent)
    );
  risers.sort(compare);
  fallers.sort(compare);
  const options = { limit, minChange };
  return {
    risers: takeRankedRows(risers, options),
    fallers: takeRankedRows(fallers, options),
  };
}
