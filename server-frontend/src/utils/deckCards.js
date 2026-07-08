import { COLLECTION_TYPE_LABELS, COLLECTION_TYPE_ORDER } from "./collectionTypes";

export const DECK_COLOR_ORDER = ["W", "U", "B", "R", "G", "C"];

export const DECK_COLOR_LABELS = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
  C: "Colorless",
};

const SECTION_ORDER = { commander: 0, main: 1, sideboard: 2 };

export function deckTypeIconType(source) {
  if (!source) {
    return "";
  }
  if (typeof source === "object") {
    if (source.kind === "type" && source.type) {
      return String(source.type).toLowerCase();
    }
    if (source.section === "commander") {
      return "commander";
    }
    if (source.section === "sideboard") {
      return "sideboard";
    }
    return "";
  }
  return String(source).toLowerCase();
}

export function deckTypeLabel(type) {
  if (!type) {
    return "Unknown";
  }
  const normalized = String(type).toLowerCase();
  return COLLECTION_TYPE_LABELS[normalized]
    || normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export function deckTypeHeadingLabel(type) {
  return deckTypeLabel(type).toUpperCase();
}

export function countDeckCards(cards) {
  return (cards || []).reduce((sum, card) => sum + (Number(card.qty) || 0), 0);
}

export function deckTypeCounts(cards) {
  const counts = new Map();
  for (const card of cards || []) {
    const type = cardTypeGroup(card);
    if (!type) {
      continue;
    }
    counts.set(type, (counts.get(type) || 0) + (Number(card.qty) || 0));
  }
  return counts;
}

export function formatDeckGroupHeading(group) {
  const count = group.count ?? countDeckCards(group.cards);
  if (group.kind === "type") {
    return `${deckTypeHeadingLabel(group.type)} (${count})`;
  }
  return `${group.label} (${count})`;
}

export function cardTypeGroup(card) {
  return String(card?.cardType || "").toLowerCase();
}

function deckTypeSortIndex(type) {
  const index = COLLECTION_TYPE_ORDER.indexOf(type);
  return index === -1 ? 999 : index;
}

export function collectDeckCardTypes(cards) {
  const types = new Set();
  for (const card of cards || []) {
    const type = cardTypeGroup(card);
    if (type) {
      types.add(type);
    }
  }
  return [...types].sort((left, right) => {
    const sortDiff = deckTypeSortIndex(left) - deckTypeSortIndex(right);
    if (sortDiff !== 0) {
      return sortDiff;
    }
    return left.localeCompare(right);
  });
}

export function cardMatchesColorFilter(card, selectedColors) {
  if (!selectedColors?.length) {
    return true;
  }
  const colors = card?.colors || [];
  if (selectedColors.includes("C") && colors.length === 0) {
    return true;
  }
  return selectedColors.some((color) => color !== "C" && colors.includes(color));
}

export function cardMatchesTypeFilter(card, typeFilter) {
  if (!typeFilter || typeFilter === "all") {
    return true;
  }
  return cardTypeGroup(card) === typeFilter;
}

function compareNames(left, right) {
  return String(left?.cardName || "").localeCompare(String(right?.cardName || ""));
}

function typeSortIndex(card) {
  return deckTypeSortIndex(cardTypeGroup(card));
}

function colorSortKey(card) {
  const colors = card?.colors || [];
  if (!colors.length) {
    return DECK_COLOR_ORDER.indexOf("C");
  }
  return Math.min(...colors.map((color) => {
    const index = DECK_COLOR_ORDER.indexOf(color);
    return index === -1 ? 99 : index;
  }));
}

export function sortDeckCards(cards, sortBy) {
  const sorted = [...(cards || [])];
  sorted.sort((left, right) => {
    if (sortBy === "value") {
      const valueDiff = (right.currentValue || 0) - (left.currentValue || 0);
      if (valueDiff !== 0) {
        return valueDiff;
      }
    } else if (sortBy === "type") {
      const typeDiff = typeSortIndex(left) - typeSortIndex(right);
      if (typeDiff !== 0) {
        return typeDiff;
      }
    } else if (sortBy === "color") {
      const colorDiff = colorSortKey(left) - colorSortKey(right);
      if (colorDiff !== 0) {
        return colorDiff;
      }
    }
    return compareNames(left, right);
  });
  return sorted;
}

export function filterDeckCards(cards, { typeFilter = "all", colorFilters = [] } = {}) {
  return (cards || []).filter(
    (card) => cardMatchesTypeFilter(card, typeFilter)
      && cardMatchesColorFilter(card, colorFilters),
  );
}

export function splitCommanderCards(cards) {
  const commanders = [];
  const deckCards = [];
  for (const card of cards || []) {
    if (card.section === "commander") {
      commanders.push(card);
    } else {
      deckCards.push(card);
    }
  }
  return { commanders, deckCards };
}

export function buildEmptyDeckCardGroups(section = "main") {
  const sectionLabel = section === "sideboard" ? "Sideboard" : "Main deck";
  return [
    {
      key: `section-${section}`,
      kind: "section",
      section,
      label: sectionLabel,
      cards: [],
    },
    {
      key: `${section}-any`,
      kind: "type",
      section,
      type: "",
      label: "Cards",
      cards: [],
    },
  ];
}

export function buildDeckCardGroups(cards, sortBy = "name") {
  const bySection = new Map();
  for (const card of cards || []) {
    const section = card.section || "main";
    if (!bySection.has(section)) {
      bySection.set(section, []);
    }
    bySection.get(section).push(card);
  }

  const groups = [];
  for (const section of [...bySection.keys()].sort(
    (left, right) => (SECTION_ORDER[left] ?? 99) - (SECTION_ORDER[right] ?? 99),
  )) {
    const sectionCards = bySection.get(section) || [];
    if (!sectionCards.length) {
      continue;
    }

    if (section === "commander") {
      groups.push({
        key: `section-${section}`,
        kind: "section",
        section,
        label: "Commander",
        count: countDeckCards(sectionCards),
        cards: sortDeckCards(sectionCards, sortBy),
      });
      continue;
    }

    const sectionLabel = section === "sideboard" ? "Sideboard" : "Main deck";
    groups.push({
      key: `section-${section}`,
      kind: "section",
      section,
      label: sectionLabel,
      count: countDeckCards(sectionCards),
      cards: [],
    });

    for (const type of collectDeckCardTypes(sectionCards)) {
      const typeCards = sectionCards.filter((card) => cardTypeGroup(card) === type);
      if (!typeCards.length) {
        continue;
      }
      groups.push({
        key: `${section}-${type}`,
        kind: "type",
        section,
        type,
        label: deckTypeLabel(type),
        count: countDeckCards(typeCards),
        cards: sortDeckCards(typeCards, sortBy),
      });
    }
  }

  return groups;
}

export function flattenGroupedDeckCards(groups) {
  const rows = [];
  for (const group of groups || []) {
    if (group.kind === "section" && group.cards?.length) {
      rows.push({ kind: "heading", group });
      for (const card of group.cards) {
        rows.push({ kind: "card", card, group });
      }
      continue;
    }
    if (group.kind === "type") {
      rows.push({ kind: "heading", group });
      for (const card of group.cards) {
        rows.push({ kind: "card", card, group });
      }
    }
  }
  return rows;
}
