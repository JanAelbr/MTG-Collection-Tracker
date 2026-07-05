export const DECK_TYPE_ORDER = ["creature", "artifact", "sorcery", "instant", "others", "land"];

export const DECK_TYPE_LABELS = {
  creature: "Creatures",
  artifact: "Artifacts",
  sorcery: "Sorceries",
  instant: "Instants",
  others: "Other",
  land: "Lands",
};

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

export function cardTypeGroup(card) {
  const type = String(card?.cardType || "").toLowerCase();
  if (DECK_TYPE_ORDER.includes(type)) {
    return type;
  }
  return "others";
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
  return DECK_TYPE_ORDER.indexOf(cardTypeGroup(card));
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
      cards: [],
    });

    for (const type of DECK_TYPE_ORDER) {
      const typeCards = sectionCards.filter((card) => cardTypeGroup(card) === type);
      if (!typeCards.length) {
        continue;
      }
      groups.push({
        key: `${section}-${type}`,
        kind: "type",
        section,
        type,
        label: DECK_TYPE_LABELS[type],
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
