import { formatEuro } from "./format.js";
import { galleryDisplayValue, galleryPricePair } from "./priceStrategies.js";

export const COLOR_GROUP_ORDER = ["W", "U", "B", "R", "G", "M", "C"];

export const COLOR_GROUP_LABELS = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
  M: "Multicolor",
  C: "Colorless",
};

const WUBRG = new Set(["W", "U", "B", "R", "G"]);

export const UNPRICED_KEY = "unpriced";

/** Exclusive euro bands; `max` is exclusive except when omitted (open-ended). */
export const VALUE_BANDS = [
  { key: "0-25c", label: "€0–€0.25", min: 0, max: 0.25 },
  { key: "25-50c", label: "€0.25–€0.50", min: 0.25, max: 0.5 },
  { key: "50c-1", label: "€0.50–€1", min: 0.5, max: 1 },
  { key: "1-5", label: "€1–€5", min: 1, max: 5 },
  { key: "5-10", label: "€5–€10", min: 5, max: 10 },
  { key: "10+", label: "€10+", min: 10, max: 25 },
  { key: "25+", label: "€25+", min: 25, max: 50 },
  { key: "50+", label: "€50+", min: 50, max: 100 },
  { key: "100+", label: "€100+", min: 100, max: 250 },
  { key: "250+", label: "€250+", min: 250, max: 500 },
  { key: "500+", label: "€500+", min: 500, max: null },
];

export const VALUE_GROUP_LABELS = Object.fromEntries([
  [UNPRICED_KEY, "Unpriced"],
  ...VALUE_BANDS.map((band) => [band.key, band.label]),
]);

/** Tile washes from 1€ up: green → gold → red. Under 1€ stays untinted. */
export const PRICE_TINT_BY_KEY = {
  "1-5": "#c8e6c9",
  "5-10": "#dcedc8",
  "10+": "#fff9c4",
  "25+": "#ffecb3",
  "50+": "#ffe082",
  "100+": "#ffcc80",
  "250+": "#ffab91",
  "500+": "#ef9a9a",
};

function castingPips(card) {
  const seen = [];
  for (const raw of card?.colors || []) {
    const pip = String(raw || "").toUpperCase();
    if (!WUBRG.has(pip) || seen.includes(pip)) {
      continue;
    }
    seen.push(pip);
  }
  seen.sort((left, right) => COLOR_GROUP_ORDER.indexOf(left) - COLOR_GROUP_ORDER.indexOf(right));
  return seen;
}

export function catalogColorGroupKey(card) {
  const pips = castingPips(card);
  if (!pips.length) {
    return "C";
  }
  if (pips.length >= 2) {
    return "M";
  }
  return pips[0];
}

export function catalogColorPips(key) {
  if (!key || key === "C") {
    return [];
  }
  if (key === "M") {
    return ["W", "U", "B", "R", "G"];
  }
  return [key];
}

export function catalogValueGroupKey(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return UNPRICED_KEY;
  }
  const num = Number(value);
  for (const band of VALUE_BANDS) {
    if (num < band.min) {
      return VALUE_BANDS[0].key;
    }
    if (band.max == null) {
      if (num >= band.min) {
        return band.key;
      }
      continue;
    }
    if (num >= band.min && num < band.max) {
      return band.key;
    }
  }
  return VALUE_BANDS[VALUE_BANDS.length - 1].key;
}

export function catalogValueGroupKeyForCard(card) {
  return catalogValueGroupKey(galleryDisplayValue(card));
}

export function priceTintForCard(card) {
  const key = catalogValueGroupKeyForCard(card);
  return PRICE_TINT_BY_KEY[key] || "";
}

/** Price washes are redundant when cards are already ordered or sectioned by value. */
export function shouldApplyPriceTileTint({
  enabled = false,
  sort = "",
  groupBy = [],
} = {}) {
  if (!enabled) {
    return false;
  }
  if (sort === "value") {
    return false;
  }
  const levels = Array.isArray(groupBy) ? groupBy : [groupBy];
  return !levels.some((level) => level === "value");
}

function colorGroupMeta(key) {
  return {
    key,
    label: COLOR_GROUP_LABELS[key] || key,
    groupBy: "color",
    pips: catalogColorPips(key),
  };
}

function valueGroupMeta(key) {
  return {
    key,
    label: VALUE_GROUP_LABELS[key] || key,
    groupBy: "value",
    pips: [],
  };
}

function groupKeyForCard(card, sort) {
  if (sort === "value") {
    return catalogValueGroupKeyForCard(card);
  }
  return catalogColorGroupKey(card);
}

export function sumGalleryPricePair(cards = []) {
  let low = 0;
  let high = 0;
  let pricedCount = 0;
  for (const card of cards || []) {
    const pair = galleryPricePair(card);
    if (pair.low == null) {
      continue;
    }
    pricedCount += 1;
    low += pair.low;
    high += pair.high ?? pair.low;
  }
  return {
    low: pricedCount ? low : null,
    high: pricedCount ? high : null,
    pricedCount,
  };
}

export function catalogGroupValueBandCounts(cards = []) {
  const counts = new Map();
  for (const card of cards || []) {
    const key = catalogValueGroupKeyForCard(card);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const order = [...VALUE_BANDS.map((band) => band.key), UNPRICED_KEY];
  return order
    .filter((key) => counts.get(key))
    .map((key) => ({
      key,
      label: VALUE_GROUP_LABELS[key] || key,
      count: counts.get(key),
      tint: PRICE_TINT_BY_KEY[key] || "#eceff1",
    }));
}

export function formatCatalogGroupMeta(cards = []) {
  const count = (cards || []).length;
  const countLabel = `${count} ${count === 1 ? "card" : "cards"}`;
  const { low, high, pricedCount } = sumGalleryPricePair(cards);
  if (!pricedCount) {
    return countLabel;
  }
  const valueLabel = high != null && high !== low
    ? `${formatEuro(low)} ~ ${formatEuro(high)}`
    : formatEuro(low);
  return `${countLabel} · ${valueLabel}`;
}

function shouldShowValueBands(group) {
  return group?.groupBy === "color" || group?.groupBy === "colorIdentity";
}

/** Count, gallery low~trend total, and price-band chips (color groups). */
export function attachCatalogGroupPricing(group) {
  const cards = group?.cards || [];
  const bands = shouldShowValueBands(group) ? catalogGroupValueBandCounts(cards) : [];
  return {
    ...group,
    metaText: formatCatalogGroupMeta(cards),
    valueBands: bands.length > 1 ? bands : [],
  };
}

/**
 * Insert section headers on consecutive runs. Does not reorder cards;
 * the same color or price band can appear more than once.
 */
export function groupCatalogCards(cards = [], sort = "number") {
  const metaFor = sort === "value" ? valueGroupMeta : colorGroupMeta;
  const groups = [];
  for (const card of cards || []) {
    const key = groupKeyForCard(card, sort);
    const last = groups[groups.length - 1];
    if (last && last.key === key) {
      last.cards.push(card);
      continue;
    }
    const meta = metaFor(key);
    groups.push({
      ...meta,
      path: `${meta.groupBy}:${key}:${groups.length}`,
      cards: [card],
    });
  }
  return groups.map(attachCatalogGroupPricing);
}
