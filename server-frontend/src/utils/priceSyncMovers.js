import { cardFavoriteKeyFromCard, favoriteCardKey } from "./favorites";
import { isSetBrowserHiddenSubsetType } from "./setBrowserSubsets";

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
    return {
      id: setCode,
      kind: "set",
      setCode,
      memberCodes,
      label: set?.name || set?.setName || set?.label || setCode,
      ...change,
    };
  }).filter((row) => row.setCode);
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
    return {
      id: key || `${setCode}|${collectorNumber}`,
      kind: "card",
      setCode,
      collectorNumber,
      finish: card?.finish ?? matched?.finish,
      name: card?.name || card?.cardName || matched?.name || "",
      label: card?.name || card?.cardName || matched?.label || `${setCode} #${collectorNumber}`,
      imageUri: card?.imageUri || matched?.imageUri || "",
      ...change,
    };
  }).filter((row) => row.setCode && row.collectorNumber);
}

export function rankMoverRows(rows, { scale = "absolute", limit = 25 } = {}) {
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
  return {
    risers: risers.slice(0, Math.max(0, limit)),
    fallers: fallers.slice(0, Math.max(0, limit)),
  };
}
