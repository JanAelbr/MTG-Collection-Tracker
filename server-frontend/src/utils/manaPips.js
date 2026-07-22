import { parseManaCostSymbols } from "./deckStackStyles.js";
import { mainDeckCardsForOverview } from "./deckOverview.js";

/** Chromatic colors only — any-color sources count toward these. */
export const CHROMATIC_COLORS = ["W", "U", "B", "R", "G"];

/** Pip / source colors including colorless. */
export const MANA_COLORS = [...CHROMATIC_COLORS, "C"];

export const MANA_COLOR_LABELS = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
  C: "Colorless",
  A: "Any",
};

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

export const PIP_CHART_COLORS = MANA_COLORS.map((color) => MANA_COLOR_HEX[color]);

/** Stacked mana-source categories (bottom → top). */
export const MANA_SOURCE_CATEGORIES = [
  { id: "basic", label: "Basic lands" },
  { id: "land", label: "Other lands" },
  { id: "creature", label: "Creatures" },
  { id: "artifact", label: "Artifacts" },
  { id: "enchantment", label: "Enchantments" },
  { id: "other", label: "Other" },
];

export const MANA_SOURCE_CATEGORY_COLORS = {
  basic: "#94a3b8",
  land: "#0f766e",
  creature: "#2563eb",
  artifact: "#d97706",
  enchantment: "#7c3aed",
  other: "#475569",
};

const BASIC_LAND_TYPES = {
  plains: "W",
  island: "U",
  swamp: "B",
  mountain: "R",
  forest: "G",
};

const ANY_COLOR_PHRASE = /mana of any(?:\s+one)?\s+colou?r|mana of any type|mana in any combination of colou?rs|one mana of a colou?r|mana of a colou?r of your choice/i;
const ADD_CLAUSE = /(?:\{t\}:\s*)?add\b([^.;\n]*)/gi;
const MANA_SYMBOL = /\{([wubrgc](?:\/[wubrgcp2])?|\d+\/[wubrg]|[wubrg]\/p)\}/gi;

