import { COLLECTION_TYPE_ORDER } from "./collectionTypes.js";
import { POWER_COMPONENTS } from "./deckPower.js";

/** Classic MTG mana symbol palette for charts. */
export const MANA_COLOR_HEX = {
  W: "#e8d78a",
  U: "#0e68ab",
  B: "#150b00",
  R: "#d3202a",
  G: "#00733e",
  C: "#bbb5af",
  A: "#c9a227",
};

/** Rarity metal palette — matches set-gallery rarity text hues. */
export const RARITY_COLORS = {
  common: "#3d3d3d",
  uncommon: "#546e7a",
  rare: "#a67c00",
  mythic: "#d84315",
  special: "#6a1b9a",
  bonus: "#5d4037",
  unknown: "#78909c",
};

/**
 * Card-frame-inspired fills for type breakdown charts.
 * Keys align with COLLECTION_TYPE_ORDER / cardTypeGroup ids.
 */
export const CARD_TYPE_COLORS = {
  creature: "#2e7d32",
  planeswalker: "#5e35b1",
  enchantment: "#8e24aa",
  artifact: "#c9a227",
  instant: "#1565c0",
  sorcery: "#c62828",
  land: "#6d4c41",
  battle: "#ef6c00",
  kindred: "#00838f",
  tribal: "#00838f",
  other: "#607d8b",
};

/** Ordered type palette for donut colorIndex (COLLECTION_TYPE_ORDER + other). */
export const TYPE_CHART_COLORS = [
  ...COLLECTION_TYPE_ORDER.map((type) => CARD_TYPE_COLORS[type] || CARD_TYPE_COLORS.other),
  CARD_TYPE_COLORS.other,
];

/** Role colors keyed to POWER_COMPONENTS order (ramp, draw, …). */
export const ROLE_COLOR_BY_ID = {
  ramp: "#2e7d32",
  draw: "#1565c0",
  interaction: "#c62828",
  tutors: "#6a1b9a",
  fastMana: "#c9a227",
  gameChangers: "#d84315",
  comboDensity: "#00838f",
};

export const ROLE_CHART_COLORS = POWER_COMPONENTS.map(
  (component) => ROLE_COLOR_BY_ID[component.id] || "#607d8b",
);

/**
 * Mana-source stack categories — land/type flavored, high contrast.
 * Ids match MANA_SOURCE_CATEGORIES in manaPips.js.
 */
export const MANA_SOURCE_CATEGORY_COLORS = {
  basic: "#8d6e63",
  land: "#5d4037",
  creature: "#2e7d32",
  artifact: "#c9a227",
  enchantment: "#8e24aa",
  other: "#607d8b",
};

/** Collection green / gold chart accents (replaces corporate blue). */
export const CHART_ACCENT = "#1b5e20";
export const CHART_ACCENT_SOFT = "#7cb342";
export const CHART_GOLD = "#c9a227";
export const CHART_SLATE = "#94a3b8";

export function rarityColor(rarity) {
  const key = String(rarity || "unknown").toLowerCase();
  return RARITY_COLORS[key] || RARITY_COLORS.unknown;
}

export function cardTypeColor(typeId) {
  const key = String(typeId || "other").toLowerCase();
  return CARD_TYPE_COLORS[key] || CARD_TYPE_COLORS.other;
}

export function typeChartColorIndex(typeId) {
  const key = String(typeId || "").toLowerCase();
  const index = COLLECTION_TYPE_ORDER.indexOf(key);
  return index >= 0 ? index : TYPE_CHART_COLORS.length - 1;
}
