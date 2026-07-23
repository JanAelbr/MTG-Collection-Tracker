import { COLLECTION_TYPE_LABELS, COLLECTION_TYPE_ORDER } from "./collectionTypes";
import { cardTypeGroup, countDeckCards, deckTypeCounts, deckTypeLabel } from "./deckCards";
import { POWER_COMPONENTS } from "./deckPower";
import { HERO_TOP_CARD_COUNT, getTopValueCards } from "./deckBrowse";
import {
  ROLE_CHART_COLORS,
  TYPE_CHART_COLORS,
  typeChartColorIndex,
} from "./mtgTheme.js";

export const OVERVIEW_TOP_CARD_LIMIT = HERO_TOP_CARD_COUNT;

export { TYPE_CHART_COLORS, ROLE_CHART_COLORS };

export function mainDeckCardsForOverview(cards = []) {
  return (cards || []).filter((card) => String(card.section || "main") !== "commander");
}

export function buildTypeBreakdown(cards = []) {
  const pool = mainDeckCardsForOverview(cards);
  const counts = deckTypeCounts(pool);
  const total = countDeckCards(pool);
  const rows = [];
  for (const type of COLLECTION_TYPE_ORDER) {
    const count = counts.get(type) || 0;
    if (!count) {
      continue;
    }
    rows.push({
      id: type,
      label: COLLECTION_TYPE_LABELS[type] || deckTypeLabel(type),
      count,
      share: total ? count / total : 0,
      colorIndex: typeChartColorIndex(type),
    });
  }
  for (const [type, count] of counts) {
    if (COLLECTION_TYPE_ORDER.includes(type) || !count) {
      continue;
    }
    rows.push({
      id: type,
      label: deckTypeLabel(type),
      count,
      share: total ? count / total : 0,
      colorIndex: TYPE_CHART_COLORS.length - 1,
    });
  }
  return { total, rows };
}

export function buildRoleBreakdown(counts = {}) {
  const rows = [];
  let total = 0;
  POWER_COMPONENTS.forEach((component, index) => {
    if (component.showCount === false) {
      return;
    }
    const count = Number(counts[component.id]) || 0;
    if (count <= 0) {
      return;
    }
    total += count;
    rows.push({
      id: component.id,
      label: component.label,
      count,
      colorIndex: index,
    });
  });
  return {
    total,
    rows: rows.map((row) => ({
      ...row,
      share: total ? row.count / total : 0,
    })),
  };
}

export function overviewTopCards(cards = [], limit = OVERVIEW_TOP_CARD_LIMIT) {
  return getTopValueCards(cards, limit, true);
}

/** Main-deck cards matching a type breakdown row id. */
export function filterCardsByType(cards = [], typeId) {
  const normalized = String(typeId || "").toLowerCase();
  if (!normalized) {
    return [];
  }
  return mainDeckCardsForOverview(cards).filter(
    (card) => cardTypeGroup(card) === normalized,
  );
}

/** Build SVG donut path segments for breakdown rows. */
export function buildDonutSegments(rows = [], { radius = 54, stroke = 18 } = {}) {
  const total = rows.reduce((sum, row) => sum + (Number(row.count) || 0), 0);
  if (!total) {
    return [];
  }
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return rows.map((row, index) => {
    const value = Number(row.count) || 0;
    const length = (value / total) * circumference;
    const segment = {
      id: row.id,
      label: row.label,
      count: value,
      share: value / total,
      colorIndex: row.colorIndex ?? index,
      radius,
      stroke,
      circumference,
      dasharray: `${length} ${circumference - length}`,
      dashoffset: -offset,
    };
    offset += length;
    return segment;
  });
}