function emptyColorCounts() {
  return { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
}

function emptyCategoryCounts() {
  return Object.fromEntries(MANA_SOURCE_CATEGORIES.map((category) => [category.id, 0]));
}

function cardQty(card) {
  return Math.max(1, Number(card?.qty) || 1);
}

function cardOracle(card) {
  return String(card?.oracleText || card?.oracle_text || "");
}

function cardTypeLine(card) {
  return String(card?.typeLine || card?.type_line || "");
}

function cardIsLand(card) {
  const cardType = String(card?.cardType || card?.card_type || "").toLowerCase();
  if (cardType === "land") {
    return true;
  }
  return /\bland\b/i.test(cardTypeLine(card));
}

function cardIsBasicLand(card) {
  if (card?.isBasicLand || card?.is_basic_land) {
    return true;
  }
  return /\bbasic\b/i.test(cardTypeLine(card));
}

function isChromaticColor(color) {
  return CHROMATIC_COLORS.includes(color);
}

/** Pip weight for a single mana symbol token (no braces). */
export function pipWeightForSymbol(symbol) {
  const token = String(symbol || "").trim().toUpperCase();
  if (!token) {
    return [];
  }
  if (MANA_COLORS.includes(token)) {
    return [{ color: token, weight: 1 }];
  }
  if (/^[WUBRG]\/P$/.test(token)) {
    return [{ color: token[0], weight: 1 }];
  }
  if (/^[2C]\/[WUBRG]$/.test(token)) {
    return [{ color: token.slice(-1), weight: 1 }];
  }
  if (/^[WUBRG]\/[WUBRG]$/.test(token)) {
    return [
      { color: token[0], weight: 0.5 },
      { color: token[2], weight: 0.5 },
    ];
  }
  return [];
}

export function countPipsFromManaCost(manaCost) {
  const counts = emptyColorCounts();
  for (const symbol of parseManaCostSymbols(manaCost)) {
    for (const { color, weight } of pipWeightForSymbol(symbol)) {
      counts[color] += weight;
    }
  }
  return counts;
}

/** Nonland main + commander cards (sideboard excluded). */
export function cardsForPipAnalysis(cards = []) {
  return (cards || []).filter((card) => {
    if (String(card.section || "main") === "sideboard") {
      return false;
    }
    return !cardIsLand(card);
  });
}

export function cardsForManaSourceAnalysis(cards = []) {
  return mainDeckCardsForOverview(cards);
}

/** @deprecated Prefer cardsForManaSourceAnalysis */
export function landsForManaAnalysis(cards = []) {
  return cardsForManaSourceAnalysis(cards).filter(cardIsLand);
}

export function buildColorPipBreakdown(cards = []) {
  const pool = cardsForPipAnalysis(cards);
  const counts = emptyColorCounts();
  let total = 0;

  for (const card of pool) {
    const qty = cardQty(card);
    const pips = countPipsFromManaCost(card.manaCost || card.mana_cost || "");
    for (const color of MANA_COLORS) {
      const value = pips[color] * qty;
      counts[color] += value;
      total += value;
    }
  }

  const rows = MANA_COLORS
    .map((color, index) => ({
      id: color,
      label: MANA_COLOR_LABELS[color],
      count: Math.round(counts[color] * 10) / 10,
      share: total ? counts[color] / total : 0,
      colorIndex: index,
    }))
    .filter((row) => row.count > 0);

  return {
    total: Math.round(total * 10) / 10,
    rows,
    counts,
    hasData: total > 0,
  };
}

export function filterCardsByPipColor(cards = [], colorId) {
  const color = String(colorId || "").toUpperCase();
  if (!MANA_COLORS.includes(color)) {
    return [];
  }
  return cardsForPipAnalysis(cards)
    .filter((card) => countPipsFromManaCost(card.manaCost || card.mana_cost || "")[color] > 0)
    .sort((left, right) => String(left?.cardName || "").localeCompare(String(right?.cardName || "")));
}

function colorsFromLandTypeLine(typeLine) {
  const colors = new Set();
  const match = String(typeLine || "").match(/—\s*(.+)$/u);
  if (!match) {
    return colors;
  }
  for (const part of match[1].split(/\s+/)) {
    const mapped = BASIC_LAND_TYPES[part.toLowerCase()];
    if (mapped) {
      colors.add(mapped);
    }
  }
  return colors;
}

function addSymbolsFromText(text, colors) {
  MANA_SYMBOL.lastIndex = 0;
  let match = MANA_SYMBOL.exec(text);
  while (match) {
    const token = match[1].toUpperCase();
    for (const { color } of pipWeightForSymbol(token)) {
      colors.add(color);
    }
    match = MANA_SYMBOL.exec(text);
  }
}

/**
 * Infer produced colors from type line + oracle text.
 * Any-color sources (Command Tower, Arcane Signet, …) set `anyColor: true`.
 * Colorless ({C}) is tracked separately and is not covered by any-color.
 */
export function cardManaProduction(card) {
  const typeLine = cardTypeLine(card);
  const oracle = cardOracle(card);
  const colors = cardIsLand(card) ? colorsFromLandTypeLine(typeLine) : new Set();
  let anyColor = ANY_COLOR_PHRASE.test(oracle);

  ADD_CLAUSE.lastIndex = 0;
  let clause = ADD_CLAUSE.exec(oracle);
  while (clause) {
    const body = clause[1] || "";
    if (ANY_COLOR_PHRASE.test(body)) {
      anyColor = true;
    }
    addSymbolsFromText(body, colors);
    clause = ADD_CLAUSE.exec(oracle);
  }

  // Basics often only have reminder text; type line already covered them.
  if (!colors.size && !anyColor && /\(\{t\}: add/i.test(oracle)) {
    addSymbolsFromText(oracle, colors);
  }

  const produced = MANA_COLORS.filter((color) => colors.has(color));
  return {
    colors: produced,
    anyColor,
    hasColorless: produced.includes("C"),
  };
}

/** @deprecated Prefer cardManaProduction */
export function landManaProduction(card) {
  return cardManaProduction(card);
}

export function manaSourceCategory(card) {
  if (cardIsLand(card)) {
    return cardIsBasicLand(card) ? "basic" : "land";
  }
  const cardType = String(card?.cardType || card?.card_type || "").toLowerCase();
  if (cardType === "creature" || /\bcreature\b/i.test(cardTypeLine(card))) {
    return "creature";
  }
  if (cardType === "artifact" || /\bartifact\b/i.test(cardTypeLine(card))) {
    if (/\bcreature\b/i.test(cardTypeLine(card))) {
      return "creature";
    }
    return "artifact";
  }
  if (cardType === "enchantment" || /\benchantment\b/i.test(cardTypeLine(card))) {
    return "enchantment";
  }
  return "other";
}

function cardKey(card) {
  return `${card.setCode}|${card.collectorNumber}|${card.finish}|${card.cardName}`;
}

/**
 * Stacked mana sources per color: basic lands, other lands, creatures, artifacts, …
 * Any-color producers count toward each chromatic color the deck uses (not colorless).
 */
export function buildManaSourceStack(cards = []) {
  const pipMeta = buildColorPipBreakdown(cards);
  const pool = cardsForManaSourceAnalysis(cards);

  const fixedByCategory = Object.fromEntries(
    MANA_COLORS.map((color) => [color, emptyCategoryCounts()]),
  );
  const cardsByColor = Object.fromEntries(MANA_COLORS.map((color) => [color, []]));
  const anyColorByCategory = emptyCategoryCounts();
  const anyColorCards = [];
  let anyColorCount = 0;
  let sourceCount = 0;

  for (const card of pool) {
    const production = cardManaProduction(card);
    const contributes = production.anyColor || production.colors.length > 0;
    if (!contributes) {
      continue;
    }
    const qty = cardQty(card);
    const category = manaSourceCategory(card);
    sourceCount += qty;

    if (production.anyColor) {
      anyColorCount += qty;
      anyColorByCategory[category] += qty;
      anyColorCards.push(card);
    }
    for (const color of production.colors) {
      fixedByCategory[color][category] += qty;
      cardsByColor[color].push(card);
    }
  }

  const activeColors = MANA_COLORS.filter((color) => {
    if (pipMeta.counts[color] > 0) {
      return true;
    }
    return MANA_SOURCE_CATEGORIES.some((category) => fixedByCategory[color][category.id] > 0);
  });

  const rows = activeColors.map((color) => {
    const stacks = MANA_SOURCE_CATEGORIES.map((category) => {
      const fixed = fixedByCategory[color][category.id];
      // Any-color mana cannot pay {C} requirements.
      const any = isChromaticColor(color) ? anyColorByCategory[category.id] : 0;
      const count = fixed + any;
      return {
        id: category.id,
        label: category.label,
        count,
        fixed,
        any,
      };
    }).filter((stack) => stack.count > 0);

    const total = stacks.reduce((sum, stack) => sum + stack.count, 0);
    const pips = pipMeta.counts[color] || 0;
    const pipShare = pipMeta.total ? pips / pipMeta.total : 0;
    return {
      id: color,
      label: MANA_COLOR_LABELS[color],
      total,
      stacks,
      pips: Math.round(pips * 10) / 10,
      pipShare,
      pipPercent: Math.round(pipShare * 100),
    };
  }).filter((row) => row.total > 0 || row.pips > 0);

  const sourceTotal = rows.reduce((sum, row) => sum + row.total, 0);
  const rowsWithRatio = rows.map((row) => {
    const sourceShare = sourceTotal ? row.total / sourceTotal : 0;
    const sourcePercent = Math.round(sourceShare * 100);
    const ratio = row.pipShare > 0
      ? Math.round((sourceShare / row.pipShare) * 100) / 100
      : (row.total > 0 ? null : 0);
    return {
      ...row,
      sourceShare,
      sourcePercent,
      ratio,
    };
  });

  const maxValue = Math.max(1, ...rowsWithRatio.map((row) => row.total));
  const activeCategories = MANA_SOURCE_CATEGORIES.filter((category) => (
    rowsWithRatio.some((row) => row.stacks.some((stack) => stack.id === category.id && stack.count > 0))
  ));

  return {
    rows: rowsWithRatio,
    categories: activeCategories,
    sourceCount,
    sourceTotal,
    totalPips: pipMeta.total,
    anyColorCount,
    anyColorCards,
    cardsByColor,
    maxValue,
    hasData: rowsWithRatio.length > 0,
  };
}

/** @deprecated Prefer buildManaSourceStack */
export function buildLandManaComparison(cards = []) {
  return buildManaSourceStack(cards);
}

export function filterManaSourcesByColor(stack, colorId, categoryId = null) {
  const color = String(colorId || "").toUpperCase();
  if (!MANA_COLORS.includes(color) || !stack) {
    return [];
  }
  const fixed = stack.cardsByColor?.[color] || [];
  const anyCards = isChromaticColor(color) ? (stack.anyColorCards || []) : [];
  const seen = new Set();
  const merged = [];
  for (const card of [...fixed, ...anyCards]) {
    const key = cardKey(card);
    if (seen.has(key)) {
      continue;
    }
    if (categoryId && manaSourceCategory(card) !== categoryId) {
      continue;
    }
    seen.add(key);
    merged.push(card);
  }
  return merged.sort((left, right) => (
    String(left?.cardName || "").localeCompare(String(right?.cardName || ""))
  ));
}

/** @deprecated Prefer filterManaSourcesByColor */
export function filterLandsByManaColor(comparison, colorId) {
  return filterManaSourcesByColor(comparison, colorId);
}
